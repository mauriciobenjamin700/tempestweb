# Booking Form — Pickers, Faixa de Preço e Anexo 🚀

Um formulário de reserva com **DatePicker**, **TimePicker**, **RangeSlider**,
**Dropdown** e **FilePicker** — os controles que dependem do widget nativo do
navegador — todos ligados a um único dataclass de estado.

---

## O que você vai construir

Três cartões e um resumo ao vivo:

| Cartão | Widgets | O que coleta |
|---|---|---|
| **When** | `DatePicker` + `TimePicker` | dia de partida e hora de embarque |
| **Fare window** | `RangeSlider` | faixa de preço aceitável (dois valores) |
| **Cabin & documents** | `Dropdown` + `FilePicker` | cabine escolhida e um documento anexo |
| **Live summary** | `Card` (leitura) | reflexo imediato de tudo acima |

Cada mudança re-renderiza o resumo. Se você escolher uma data e o resumo não
mudar, o evento não chegou — é o teste de fumaça mais rápido que existe.

!!! tip "Por que estes cinco controles juntos"
    Todos são controles que o navegador desenha melhor do que qualquer
    reimplementação: o calendário, o relógio, o seletor de arquivo. No celular,
    cada um abre o seletor nativo do sistema. Este exemplo existe para você
    exercitá-los de verdade, num browser real.

---

## Pré-requisitos

```bash
pip install tempestweb
```

Leitura recomendada antes de continuar:

- [Tutorial básico](../tutorial/index.md) — `App`, `view` e `set_state`
- [Controles](../tutorial/controls.md) — o mapa widget → elemento → evento

---

## O estado

Um dataclass com um campo por controle. Note o par `low`/`high` do
`RangeSlider` e o `cabin_index`, que é o índice que o `SelectEvent` reporta:

```python
from dataclasses import dataclass


@dataclass
class BookingState:
    """Tudo o que o formulário coleta.

    Attributes:
        departure: Dia de partida, no formato ISO que o input nativo usa.
        boarding: Hora de embarque, ``HH:MM``.
        fare_low: Extremo inferior da faixa de preço aceitável, em BRL.
        fare_high: Extremo superior da faixa, em BRL.
        cabin: Cabine escolhida.
        cabin_index: Posição dela na lista (o que um ``SelectEvent`` reporta).
        document: Nome do documento anexado, ou ``""`` quando não há.
    """

    departure: str = "2026-09-14"
    boarding: str = "07:30"
    fare_low: float = 400.0
    fare_high: float = 1800.0
    cabin: str = "Economy"
    cabin_index: int = 0
    document: str = ""


def make_state() -> BookingState:
    """Estado inicial, com uma viagem plausível pré-preenchida."""
    return BookingState()
```

---

## Data e hora

Os dois pickers recebem e devolvem **texto ISO** — o mesmo formato que o input
nativo usa, então não há conversão nenhuma no meio:

```python
from tempest_core import App, Card, DateChangeEvent, DatePicker, TimeChangeEvent, TimePicker, Widget


def _when_card(app: App[BookingState]) -> Widget:
    """Cartão da data de partida e da hora de embarque."""

    def on_departure(event: DateChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "departure", event.value))

    def on_boarding(event: TimeChangeEvent) -> None:
        app.set_state(lambda s: setattr(s, "boarding", event.value))

    return Card(
        key="when-card",
        children=[
            DatePicker(key="departure", label="Departure", value=app.state.departure, on_change=on_departure),
            TimePicker(key="boarding", label="Boarding", value=app.state.boarding, on_change=on_boarding),
        ],
    )
```

!!! note "A legenda vem antes do controle"
    O `label` do picker é a legenda visível, e ela nomeia o campo para o leitor
    de tela nativamente (o controle mora dentro de um `<label>`). Em tela estreita
    a legenda quebra para a linha de cima em vez de empurrar a página.

---

## A faixa de preço

Um `RangeSlider` tem **dois** valores, e o evento traz os dois de uma vez —
sempre normalizados, com `low <= high`, mesmo que você arraste um polegar para
além do outro:

```python
from tempest_core import App, Card, RangeChangeEvent, RangeSlider, Text, Widget


def _fare_card(app: App[BookingState]) -> Widget:
    """Cartão da faixa de preço, com leitura ao vivo."""

    def on_fare(event: RangeChangeEvent) -> None:
        def apply(state: BookingState) -> None:
            state.fare_low = event.low
            state.fare_high = event.high

        app.set_state(apply)

    return Card(
        key="fare-card",
        children=[
            Text(key="fare-reading", content=f"R$ {app.state.fare_low:.0f} — R$ {app.state.fare_high:.0f}"),
            RangeSlider(
                key="fare",
                low=app.state.fare_low,
                high=app.state.fare_high,
                min_value=0.0,
                max_value=4000.0,
                step=50.0,
                on_change=on_fare,
            ),
        ],
    )
```

---

## Cabine e anexo

`Dropdown` e `FilePicker` são os dois controles que reportam **`on_select`**, não
`on_change`: escolher não é editar um valor:

```python
from tempest_core import App, Card, Dropdown, FilePicker, FileSelectEvent, SelectEvent, Widget

_CABINS: list[str] = ["Economy", "Premium", "Business", "First"]


def _cabin_card(app: App[BookingState]) -> Widget:
    """Cartão da cabine e do documento."""

    def on_cabin(event: SelectEvent) -> None:
        def apply(state: BookingState) -> None:
            state.cabin = event.value
            state.cabin_index = event.index

        app.set_state(apply)

    def on_document(event: FileSelectEvent) -> None:
        app.set_state(lambda s: setattr(s, "document", event.name or ""))

    return Card(
        key="cabin-card",
        children=[
            Dropdown(
                key="cabin",
                options=_CABINS,
                value=app.state.cabin,
                placeholder="Choose a cabin",
                on_select=on_cabin,
            ),
            FilePicker(key="document", label="Attach ID", value=app.state.document, on_select=on_document),
        ],
    )
```

!!! warning "O `placeholder` não desloca o índice"
    O `placeholder` do `Dropdown` é uma `<option>` desabilitada na frente da
    lista, mas o `event.index` conta só as opções reais: escolher `"Business"` na
    lista acima reporta `index=2`, não `3`.

---

## Rodando

```bash
tempestweb run --mode server --path examples/booking-form --port 8000   # Python no servidor
tempestweb run --mode wasm   --path examples/booking-form --port 8000   # Python no browser
tempestweb build --mode transpile --path examples/booking-form          # bundle JS estático
```

Os três servem o mesmo `app.py`. No Modo C não há Python nenhum rodando e os
cinco controles continuam atualizando o estado.

---

## Recap

* `DatePicker`/`TimePicker` trocam **texto ISO** com o controle nativo — sem
  conversão.
* `RangeSlider` reporta o par `low`/`high` normalizado, num evento só.
* `Dropdown` e `FilePicker` reportam **`on_select`**; o índice do `Dropdown`
  ignora o `placeholder`.
* O `value` de um `FilePicker` é exibido, nunca atribuído — nenhuma página pode
  escolher um arquivo pelo usuário.
* Um cartão de resumo ao vivo prova a ligação bidirecional melhor que qualquer
  print.

Continue pelo [Settings panel](settings-panel.md), que faz o mesmo com `Switch`,
`Checkbox` e `Slider`, e pela página de [Controles](../tutorial/controls.md).
