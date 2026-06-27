# Onboarding Carousel — Navegação por Páginas 🚀

Construa um fluxo de boas-vindas de três slides com `PageView`, indicador de dots, botões Skip/Next/Get started e uma tela de conclusão — tudo em Python puro e tipado.

---

## O que você vai construir

Um carrossel de onboarding clássico com:

- 📄 **Três slides** de introdução, cada um com ícone, título e descrição
- 🔵 **Indicador de dots** centralizado que reflete a página ativa
- ⏩ Botão **Skip** que pula direto para o último slide
- ➡ Botão **Next →** que avança uma página por vez
- ✅ Botão **Get started** (aparece só no último slide) que conclui o fluxo
- 🎉 **Tela de conclusão** exibida assim que o usuário finaliza o onboarding

!!! note "Nota — dois inputs de navegação"
    A página pode mudar de duas formas: pelo **swipe** do usuário (emitido pelo `PageView` via `PageChangeEvent`) ou pelo **clique nos botões**. Ambos atualizam o mesmo campo `page` no estado — o widget tree sempre reflete uma única fonte de verdade.

---

## Pré-requisitos

Certifique-se de ter o tempestweb instalado:

```bash
pip install tempestweb
```

Leia antes (opcional, mas recomendado):

- [Tutorial básico](../tutorial/index.md) — primeiros passos com `App`, `view` e `set_state`
- [Gerenciando estado](../tutorial/state.md) — como `set_state` funciona
- [Modos de execução](../tutorial/modes.md) — WASM vs. servidor

---

## Criando o projeto

Crie a pasta e o arquivo do app:

```bash
mkdir -p examples/onboarding-carousel
touch examples/onboarding-carousel/app.py
```

---

## Passo 1 — Definindo os dados dos slides

Antes de qualquer UI, defina o conteúdo dos slides em uma lista de dicionários. Isso mantém o conteúdo separado da lógica de apresentação:

```python
from __future__ import annotations

_SLIDES: list[dict[str, str]] = [
    {
        "icon": "🚀",
        "title": "Welcome to TempestWeb",
        "body": (
            "Build rich web apps in plain, typed Python. "
            "Write once — deploy as WASM in the browser or "
            "as a server-side stream over WebSocket."
        ),
    },
    {
        "icon": "🌊",
        "title": "One tree, two modes",
        "body": (
            "Your view function returns a widget tree that never names a "
            "transport.  The framework picks the mode; your code stays clean, "
            "diffable and fully type-checked."
        ),
    },
    {
        "icon": "⚡",
        "title": "Ready to ship",
        "body": (
            "Hot-reload in dev, static WASM bundle or FastAPI server in "
            "production.  Add push notifications, offline support and native "
            "device features with zero extra boilerplate."
        ),
    },
]

_TOTAL: int = len(_SLIDES)
```

!!! tip "Dica — extraia dados da UI"
    Manter os textos em `_SLIDES` (fora de `view`) facilita a tradução, testes e futura busca de conteúdo em uma API. A função `view` não precisa saber _o que_ está escrito — apenas _quantos_ slides existem e _qual_ está ativo.

---

## Passo 2 — Definindo o estado

O estado do carrossel precisa guardar apenas duas coisas:

| Campo | Tipo | Significado |
|---|---|---|
| `page` | `int` | Índice da página ativa (base 0) |
| `done` | `bool` | Usuário concluiu o onboarding? |

```python
from dataclasses import dataclass


@dataclass
class OnboardingState:
    """Mutable state for the onboarding carousel.

    Attributes:
        page: Active page index (0-based, 0 ≤ page < _TOTAL).
        done: Whether the user has completed the onboarding flow.
    """

    page: int = 0
    done: bool = False


def make_state() -> OnboardingState:
    """Build the initial onboarding state.

    Returns:
        A fresh :class:`OnboardingState` positioned on the first slide.
    """
    return OnboardingState()
```

!!! info "Nota — `done` não é derivado de `page`"
    Você pode se perguntar: "por que ter `done` se posso verificar `page == _TOTAL - 1`?" A resposta é que estar no último slide não significa ter concluído — o usuário pode simplesmente estar lendo. O clique em **Get started** é o sinal explícito de conclusão, e esse momento precisa ser capturado em estado próprio.

