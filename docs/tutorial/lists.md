# Listas longas

Uma lista de 10 mil itens não pode virar 10 mil nós no DOM. O tempestweb resolve
isso com **listas virtualizadas**: você declara *quantos* itens existem e *como*
construir o item de um índice, e só a janela visível é materializada.

Nesta página você monta uma lista virtualizada, liga **infinite scroll** e
**pull-to-refresh** — as duas bordas de qualquer lista de verdade. 🚀

## Virtualização: o `LazyColumn`

Comece pelo caso mais simples: mil itens, uma janela.

```python
from tempest_core import App, Container, Style, Text, Widget
from tempest_core import Edge
from tempest_core import LazyColumn


def view(app: App[None]) -> Widget:
    """Render a thousand items with only a window in the DOM."""

    def build_row(index: int) -> Widget:
        return Container(
            key=str(index),
            style=Style(padding=Edge.all(8)),
            child=Text(content=f"Item {index}", key=f"t{index}"),
        )

    return LazyColumn(
        key="rows",
        item_count=1000,
        item_builder=build_row,
        window_size=30,
        style=Style(height=300.0),
    )
```

Pedaço por pedaço:

* **`item_count=1000`** — o tamanho da lista inteira. É o que a barra de rolagem
  descreve.
* **`item_builder=build_row`** — a fábrica que constrói o item de um índice. É um
  callable Python: nunca atravessa o fio, e só é chamado para os índices da
  janela.
* **`window_size=30`** — quantos itens são materializados. Peça mais do que cabe
  no viewport, para haver folga antes de a janela precisar deslizar.
* **`style=Style(height=300.0)`** — a altura é o que faz o elemento virar um
  viewport rolável. Sem altura, a lista cresce com o conteúdo e não rola.

!!! tip "Cada item precisa de `key`"
    O item é keado pelo índice absoluto, então uma janela que desliza vira uma
    sequência mínima de remove/reorder/insert em vez de uma árvore nova.

O resultado no browser: **30 nós** no DOM e uma barra de rolagem de mil itens —
o espaço fora da janela é reservado sem criar elemento nenhum.

## Infinite scroll: `on_end_reached`

Lista paginada não sabe o tamanho final: ela carrega mais quando o leitor chega
perto do fim. Declare `on_end_reached`.

```python
from dataclasses import dataclass

from tempest_core import App, Container, Style, Text, Widget
from tempest_core import Edge
from tempest_core import EndReachedEvent
from tempest_core import LazyColumn

PAGE_SIZE = 25
TOTAL_ITEMS = 200


@dataclass
class ListState:
    """How many items are available so far."""

    loaded: int = PAGE_SIZE


def view(app: App[ListState]) -> Widget:
    """Render a list that loads another page at its end."""

    def build_row(index: int) -> Widget:
        return Container(
            key=str(index),
            style=Style(padding=Edge.all(8)),
            child=Text(content=f"Item {index}", key=f"t{index}"),
        )

    def load_more(event: EndReachedEvent) -> None:
        if app.state.loaded >= TOTAL_ITEMS:
            return
        app.set_state(
            lambda state: setattr(
                state, "loaded", min(TOTAL_ITEMS, state.loaded + PAGE_SIZE)
            )
        )

    return LazyColumn(
        key="rows",
        item_count=app.state.loaded,
        item_builder=build_row,
        window_size=30,
        end_reached_threshold=0.8,
        on_end_reached=load_more,
        style=Style(height=300.0),
    )
```

`end_reached_threshold` é a fração do scroll que dispara o evento — `0.8`, o
default, significa "a 80% do caminho". O cliente reporta `end_reached` **uma vez
por travessia**: entrou na zona final, avisou, e só volta a avisar depois de a
lista sair dela (o que acontece naturalmente quando o handler acrescenta itens).

!!! warning "Sempre tenha uma condição de parada"
    O evento continua sendo reportado enquanto o leitor rola no fim da lista. Se
    o handler crescer o estado sem limite, a lista cresce para sempre. O `return`
    quando tudo já foi carregado é o que torna isso inofensivo — responder com
    estado inalterado é uma resposta perfeitamente válida.

