# Tutorial — o Counter

Bem-vindo! 👋 Neste tutorial você constrói o **counter**, o app canônico do
tempestweb, do zero. É um botão `+`, um botão `-` e um texto que mostra a
contagem. Simples — mas ele exercita **todo o contrato de fronteira**: árvore de
view, estado, handlers, patches e os três modos de execução.

Vamos um conceito por página, na ordem:

<div class="grid cards" markdown>

-   __[1. A árvore de view](view.md)__

    ---

    Como escrever `view()` e montar widgets tipados (`Column`, `Row`, `Text`,
    `Button`).

-   __[2. Estado e handlers](state.md)__

    ---

    `set_state`, o rebuild coalescido, e por que handlers nunca tocam o DOM.

-   __[3. Patches na rede](patches.md)__

    ---

    O que o reconciliador emite quando a contagem muda — e como o cliente aplica.

-   __[4. Rodando os modos](modes.md)__

    ---

    O mesmo `app.py` sob `--mode wasm`, `--mode server` e `--mode transpile`, sem
    mudar uma linha.

</div>

!!! tip "Pré-requisito"
    Você só precisa ter feito a [Instalação](../installation.md). Cada página
    assume apenas a anterior — comece pela página 1 e siga em frente.

!!! note "Quer só rodar, não digitar?"
    O `tempestweb new <nome>` já scaffolda exatamente este counter (com
    `tempestweb.toml`) num projeto rodável — veja
    [Criar seu primeiro projeto](../installation.md#criar-seu-primeiro-projeto).
    Este tutorial reconstrói o mesmo app do zero para explicar cada peça.

## O que vamos construir

Ao final, este é o app completo — exatamente o que vive em
[`examples/counter/app.py`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/counter/app.py):

```python
"""Counter — the canonical tempestweb example."""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Button, Column, Row, Style, Text, Widget
from tempest_core.style import Edge


@dataclass
class CounterState:
    """State for the counter app."""

    value: int = 0


def make_state() -> CounterState:
    """Build the initial state."""
    return CounterState()


def view(app: App[CounterState]) -> Widget:
    """Render the counter UI from the current state."""

    def increment() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value + 1))

    def decrement() -> None:
        app.set_state(lambda s: setattr(s, "value", s.value - 1))

    return Column(
        style=Style(gap=8.0, padding=Edge.all(16)),
        children=[
            Text(content=f"Count: {app.state.value}", key="label"),
            Row(
                style=Style(gap=4.0),
                children=[
                    Button(label="-", on_click=decrement, key="dec"),
                    Button(label="+", on_click=increment, key="inc"),
                ],
            ),
        ],
    )
```

!!! check "Tudo que você precisa saber está aqui"
    Não há mágica escondida. As quatro páginas a seguir explicam cada linha
    acima, peça por peça. Vamos começar pela [árvore de view](view.md). 🚀