---

## Passo 3 — Sub-builders: dot indicator e slide

Antes de montar a `view`, escreva dois helpers puros que constroem partes da UI. Isso mantém `view` legível.

### 3.1 — O indicador de dots

Recebe o índice ativo e o total de páginas; retorna uma `Row` de `Container` circulares. O dot ativo é maior e colorido com `ACCENT`; os demais ficam em cinza muted.

```python
from tempest_core import Button, Column, Row, Style, Widget
from tempest_core.components import ACCENT, BACKGROUND, ON_MUTED, ON_SURFACE, Card
from tempest_core.style import (
    AlignItems,
    Color,
    Edge,
    FontWeight,
    JustifyContent,
    TextAlign,
)
from tempest_core.widgets import Container, PageView, Text
from tempest_core.widgets.events import PageChangeEvent


def _dot_indicator(active: int, total: int) -> Widget:
    """Render a row of pagination dots.

    The active page's dot is highlighted in ``ACCENT`` and slightly larger;
    inactive dots are muted.

    Args:
        active: The currently active page index (0-based).
        total: The total number of pages.

    Returns:
        A ``Row`` of ``Container`` dots.
    """
    dots: list[Widget] = []
    for i in range(total):
        is_active: bool = i == active
        size: float = 10.0 if is_active else 8.0
        bg: Color = ACCENT if is_active else Color.from_hex("#4b5563")
        dots.append(
            Container(
                key=f"dot-{i}",
                style=Style(
                    width=size,
                    height=size,
                    radius=size / 2.0,
                    background=bg,
                    margin=Edge.symmetric(horizontal=4.0),
                ),
            )
        )
    return Row(
        key="dot-row",
        style=Style(justify=JustifyContent.CENTER, align=AlignItems.CENTER),
        children=dots,
    )
```

!!! tip "Dica — `radius=size / 2.0` para círculos perfeitos"
    Definir `radius` como metade da largura/altura transforma o `Container` retangular em um círculo perfeito. Isso é mais simples do que tentar aplicar `border-radius: 50%` via string — o sistema de estilo tipado cuida da conversão CSS automaticamente.

### 3.2 — Um slide

Cada slide é uma `Column` centrada com ícone, título e texto descritivo:

```python
def _slide(index: int) -> Widget:
    """Render one onboarding slide.

    Each slide contains a large emoji icon, a bold headline and a
    multi-line description, all centred on a dark surface card.

    Args:
        index: The slide index into :data:`_SLIDES`.

    Returns:
        A ``Column`` composing the slide content.
    """
    data: dict[str, str] = _SLIDES[index]
    return Column(
        key=f"slide-{index}",
        style=Style(
            align=AlignItems.CENTER,
            justify=JustifyContent.CENTER,
            padding=Edge.all(32.0),
            gap=24.0,
            background=BACKGROUND,
            min_height=380.0,
        ),
        children=[
            Text(
                content=data["icon"],
                key=f"slide-icon-{index}",
                style=Style(font_size=72.0, text_align=TextAlign.CENTER),
            ),
            Text(
                content=data["title"],
                key=f"slide-title-{index}",
                style=Style(
                    font_size=26.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_SURFACE,
                    text_align=TextAlign.CENTER,
                ),
            ),
            Text(
                content=data["body"],
                key=f"slide-body-{index}",
                style=Style(
                    font_size=15.0,
                    color=ON_MUTED,
                    text_align=TextAlign.CENTER,
                    line_height=1.6,
                    max_width=480.0,
                ),
            ),
        ],
    )
```

### 3.3 — A tela de conclusão

Quando o usuário clica em **Get started**, `state.done` vira `True` e o carrossel é substituído por este card de agradecimento:

