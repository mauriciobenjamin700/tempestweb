# Gestos: arrastar, reordenar, paginar

Três gestos que o navegador não dá de graça a um elemento qualquer, e que o
tempestweb entrega como widget: soltar uma coisa em cima de outra, reordenar uma
lista arrastando, e virar página num carrossel. Você declara o handler; o cliente
reconhece o gesto e reporta.

## Arrastar e soltar

`Draggable` carrega um dado; `DragTarget` aceita a soltura. O par implementa o
contrato HTML5 de drag, então funciona com mouse e trackpad sem nenhuma
biblioteca:

```python
from tempest_core import App, Text, Widget
from tempest_core import DragEvent
from tempest_core import Draggable, DragTarget


def view(app: App[Board]) -> Widget:
    """Render a card that can be dropped into a column."""

    def dropped(event: DragEvent) -> None:
        app.set_state(lambda state: state.move(event.data, to="done"))

    return DragTarget(
        key="done",
        on_drop=dropped,
        child=Draggable(
            key="card-7",
            drag_data="card-7",
            child=Text(content="Escrever o post"),
        ),
    )
```

O `drag_data` é o que chega em `event.data` no `on_drop` — normalmente o id do
que foi arrastado. `on_drag` avisa quando a arrastada começou, se você quiser
pintar o estado "carregando isto".

!!! warning "`child`, não `children`"
    `Draggable` e `DragTarget` embrulham **um** widget: o campo é `child`. Passar
    `children=` levanta `ValidationError` com o nome do campo — o core recusa
    kwarg que não declara. Precisa de vários filhos? Ponha uma `Column`/`Row`
    dentro do `child`, como faz o [Kanban](../examples/kanban-board.md).

## Reordenar uma lista

`ReorderableList` é o caso em que o item não vai *para outro lugar*: ele muda de
posição dentro da própria lista. O handler recebe as duas posições — e mover é
trabalho da app, porque a ordem é estado:

```python
from tempest_core import App, Container, Style, Text, Widget
from tempest_core import Edge
from tempest_core import ReorderEvent
from tempest_core import ReorderableList


def view(app: App[Tasks]) -> Widget:
    """Render a list whose rows are sorted by dragging."""

    def moved(event: ReorderEvent) -> None:
        def mutate(state: Tasks) -> None:
            task = state.tasks.pop(event.from_index)
            state.tasks.insert(event.to_index, task)

        app.set_state(mutate)

    return ReorderableList(
        key="tasks",
        style=Style(gap=8.0),
        children=[
            Container(
                key=f"task-{task}",
                style=Style(padding=Edge.all(12)),
                child=Text(content=task),
            )
            for task in app.state.tasks
        ],
        on_reorder=moved,
    )
```

* Os filhos são widgets comuns: o cliente é que os marca arrastáveis, depois de
  cada batch de patches, e desenha o cursor de "pegar".
* As posições são calculadas no momento do evento, a partir do DOM — nada é
  gravado no item. Um índice gravado ficaria velho no instante em que a lista
  mudasse.
* Soltar a linha no lugar de onde ela saiu não reporta nada.

!!! tip "Dê `key` a cada linha"
    A key é o que permite ao reconciliador transformar a reordenação em um
    remove/insert mínimo em vez de reescrever todas as linhas.

## Carrossel por página

`PageView` mostra um filho por vez e declara `page` + `on_page_change`. Ele é um
scroller horizontal com *snap*, o que dá swipe no touch, no trackpad e no
`shift`+roda — o navegador é bom nisso. O que ele não faz é dizer em qual página
parou; isso é o que o cliente reporta.

```python
from tempest_core import PageChangeEvent
from tempest_core import PageView


def view(app: App[Tour]) -> Widget:
    """Render a three-slide tour with dots and a Next button."""

    def changed(event: PageChangeEvent) -> None:
        app.set_state(lambda state: setattr(state, "page", event.page))

    return PageView(
        key="tour",
        page=app.state.page,
        children=[_slide(index) for index in range(3)],
        on_page_change=changed,
    )
```

