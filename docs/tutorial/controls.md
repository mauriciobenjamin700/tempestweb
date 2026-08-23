# Controles: campos, switches, sliders e pickers

Um formulário é feito de controles, e cada controle tem duas metades: o que ele
**desenha** e o que ele **reporta**. No tempestweb você declara o widget do core;
o renderizador escolhe o elemento HTML nativo e o cliente reporta o evento que o
seu handler declarou.

Esta página é o mapa das duas metades. 🚀

## O princípio: o navegador já sabe

Cada controle do core vira o elemento que o navegador já sabe operar — com
teclado, foco, leitor de tela e, no celular, o teclado e o seletor certos:

| Widget | Elemento | Evento → handler | O que chega |
|---|---|---|---|
| `Input` | `<input>` | `input`/`change` → `on_change` | `TextChangeEvent(value)` |
| `TextArea` | `<textarea>` | `input`/`change` → `on_change` | `TextChangeEvent(value)` |
| `MaskedInput` | `<input>` + máscara | `input`/`change` → `on_change` | `TextChangeEvent(value)` |
| `PinInput` | `<input>` + `one-time-code` | `input` → `on_change`, `complete` | `TextChangeEvent(value)` |
| `Checkbox` | `<label>` + `<input type=checkbox>` | `change` → `on_change` | `ToggleEvent(checked)` |
| `Switch` | `<label>` + checkbox `role=switch` | `change` → `on_change` | `ToggleEvent(checked)` |
| `Slider` | `<input type=range>` | `input`/`change` → `on_change` | `SlideEvent(value)` |
| `RangeSlider` | dois `<input type=range>` | `input`/`change` → `on_change` | `RangeChangeEvent(low, high)` |
| `Dropdown` | `<select>` + `<option>` | `change` → `on_select` | `SelectEvent(value, index)` |
| `Autocomplete` | `<input>` + `<datalist>` | `input` → `on_change`, `select` → `on_select` | `TextChangeEvent` / `SelectEvent` |
| `DatePicker` | `<input type=date>` | `change` → `on_change` | `DateChangeEvent(value)` |
| `TimePicker` | `<input type=time>` | `change` → `on_change` | `TimeChangeEvent(value)` |
| `FilePicker` | `<input type=file>` | `change` → `on_select` | `FileSelectEvent(uri, name)` |
| `TabBar` | `role=tablist` + `role=tab` | `click` → `on_change` | `RouteChangeEvent(name, params)` |

Vale igual nos três modos: o renderizador (`client/dom.js`) é o mesmo no Modo A
(WASM), no Modo B (servidor) e no Modo C (transpilado).

!!! tip "O evento tem a forma do widget, não do DOM"
    Um `Switch` recebe `event.checked`, um `Slider` recebe `event.value`, um
    `RangeSlider` recebe `event.low`/`event.high`. Você nunca lê
    `payload["value"]` na mão — o runtime valida o payload no evento tipado que o
    handler declarou.

## Um switch e um slider

```python
from dataclasses import dataclass

from tempest_core import App, Column, SlideEvent, Slider, Switch, Text, ToggleEvent, Widget


@dataclass
class Prefs:
    """Preferências que a tela controla.

    Attributes:
        notify: Se as notificações estão ligadas.
        volume: Volume de reprodução, em ``[0, 100]``.
    """

    notify: bool = True
    volume: float = 70.0


def make_state() -> Prefs:
    """Estado inicial da tela."""
    return Prefs()


def view(app: App[Prefs]) -> Widget:
    """Desenha um switch e um slider ligados ao estado."""

    def toggle(event: ToggleEvent) -> None:
        app.set_state(lambda prefs: setattr(prefs, "notify", event.checked))

    def slide(event: SlideEvent) -> None:
        app.set_state(lambda prefs: setattr(prefs, "volume", event.value))

    return Column(
        key="prefs",
        children=[
            Switch(key="notify", label="Notificações", checked=app.state.notify, on_change=toggle),
            Slider(
                key="volume",
                value=app.state.volume,
                min_value=0.0,
                max_value=100.0,
                step=5.0,
                on_change=slide,
            ),
            Text(key="reading", content=f"Volume: {app.state.volume:.0f}%"),
        ],
    )
```

O `Text` no fim é o teste de fumaça mais rápido que existe: se você mexe no
slider e o texto não muda, o evento não chegou.

!!! note "Por que o `Switch` é um `<label>`"
    Quem carrega o estado é um `<input type=checkbox role=switch>` de verdade
    dentro do `<label>`. Assim o Espaço alterna, o Tab alcança, e o leitor de tela
    anuncia "switch, ligado" — de graça. A `label` é o elemento que tem a `key`, e
    o input dentro dela é do renderizador.