```python
def _done_card() -> Widget:
    """Render the post-onboarding thank-you card.

    Displayed once the user taps ``Get started`` on the final slide,
    confirming that the onboarding flow has been completed.

    Returns:
        A centred ``Column`` with a success icon and confirmation text.
    """
    return Column(
        key="done-card",
        style=Style(
            align=AlignItems.CENTER,
            justify=JustifyContent.CENTER,
            padding=Edge.all(40.0),
            gap=20.0,
            min_height=380.0,
        ),
        children=[
            Text(
                content="✅",
                key="done-icon",
                style=Style(font_size=72.0, text_align=TextAlign.CENTER),
            ),
            Text(
                content="You're all set!",
                key="done-title",
                style=Style(
                    font_size=26.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_SURFACE,
                    text_align=TextAlign.CENTER,
                ),
            ),
            Text(
                content="Onboarding complete. Enjoy building with TempestWeb.",
                key="done-body",
                style=Style(
                    font_size=15.0,
                    color=ON_MUTED,
                    text_align=TextAlign.CENTER,
                    max_width=400.0,
                ),
            ),
            Card(
                key="start-card",
                children=[
                    Text(
                        content="Head over to the examples to see what's possible.",
                        key="start-hint",
                        style=Style(
                            font_size=14.0,
                            color=ON_MUTED,
                            text_align=TextAlign.CENTER,
                        ),
                    ),
                ],
            ),
        ],
    )
```

---

## Passo 4 — Os handlers de evento

Dentro de `view()`, definimos cinco funções que reagem às interações do usuário. Todas chamam `app.set_state(mutador)`:

```python
from tempest_core import App


def view(app: App[OnboardingState]) -> Widget:
    """Render the onboarding carousel from the current state."""
    state: OnboardingState = app.state
    is_last: bool = state.page == _TOTAL - 1

    def on_page_change(event: PageChangeEvent) -> None:
        """Synchronise state when the user swipes the PageView.

        Guards against feedback loops: if the emitted page already matches the
        state, the write is skipped.

        Args:
            event: The page-change event carrying the new page index.
        """
        if event.page == state.page:
            return
        app.set_state(lambda s: setattr(s, "page", event.page))

    def go_to_page(target: int) -> None:
        """Navigate to a specific slide index.

        Args:
            target: The destination page (clamped to 0 ≤ target < _TOTAL).
        """
        clamped: int = max(0, min(target, _TOTAL - 1))
        app.set_state(lambda s: setattr(s, "page", clamped))

    def on_skip() -> None:
        """Jump directly to the last slide when Skip is tapped."""
        go_to_page(_TOTAL - 1)

    def on_next() -> None:
        """Advance to the next slide, or mark onboarding done on the last slide."""
        if is_last:
            app.set_state(lambda s: setattr(s, "done", True))
        else:
            go_to_page(state.page + 1)
```

!!! warning "Aviso — guard contra feedback loops no `on_page_change`"
    O `PageView` pode emitir um `PageChangeEvent` mesmo quando a página já corresponde ao estado (por exemplo, após um snap de animação). Sem o guard `if event.page == state.page: return`, cada emit dispararia um `set_state` desnecessário, re-renderizando a árvore sem motivo. Sempre proteja handlers de eventos de posição assim.

---

## Passo 5 — Montando a `view` completa

Com os helpers e handlers prontos, a `view` principal só precisa orquestrar:

1. Verificar `state.done` e devolver a tela de conclusão se for o caso.
2. Construir a lista de slides.
3. Montar a linha de controles (Skip / dots / Next).
4. Compor tudo em uma `Column` raiz.

