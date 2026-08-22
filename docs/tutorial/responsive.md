# Layout responsivo

O browser é dono do viewport; sua `view` é dona da árvore. O ponto de encontro é
`app.media`: uma foto do viewport que o cliente reporta no mount e a cada resize,
mudança de orientação ou de preferência de tema do sistema.

Como o `view` roda de novo a cada mudança, **um `if` já é responsividade**. Não
existe media query para escrever, nem CSS para manter. 🚀

## A foto do viewport

`app.media` é um `MediaQueryData` com seis campos:

| Campo | O que é |
| --- | --- |
| `width` · `height` | tamanho do viewport em px CSS |
| `device_pixel_ratio` | densidade da tela (1 num monitor comum, 2–3 num celular) |
| `orientation` | `"portrait"` ou `"landscape"` |
| `platform_dark_mode` | se o sistema pede tema escuro |
| `text_scale_factor` | escala de texto pedida pelo usuário (1.0 no browser) |

```python
from tempest_core import App, Column, Row, Style, Text, Widget

BREAKPOINT = 700.0


def view(app: App[None]) -> Widget:
    """Render a row on a wide viewport and a column on a narrow one."""
    cards: list[Widget] = [
        Text(content="Requests", key="a"),
        Text(content="Errors", key="b"),
    ]
    if app.media.width >= BREAKPOINT:
        return Row(key="cards", style=Style(gap=12.0), children=cards)
    return Column(key="cards", style=Style(gap=12.0), children=cards)
```

Abra num monitor e estreite a janela: a árvore troca de `Row` para `Column`, e o
reconciliador transforma isso na sequência mínima de patches — os cards não são
reconstruídos, só remontados.

!!! tip "Escolha o breakpoint pelo conteúdo, não pelo aparelho"
    `700.0` acima não é "celular"; é "abaixo disso os três cards ficam estreitos
    demais". Uma constante nomeada no módulo, comparada com `media.width`, é toda
    a infraestrutura de que você precisa.

## Frames com altura de viewport

`Style` não tem `100vh`. Quando você precisa que algo ocupe a tela inteira — o
caso clássico é um `Scaffold(scroll=True)`, cuja `app_bar` e `bottom_bar` só ficam
paradas se a coluna em volta tiver altura limitada — o limite vem de
`media.height`:

```python
from tempest_core import Style
from tempest_core.presets import Scaffold


def view(app: App[None]) -> Widget:
    """Render a scaffold bounded by the viewport, so its bars do not scroll away."""
    return Scaffold(
        key="screen",
        style=Style(height=app.media.height),
        scroll=True,
        app_bar=...,
        bottom_bar=...,
        body=...,
    )
```

!!! warning "Sem `media`, isso vira uma página de 4000px"
    Sem uma altura, a coluna cresce com o conteúdo, o `ScrollView` nunca rola e a
    barra de ações fica no fim do documento — longe do dedo do usuário. Era
    exatamente o sintoma que o Modo B tinha antes de `app.media` ser atualizado
    lá (issue #74).

## Tema do sistema

`platform_dark_mode` chega na mesma foto, então um app pode seguir a preferência
do sistema sem escrever CSS:

```python
from tempest_core import Theme, ThemeMode


def view(app: App[None]) -> Widget:
    """Pick the palette the OS asked for."""
    mode = ThemeMode.DARK if app.media.platform_dark_mode else ThemeMode.LIGHT
    theme = Theme.from_seed(seed=..., mode=mode)
    ...
```

## Como isso chega até você

??? info "Detalhes técnicos: o evento `media`"
    `client/media.js` lê o viewport e envia
    `{"type": "media", "key": "", "payload": {...}}` no mount e em cada `resize`
    ou mudança de `prefers-color-scheme`. O `mount()` compartilhado o instala, então
    os três modos reportam.

    Do outro lado, o evento é tratado **antes** da resolução de handler (como o
    `navigate`): no Modo C pelo runtime JS, e nos Modos A e B por `apply_media`,
    que valida o payload num `MediaQueryData` e chama `App._update_media` — o
    mesmo método que a docstring do core sempre prometeu que um renderizador
    chamaria.

    A chave é vazia de propósito: `media` é um evento do app, não de um widget.
    Um campo ausente mantém o default e um payload malformado é ignorado, porque
    um resize estranho não pode derrubar o loop de eventos.

## Recap

* `app.media` é a foto do viewport, atualizada no mount e a cada resize —
  idêntica nos três modos.
* Layout responsivo é um `if` na `view`; nenhuma media query, nenhum CSS.
* `media.height` é o único limite de altura disponível para um frame que precisa
  caber na tela.
* `platform_dark_mode` deixa o app seguir o tema do sistema.

O exemplo completo, que imprime a foto ao vivo e troca de layout no breakpoint,
está em
[`examples/responsive_demo/app.py`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/responsive_demo/app.py):

```bash
tempestweb run --mode server --path examples/responsive_demo
```