## Escolher de uma lista

`Dropdown` reporta `on_select` com o valor **e** o índice. O `placeholder` é uma
opção desabilitada na frente, e ela não desloca o índice:

```python
from tempest_core import App, Dropdown, SelectEvent, Widget

_CABINS: list[str] = ["Economy", "Premium", "Business", "First"]


def view(app: App[Booking]) -> Widget:
    """Desenha a escolha de cabine."""

    def choose(event: SelectEvent) -> None:
        def apply(booking: Booking) -> None:
            booking.cabin = event.value
            booking.cabin_index = event.index

        app.set_state(apply)

    return Dropdown(
        key="cabin",
        options=_CABINS,
        value=app.state.cabin,
        placeholder="Escolha uma cabine",
        on_select=choose,
    )
```

`Autocomplete` é o irmão que aceita texto livre: as `options` viram um
`<datalist>` que o navegador desenha, `on_change` chega a cada tecla e
`on_select` chega quando o que está no campo é exatamente uma das opções.

## Data, hora e arquivo

Os três pickers usam o controle da plataforma — o calendário do navegador é
melhor do que qualquer um que este renderizador desenharia, e no celular é o
seletor nativo:

```python
from tempest_core import App, Column, DateChangeEvent, DatePicker, FilePicker, FileSelectEvent, Widget


def view(app: App[Booking]) -> Widget:
    """Desenha a data de partida e o anexo."""

    def when(event: DateChangeEvent) -> None:
        app.set_state(lambda b: setattr(b, "departure", event.value))

    def attach(event: FileSelectEvent) -> None:
        app.set_state(lambda b: setattr(b, "document", event.name or ""))

    return Column(
        key="trip",
        children=[
            DatePicker(key="departure", label="Partida", value=app.state.departure, on_change=when),
            FilePicker(key="doc", label="Anexar RG", value=app.state.document, on_select=attach),
        ],
    )
```

!!! warning "O `value` de um `FilePicker` é só leitura"
    Nenhuma página pode atribuir o valor de um `<input type=file>` — é uma
    proteção do navegador, não uma limitação daqui. O `value` que você passa é
    **exibido** ao lado do botão (o renderizador o reflete num atributo que a
    folha base imprime), e o que chega no `on_select` é o `name` do arquivo mais
    um `uri` `blob:` para os bytes.

## Abas: `TabBar` desenha, `TabView` mostra

São dois widgets, e isso é de propósito:

```python
from tempest_core import App, Column, RouteChangeEvent, TabBar, TabView, Widget

_TABS: list[str] = ["Visão geral", "Atividade", "Ajustes"]


def view(app: App[Profile]) -> Widget:
    """Desenha a faixa de abas acima do painel."""

    def switch(event: RouteChangeEvent) -> None:
        app.set_state(lambda p: setattr(p, "tab", int(event.params.get("index", 0))))

    return Column(
        key="profile",
        children=[
            TabBar(key="tabs", tabs=_TABS, active=app.state.tab, on_change=switch),
            TabView(key="panel", tabs=_TABS, active=app.state.tab, child=_section(app.state)),
        ],
    )
```

!!! info "Detalhes técnicos — por que o `TabView` não desenha as próprias abas"
    Um `TabView` tem um **filho de IR** (o painel), e patch path endereça filho
    por índice. Uma faixa de abas criada pelo renderizador ocuparia o índice 0 e
    todo patch seguinte apontaria para o elemento errado — é a regra do contrato:
    filho criado pelo renderizador só é legal dentro de folha da IR.

    O `TabBar` **é** uma folha, então ele pode desenhar os próprios botões. O que
    o `TabView` faz é dizer a verdade sobre o estado: `role="tabpanel"` e o nome
    da aba ativa em `aria-label`. Ligue os dois no mesmo handler, como acima.

    O mesmo vale para o `RouteDrawer`: ele tem dois filhos de IR (conteúdo e
    gaveta), então o `open` vira o atributo `data-tw-open` que a folha base usa
    para deslizar a gaveta por cima do conteúdo. Quem alterna é um botão seu.

## Recap

* Todo controle do core vira o elemento nativo equivalente — teclado, foco e
  a11y vêm do navegador.
* O handler recebe o **evento tipado do widget** (`checked`, `value`,
  `low`/`high`, `value`/`index`), nunca um dicionário cru.
* `Dropdown` e `FilePicker` reportam `on_select`; os demais campos reportam
  `on_change`.
* `TabBar` desenha a faixa, `TabView` mostra o painel, e os dois compartilham o
  handler.
* Um `Text` de resumo ao lado do formulário é o jeito mais rápido de provar que a
  ligação bidirecional funciona — é o que o exemplo
  [Booking form](../examples/booking-form.md) faz.