```python
    # --- Completion screen --------------------------------------------------

    if state.done:
        return Column(
            key="onboarding-root",
            style=Style(
                background=BACKGROUND,
                padding=Edge.symmetric(vertical=24.0, horizontal=16.0),
                gap=0.0,
            ),
            children=[_done_card()],
        )

    # --- Carousel + controls ------------------------------------------------

    slides: list[Widget] = [_slide(i) for i in range(_TOTAL)]

    controls: list[Widget] = [
        # Skip button — only shown when not on the last slide
        Button(
            label="Skip",
            on_click=on_skip,
            key="btn-skip",
            style=Style(color=ON_MUTED),
        )
        if not is_last
        else Container(key="skip-spacer", style=Style(width=60.0)),
        # Dot indicator in the centre
        _dot_indicator(active=state.page, total=_TOTAL),
        # Next / Get started
        Button(
            label="Get started" if is_last else "Next →",
            on_click=on_next,
            key="btn-next",
            style=Style(
                background=ACCENT,
                color=ON_SURFACE,
                padding=Edge.symmetric(vertical=10.0, horizontal=20.0),
                radius=8.0,
                font_weight=FontWeight.SEMIBOLD,
            ),
        ),
    ]

    return Column(
        key="onboarding-root",
        style=Style(
            background=BACKGROUND,
            padding=Edge.symmetric(vertical=24.0, horizontal=16.0),
            gap=24.0,
        ),
        children=[
            # Header label
            Text(
                content=f"Step {state.page + 1} of {_TOTAL}",
                key="step-label",
                style=Style(
                    font_size=12.0,
                    color=ON_MUTED,
                    text_align=TextAlign.CENTER,
                ),
            ),
            # Paged carousel
            PageView(
                key="onboarding-pager",
                page=state.page,
                on_page_change=on_page_change,
                children=slides,
            ),
            # Skip / dots / Next row
            Row(
                key="controls-row",
                style=Style(
                    justify=JustifyContent.SPACE_BETWEEN,
                    align=AlignItems.CENTER,
                    padding=Edge.symmetric(horizontal=8.0),
                ),
                children=controls,
            ),
        ],
    )
```

!!! tip "Dica — `Container` como espaçador"
    No último slide, o botão **Skip** precisa desaparecer, mas a `Row` com `JustifyContent.SPACE_BETWEEN` continua precisando de três filhos para manter o layout equilibrado. Usar um `Container(key="skip-spacer", style=Style(width=60.0))` no lugar do botão garante que os dots e o botão **Get started** permaneçam centralizados sem alterar a estrutura da árvore.

---

## O app completo

Aqui está o arquivo completo, pronto para copiar:

```python
"""Onboarding carousel — paged navigation demo.

A multi-step onboarding flow built with :class:`~tempest_core.widgets.PageView`.
Three full-width slides walk the user through a product introduction; a dot
indicator below the pager tracks the active page, and ``Skip`` / ``Next``
buttons (replaced by a ``Get started`` button on the last slide) let the user
navigate without swiping.

Demonstrates:

* :class:`~tempest_core.widgets.PageView` driven by ``page`` state.
* :class:`~tempest_core.widgets.events.PageChangeEvent` — fired when the
  user swipes; the handler ignores events that would land on the current page to
  break feedback loops.
* Dot-indicator pattern: three ``Container`` widgets styled conditionally on the
  active-page index.
* ``Skip`` button that jumps straight to the last slide.
* ``Next`` / ``Get started`` buttons that advance the page or conclude the flow,
  with the conclusion reflected in a thank-you card.

Run unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)
"""

from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Button, Column, Row, Style, Widget
from tempest_core.components import ACCENT, BACKGROUND, ON_MUTED, ON_SURFACE, Card
from tempest_core.style import (
    AlignItems,
    Color,
    Edge,
    FontWeight,
    JustifyContent,
    TextAlign,
)
from tempest_core.widgets import Container, PageView, Text
from tempest_core.widgets.events import PageChangeEvent

# ---------------------------------------------------------------------------
# Slide data
# ---------------------------------------------------------------------------

_SLIDES: list[dict[str, str]] = [
    {
        "icon": "🚀",
        "title": "Welcome to TempestWeb",
        "body": (
            "Build rich web apps in plain, typed Python. "
            "Write once — deploy as WASM in the browser or "
            "as a server-side stream over WebSocket."
        ),
    },
    {
        "icon": "🌊",
        "title": "One tree, two modes",
        "body": (
            "Your view function returns a widget tree that never names a "
            "transport.  The framework picks the mode; your code stays clean, "
            "diffable and fully type-checked."
        ),
    },
    {
        "icon": "⚡",
        "title": "Ready to ship",
        "body": (
            "Hot-reload in dev, static WASM bundle or FastAPI server in "
            "production.  Add push notifications, offline support and native "
            "device features with zero extra boilerplate."
        ),
    },
]

_TOTAL: int = len(_SLIDES)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class OnboardingState:
    """Mutable state for the onboarding carousel.

    Attributes:
        page: Active page index (0-based, 0 ≤ page < _TOTAL).
        done: Whether the user has completed the onboarding flow.
    """

    page: int = 0
    done: bool = False


def make_state() -> OnboardingState:
    """Build the initial onboarding state.

    Returns:
        A fresh :class:`OnboardingState` positioned on the first slide.
    """
    return OnboardingState()


# ---------------------------------------------------------------------------
# Sub-builders
# ---------------------------------------------------------------------------


def _dot_indicator(active: int, total: int) -> Widget:
    """Render a row of pagination dots.

    The active page's dot is highlighted in ``ACCENT`` and slightly larger;
    inactive dots are muted.

    Args:
        active: The currently active page index (0-based).
        total: The total number of pages.

    Returns:
        A ``Row`` of ``Container`` dots.
    """
    dots: list[Widget] = []
    for i in range(total):
        is_active: bool = i == active
        size: float = 10.0 if is_active else 8.0
        bg: Color = ACCENT if is_active else Color.from_hex("#4b5563")
        dots.append(
            Container(
                key=f"dot-{i}",
                style=Style(
                    width=size,
                    height=size,
                    radius=size / 2.0,
                    background=bg,
                    margin=Edge.symmetric(horizontal=4.0),
                ),
            )
        )
    return Row(
        key="dot-row",
        style=Style(justify=JustifyContent.CENTER, align=AlignItems.CENTER),
        children=dots,
    )


def _slide(index: int) -> Widget:
    """Render one onboarding slide.

    Each slide contains a large emoji icon, a bold headline and a
    multi-line description, all centred on a dark surface card.

    Args:
        index: The slide index into :data:`_SLIDES`.

    Returns:
        A ``Column`` composing the slide content.
    """
    data: dict[str, str] = _SLIDES[index]
    return Column(
        key=f"slide-{index}",
        style=Style(
            align=AlignItems.CENTER,
            justify=JustifyContent.CENTER,
            padding=Edge.all(32.0),
            gap=24.0,
            background=BACKGROUND,
            min_height=380.0,
        ),
        children=[
            Text(
                content=data["icon"],
                key=f"slide-icon-{index}",
                style=Style(font_size=72.0, text_align=TextAlign.CENTER),
            ),
            Text(
                content=data["title"],
                key=f"slide-title-{index}",
                style=Style(
                    font_size=26.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_SURFACE,
                    text_align=TextAlign.CENTER,
                ),
            ),
            Text(
                content=data["body"],
                key=f"slide-body-{index}",
                style=Style(
                    font_size=15.0,
                    color=ON_MUTED,
                    text_align=TextAlign.CENTER,
                    line_height=1.6,
                    max_width=480.0,
                ),
            ),
        ],
    )


def _done_card() -> Widget:
    """Render the post-onboarding thank-you card.

    Displayed once the user taps ``Get started`` on the final slide,
    confirming that the onboarding flow has been completed.

    Returns:
        A centred ``Column`` with a success icon and confirmation text.
    """
    return Column(
        key="done-card",
        style=Style(
            align=AlignItems.CENTER,
            justify=JustifyContent.CENTER,
            padding=Edge.all(40.0),
            gap=20.0,
            min_height=380.0,
        ),
        children=[
            Text(
                content="✅",
                key="done-icon",
                style=Style(font_size=72.0, text_align=TextAlign.CENTER),
            ),
            Text(
                content="You're all set!",
                key="done-title",
                style=Style(
                    font_size=26.0,
                    font_weight=FontWeight.BOLD,
                    color=ON_SURFACE,
                    text_align=TextAlign.CENTER,
                ),
            ),
            Text(
                content="Onboarding complete. Enjoy building with TempestWeb.",
                key="done-body",
                style=Style(
                    font_size=15.0,
                    color=ON_MUTED,
                    text_align=TextAlign.CENTER,
                    max_width=400.0,
                ),
            ),
            Card(
                key="start-card",
                children=[
                    Text(
                        content="Head over to the examples to see what's possible.",
                        key="start-hint",
                        style=Style(
                            font_size=14.0,
                            color=ON_MUTED,
                            text_align=TextAlign.CENTER,
                        ),
                    ),
                ],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# view
# ---------------------------------------------------------------------------


def view(app: App[OnboardingState]) -> Widget:
    """Render the onboarding carousel from the current state.

    The active page index lives in ``app.state.page`` and is updated both by
    the ``PageView``'s ``on_page_change`` handler (swipe gesture) and by the
    ``Skip`` / ``Next`` / ``Get started`` buttons.

    When ``app.state.done`` is ``True``, the ``PageView`` is replaced by a
    completion card so the user sees clear feedback that onboarding finished.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """
    state: OnboardingState = app.state
    is_last: bool = state.page == _TOTAL - 1

    # --- Handlers -----------------------------------------------------------

    def on_page_change(event: PageChangeEvent) -> None:
        """Synchronise state when the user swipes the PageView.

        Guards against feedback loops: if the emitted page already matches the
        state, the write is skipped.

        Args:
            event: The page-change event carrying the new page index.
        """
        if event.page == state.page:
            return
        app.set_state(lambda s: setattr(s, "page", event.page))

    def go_to_page(target: int) -> None:
        """Navigate to a specific slide index.

        Args:
            target: The destination page (clamped to 0 ≤ target < _TOTAL).
        """
        clamped: int = max(0, min(target, _TOTAL - 1))
        app.set_state(lambda s: setattr(s, "page", clamped))

    def on_skip() -> None:
        """Jump directly to the last slide when Skip is tapped."""
        go_to_page(_TOTAL - 1)

    def on_next() -> None:
        """Advance to the next slide, or mark onboarding done on the last slide."""
        if is_last:
            app.set_state(lambda s: setattr(s, "done", True))
        else:
            go_to_page(state.page + 1)

    # --- Completion screen --------------------------------------------------

    if state.done:
        return Column(
            key="onboarding-root",
            style=Style(
                background=BACKGROUND,
                padding=Edge.symmetric(vertical=24.0, horizontal=16.0),
                gap=0.0,
            ),
            children=[_done_card()],
        )

    # --- Carousel + controls ------------------------------------------------

    slides: list[Widget] = [_slide(i) for i in range(_TOTAL)]

    controls: list[Widget] = [
        # Skip button — only shown when not on the last slide
        Button(
            label="Skip",
            on_click=on_skip,
            key="btn-skip",
            style=Style(color=ON_MUTED),
        )
        if not is_last
        else Container(key="skip-spacer", style=Style(width=60.0)),
        # Dot indicator in the centre
        _dot_indicator(active=state.page, total=_TOTAL),
        # Next / Get started
        Button(
            label="Get started" if is_last else "Next →",
            on_click=on_next,
            key="btn-next",
            style=Style(
                background=ACCENT,
                color=ON_SURFACE,
                padding=Edge.symmetric(vertical=10.0, horizontal=20.0),
                radius=8.0,
                font_weight=FontWeight.SEMIBOLD,
            ),
        ),
    ]

    return Column(
        key="onboarding-root",
        style=Style(
            background=BACKGROUND,
            padding=Edge.symmetric(vertical=24.0, horizontal=16.0),
            gap=24.0,
        ),
        children=[
            # Header label
            Text(
                content=f"Step {state.page + 1} of {_TOTAL}",
                key="step-label",
                style=Style(
                    font_size=12.0,
                    color=ON_MUTED,
                    text_align=TextAlign.CENTER,
                ),
            ),
            # Paged carousel
            PageView(
                key="onboarding-pager",
                page=state.page,
                on_page_change=on_page_change,
                children=slides,
            ),
            # Skip / dots / Next row
            Row(
                key="controls-row",
                style=Style(
                    justify=JustifyContent.SPACE_BETWEEN,
                    align=AlignItems.CENTER,
                    padding=Edge.symmetric(horizontal=8.0),
                ),
                children=controls,
            ),
        ],
    )
```