O caminho é de mão dupla: o leitor arrasta e o `page` do estado acompanha; a app
muda `page` (um botão "Próximo", por exemplo) e o carrossel rola até lá.

!!! note "O reporte espera o scroll parar"
    Uma rolagem é uma sequência de eventos, e as posições intermediárias
    arredondam para a página que está sendo *deixada*. Reportá-las fazia a app
    brigar consigo mesma — aperta "Próximo", o carrossel começa a andar, e o
    primeiro evento intermediário dizia "voltou para a página anterior". Por isso
    a página só é reportada depois de um instante de silêncio, quando o carrossel
    assentou.

## Gestos de ponteiro: toque, arrasto, pinça

`GestureDetector` reconhece os gestos discretos — `on_tap`, `on_double_tap`,
`on_long_press`, `on_swipe`. Os contínuos têm widget próprio, porque o evento que
eles reportam é outro:

| Widget | Handler | Recebe |
| --- | --- | --- |
| `PanHandler` | `on_pan` | `PanEvent{dx, dy, vx, vy}` — o passo do arrasto e sua velocidade |
| `ScaleHandler` | `on_scale` · `on_double_tap` | `ScaleEvent{scale, focus_x, focus_y, rotation}` |
| `InteractiveViewer` | `on_interaction` | `ScaleEvent` — um dedo faz pan, dois fazem zoom |

```python
from tempest_core import PanEvent, ScaleEvent
from tempest_core import InteractiveViewer, PanHandler


def on_pan(event: PanEvent) -> None:
    """Accumulate the drag — a pan step is relative, not absolute."""

    def mutate(state: Board) -> None:
        state.offset_x += event.dx
        state.offset_y += event.dy

    app.set_state(mutate)


def on_interaction(event: ScaleEvent) -> None:
    """Follow the viewer: the scale zooms, the focus says where."""
    app.set_state(lambda state: setattr(state, "zoom", event.scale))


PanHandler(key="pad", on_pan=on_pan, child=...)
InteractiveViewer(key="map", on_interaction=on_interaction, child=...)
```

Três coisas que decidem se isso funciona bem:

* **`on_pan` é relativo.** Cada evento é o passo desde o anterior, então a app
  acumula. Isso é o que permite arrastar sem saber onde o gesto começou.
* **`on_interaction` recebe `ScaleEvent` mesmo quando é só pan** — um dedo
  reporta `scale=1` e o foco onde o dedo está; a app deriva a translação do foco
  que se move.
* **A folha base tira o `touch-action` dessas três superfícies**, e só delas: um
  browser não manda `pointermove` enquanto está ocupado rolando a própria página.
  O `GestureDetector` fica de fora de propósito — tap, swipe e long press
  convivem com a rolagem, e tirar o `touch-action` dele quebraria o scroll de
  qualquer lista que envolva as linhas num detector.

!!! note "Gesto contínuo é reportado uma vez por frame"
    Um `pointermove` chega 60–120 vezes por segundo, e no Modo B cada um é uma
    ida e volta. O cliente reporta no máximo um por frame, mantendo o **último**
    valor, e descarrega o pendente quando o dedo sai — sem isso, largar uma pinça
    de 2× deixava a app em 1,5× (medido no Chrome), porque o frame que levaria o
    último movimento nunca vinha.

## Recapitulando

* `Draggable` + `DragTarget`: soltar uma coisa em outra, com `drag_data`
  chegando em `event.data`.
* `ReorderableList` + `on_reorder`: `from_index` e `to_index`; mover é da app.
* `PageView` + `on_page_change`: swipe nativo com snap, reporte quando assenta, e
  a app pode mover `page` de volta.
* `PanHandler` / `ScaleHandler` / `InteractiveViewer`: arrasto e pinça, um
  reporte por frame, `touch-action` tirado só dessas superfícies.

Exemplos completos:
[`examples/reorder_demo`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/reorder_demo/app.py),
[`examples/onboarding-carousel`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/onboarding-carousel/app.py)
e [`examples/kanban-board`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/kanban-board/app.py):

```bash
tempestweb run --mode server --path examples/reorder_demo
```
