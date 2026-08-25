# Dark Mode — O Tema Chega ao Widget 🌙

Um app pequeno com **Card**, **Badge**, **Input**, **Button** e **Alert**, todos
resolvendo cor do tema que você passa — e dois botões que trocam o tema em
runtime.

---

## O que você vai construir

Uma tela em que **cada widget estilizado recebe `theme=app.theme`**. Clicar em
"Dark" chama `app.set_theme(...)`, a árvore é reconstruída, e cada widget
re-resolve a própria paleta.

!!! tip "É uma linha, e é a linha que importa"
    ```python
    Button(label="Salvar", theme=app.theme, on_click=salvar)
    ```
    Sem o `theme=`, o widget resolve a paleta clara — mesmo com o app em modo
    escuro. O tema não é ambiente: ele é campo do widget.

---

## Pré-requisitos

```bash
pip install tempestweb
```

Leitura recomendada: [Tema (Material 3)](../tutorial/theming.md), em especial a
seção **Modo escuro: passe o tema ao widget**.

---

## O estado e a troca de tema

```python
from dataclasses import dataclass

from tempest_core import App, Theme, ThemeMode


@dataclass
class DarkModeState:
    """O que a tela guarda.

    Attributes:
        dark: Se o leitor pediu o tema escuro.
        draft: O texto digitado no campo de exemplo.
    """

    dark: bool = False
    draft: str = ""


def make_state() -> DarkModeState:
    """Estado inicial: claro, com o campo vazio."""
    return DarkModeState()


def choose(app: App[DarkModeState], dark: bool = False) -> None:
    """Troca o tema do app, o que re-resolve todo widget abaixo.

    Args:
        app: O handle da aplicação.
        dark: Se deve passar para o tema escuro.
    """
    app.set_state(lambda state: setattr(state, "dark", dark))
    app.set_theme(Theme(mode=ThemeMode.DARK if dark else ThemeMode.LIGHT))
```

---

## A árvore

Todo widget **estilizado** recebe o tema; `Row`, `Column` e `Text` não recebem
porque o core não lhes dá o campo — a cor deles é herdada da caixa em volta.

```python
from tempest_core import Alert, Badge, Button, Card, Column, Input, Row, Style, Text, Widget


def view(app: App[DarkModeState]) -> Widget:
    """Desenha a árvore de exemplo, cada widget resolvendo de ``app.theme``."""
    theme = app.theme
    return Column(
        key="dark-body",
        children=[
            Row(
                key="mode-row",
                children=[
                    Text(content="Dark mode", key="mode-label"),
                    Button(key="mode-light", label="Light", theme=theme,
                           variant="outline" if app.state.dark else "solid",
                           on_click=lambda: choose(app, False)),
                    Button(key="mode-dark", label="Dark", theme=theme,
                           variant="solid" if app.state.dark else "outline",
                           on_click=lambda: choose(app, True)),
                ],
            ),
            Card(
                key="sample-card",
                theme=theme,
                children=[
                    Badge(key="sample-badge", label="new", theme=theme),
                    Input(key="sample-input", value=app.state.draft, theme=theme,
                          placeholder="Type here", on_change=lambda e: None),
                    Button(key="sample-button", label="Save", theme=theme,
                           on_click=lambda: None),
                ],
            ),
            Alert(key="sample-alert", theme=theme,
                  title="Every colour above came from the theme"),
        ],
    )
```

---

## Rodando

```bash
tempestweb run --mode server --path examples/dark-mode --port 8000
tempestweb run --mode wasm   --path examples/dark-mode --port 8000
tempestweb build --mode transpile --path examples/dark-mode
```

Medido nos Modos B e C, com os **mesmos** valores computados nos dois — que são
os que o core resolve:

| widget | claro | escuro |
| --- | --- | --- |
| `Button` | `rgb(88, 71, 133)` | `rgb(199, 193, 215)` |
| `Card` | `rgb(252, 252, 252)` | `rgb(25, 25, 26)` |
| `Alert` | `rgb(219, 226, 240)` | `rgb(29, 59, 124)` |

!!! warning "O que ainda fica claro"
    O fundo do `Input` e o fundo da página vêm da **folha base**, cujos tokens
    `--tw-*` não têm eixo de modo — então num app escuro o campo aparece branco.
    Rastreado em
    [#148](https://github.com/mauriciobenjamin700/tempestweb/issues/148).

---

## Recap

* O tema é **campo do widget**, não ambiente: `theme=app.theme` em cada widget
  estilizado.
* `app.set_theme(...)` reconstrói a árvore e cada widget re-resolve.
* Widget de layout (`Row`/`Column`/`Text`) não tem `theme` — e passar levanta erro.
* Modo C carrega os dois modos na tabela gerada desde a 0.99.0; antes, todo
  widget transpilado renderizava claro.