---

## Rodando o exemplo ▶

### Modo A — Python no browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm examples/onboarding-carousel/app.py
```

O Python roda **dentro do browser** via Pyodide. Nenhum servidor necessário.

### Modo B — Python no servidor (FastAPI + WebSocket)

```bash
tempestweb dev --mode server examples/onboarding-carousel/app.py
```

O Python roda no servidor; o browser recebe patches JSON pelo WebSocket e aplica ao DOM.

!!! check "Verificação"
    Em qualquer modo, você deve ver:

    1. Label **"Step 1 of 3"** no topo
    2. Slide 1 com ícone 🚀, título e descrição
    3. Linha de controles: **Skip** à esquerda, três dots no centro, **Next →** à direita
    4. Clique **Next →** → slide avança, label muda para "Step 2 of 3", dot central acende
    5. Clique **Skip** em qualquer slide antes do último → pula para o slide 3, botão vira **Get started**
    6. No slide 3, o botão **Skip** desaparece (substituído por espaçador transparente)
    7. Clique **Get started** → carrossel é substituído pela tela ✅ "You're all set!"

---

## Verificação automatizada ✅

Rode os quatro checks antes de commitar:

```bash
# Lint
ruff check .

# Formatação
ruff format --check .

# Tipos
mypy --strict tempestweb