## Pull-to-refresh: `on_refresh` + `refreshing`

O DOM não tem pull-to-refresh de elemento, então o cliente reconhece o gesto:
um arrasto **a partir da origem do scroll**, ao longo do eixo da lista, passando
de 64px. Fora da origem o arrasto é scroll, não pull.

```python
import asyncio

from tempest_core import RefreshEvent


async def reload(event: RefreshEvent) -> None:
    """Reload the list from the top."""
    app.set_state(lambda state: setattr(state, "refreshing", True))
    await asyncio.sleep(0.6)  # a busca de verdade entra aqui

    def done(state: ListState) -> None:
        state.refreshing = False
        state.loaded = PAGE_SIZE

    app.set_state(done)
```

Passe o handler **e** o estado para a lista:

```python
LazyColumn(
    key="rows",
    item_count=app.state.loaded,
    item_builder=build_row,
    refreshing=app.state.refreshing,
    on_refresh=reload,
    on_end_reached=load_more,
    style=Style(height=300.0),
)
```

`refreshing` faz duas coisas: desenha o indicador (uma faixa na borda do pull) e
**bloqueia um segundo pull** enquanto a recarga está em voo. Também vira
`aria-busy`, para a espera ser anunciada.

!!! note "Handler async é o que torna o estado visível"
    Um handler sincrono liga e desliga `refreshing` no mesmo tick — o leitor
    nunca vê o indicador. `async` + `await` da busca real renderiza o estado
    intermediário.

### `RefreshControl`: o gesto sem a lista

Quer pull-to-refresh em conteúdo que não é lista? Use o controle avulso:

```python
from tempest_core import RefreshControl

RefreshControl(key="pull", refreshing=app.state.refreshing, on_refresh=reload)
```

Ele é uma folha da IR: o renderizador é dono do que aparece dentro — um spinner
invisível em repouso, visível quando o pull arma, girando enquanto `refreshing`
está ativo.

## `SectionList`: a lista que corre na página

`SectionList` agrupa seções com cabeçalho e itens virtualizados por seção. Ela
não é um viewport com altura própria: corre no fluxo da página. `on_end_reached`
funciona igual — o progresso é medido por quanto da caixa da lista o viewport da
página já revelou.

??? info "Detalhes técnicos: como o cliente mede o fim"
    O renderizador marca a lista com `data-tw-end-threshold`, e o cliente
    (`client/lists.js`) escolhe a geometria:

    * elemento que rola a própria caixa →
      `(scrollTop + clientHeight) / scrollHeight`, que numa lista virtualizada já
      inclui o espaço reservado fora da janela, e portanto acompanha o
      `item_count` real;
    * elemento no fluxo da página → quanto da caixa o viewport revelou.

    O gesto de pull vira `data-tw-refresh` (`y`/`x`, então num `LazyRow` o pull é
    para a direita) e o estado armado vira `data-tw-pull-armed`. No fio, os dois
    eventos são `{"type": "end_reached", "key": "..."}` e
    `{"type": "refresh", "key": "..."}` — sem payload, iguais nos três modos.

## Recap

* `LazyColumn` / `LazyRow` / `LazyGrid` declaram `item_count` +
  `item_builder`; só a janela existe no DOM. A altura no `Style` é o que faz o
  viewport rolar.
* `on_end_reached` + `end_reached_threshold` dão infinite scroll — com uma
  condição de parada no handler.
* `on_refresh` + `refreshing` dão pull-to-refresh, com indicador e sem recarga
  duplicada. Handler `async` para o estado ser visível.
* `RefreshControl` leva o gesto para conteúdo que não é lista.
* `SectionList` mede o fim pelo scroll da página, não pelo próprio.

O exemplo completo, com as três coisas ligadas ao mesmo tempo, está em
[`examples/list_demo/app.py`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/list_demo/app.py):

```bash
tempestweb run --mode server --path examples/list_demo
```