# Testes
pytest -q
```

Todos devem passar em verde. O exemplo foi projetado para ser `mypy --strict` clean — toda variável, parâmetro e retorno está anotado explicitamente.

---

## Como funciona por dentro

### O ciclo de atualização

```
Swipe ou clique no botão
         │
         ▼
handler (on_page_change / on_skip / on_next)
         │
         ▼
app.set_state(lambda s: setattr(s, "page", novo_valor))
         │
         ▼
tempestweb aplica o mutador → novo estado
         │
         ▼
view(app) chamada novamente → nova árvore de widgets
         │
         ▼
reconciliador calcula diff (patches mínimos)
         │
         ▼
DOM atualizado — apenas os nós que mudaram
```

### `PageView` e duas fontes de navegação

O `PageView` expõe `page=` (fonte de verdade vindo do estado Python) e `on_page_change=` (callback para quando o usuário desliza). Essa separação garante que o Python _sempre_ controla qual página está ativa:

- Botão clicado → handler chama `go_to_page` → `set_state` → re-render → `PageView` recebe novo `page=`
- Usuário desliza → `PageView` emite `PageChangeEvent` → `on_page_change` chama `set_state` → re-render confirma a posição

As duas rotas convergem para o mesmo `state.page`. Nunca há estado "local" no `PageView` que possa divergir do Python.

### Por que `key` importa aqui

O reconciliador usa `key` para identificar nós entre renders. Os slides têm `key=f"slide-{index}"` e os dots têm `key=f"dot-{i}"`. Isso garante que ao trocar de página, apenas o conteúdo que realmente mudou (o background do dot, o slide visível) recebe patches — não uma remontagem completa da árvore.

---

## Recapitulando

Neste tutorial você aprendeu:

- ✅ Usar **`PageView`** com a prop `page=` para navegação controlada pelo estado
- ✅ Tratar **`PageChangeEvent`** com guard anti-feedback-loop
- ✅ Construir um **dot indicator** dinamicamente com `Container` circulares
- ✅ Alternar o label do botão entre **"Next →"** e **"Get started"** baseado em `is_last`
- ✅ Usar um **`Container` espaçador** para manter layout estável quando um botão some
- ✅ Modelar **estado de conclusão** (`done: bool`) separado da posição (`page: int`)
- ✅ Extrair sub-builders (`_slide`, `_dot_indicator`, `_done_card`) para manter `view` legível

---

## Próximos passos

Experimente estender o exemplo:

- 💡 Adicione animação de transição entre slides usando o módulo de animações do `_core`
- 💡 Persista o campo `done` em `localStorage` via a API de storage do Modo A para não exibir o onboarding novamente
- 💡 Adicione um quarto slide com um formulário de cadastro — veja o exemplo [BR Cadastro](./br-cadastro.md)
- 💡 Explore o [Signup Wizard](./signup-wizard.md) para um fluxo paginado com validação de etapa
- 💡 Veja o [Tutorial básico](../tutorial/index.md) para entender melhor o ciclo `view` → `set_state`
