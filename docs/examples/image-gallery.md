# Galeria de Imagens com Lightbox 🚀

Construa uma galeria virtualizada de 12 fotos onde tocar em qualquer miniatura abre um lightbox Dialog com a imagem em alta resolução, legenda, crédito e navegação Anterior / Próximo / Fechar — **tudo em Python puro**.

---

## O que você vai construir

Uma galeria escura com:

- 🖼 Grade 3 colunas renderizada pelo **`LazyGrid`** (virtualização automática)
- 👆 Cada miniatura é um **`GestureDetector`** que abre o lightbox ao toque
- 💬 **`Dialog`** lightbox com imagem full-res, legenda, autor e 4 botões de navegação
- ↔ Navegação circular (Anterior/Próximo com wrap-around)
- 🔢 Contador `1 / 12` centralizado entre os botões

!!! note "Nota — um estado, dois modos"
    O campo `selected: int | None` é a única peça de estado. `None` = galeria aberta; um índice = lightbox aberto. O tempestweb roda esse mesmo código sem alteração no Modo A (WASM/Pyodide) e no Modo B (servidor + WebSocket).

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

```bash
mkdir -p examples/image-gallery
touch examples/image-gallery/app.py
```

---

## Passo 1 — Modelando os dados

Antes de qualquer UI, pensamos nos dados. Cada foto tem quatro atributos:

```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GalleryImage:
    """A single gallery entry.

    Attributes:
        src: URL of the full-resolution image.
        thumb: URL of the thumbnail image (lower resolution).
        caption: Short descriptive caption shown in the lightbox.
        author: Photographer / attribution credit.
    """

    src: str
    thumb: str
    caption: str
    author: str
```

Dois URLs separados — `thumb` para a grade (400×300 px) e `src` para o lightbox (1200×800 px) — evitam baixar imagens pesadas até que o usuário clique.

!!! tip "Dica — picsum.photos"
    O exemplo usa `https://picsum.photos/id/<N>/<largura>/<altura>` para servir imagens CC0 sem precisar de chaves de API. Qualquer URL pública funciona no lugar.

---

## Passo 2 — Definindo o estado

```python
@dataclass
class GalleryState:
    """Runtime state for the image gallery.

    Attributes:
        images: The full ordered list of gallery images.
        selected: Index of the image currently open in the lightbox,
            or ``None`` when the lightbox is closed.
    """

    images: list[GalleryImage] = field(default_factory=lambda: list(_IMAGES))
    selected: int | None = None


def make_state() -> GalleryState:
    """Build the initial gallery state.

    Returns:
        A fresh :class:`GalleryState` with all sample images and no selection.
    """
    return GalleryState()
```

!!! info "Nota — `int | None`"
    `selected` é `None` enquanto o lightbox está fechado e um inteiro (índice da foto) quando está aberto. Esse é o padrão **"UI state como valor opcional"** — simples, sem booleans extras.

---

## Passo 3 — Constantes de estilo

Centralizamos as cores em constantes nomeadas para não repetir valores numéricos por todo o código:

```python
from tempest_core.style import (
    AlignItems,
    Color,
    Edge,
    FontWeight,
    JustifyContent,
    Shadow,
    TextAlign,
)

_WHITE: Color = Color(r=255, g=255, b=255)
_DARK_BG: Color = Color(r=18, g=18, b=18)
_OVERLAY_BG: Color = Color(r=0, g=0, b=0, a=0.85)
_CAPTION_BG: Color = Color(r=30, g=30, b=30)
_ACCENT: Color = Color(r=99, g=179, b=237)
_MUTED: Color = Color(r=160, g=160, b=160)
_CARD_BG: Color = Color(r=38, g=38, b=38)

_CARD_SHADOW: Shadow = Shadow(
    color=Color(r=0, g=0, b=0, a=0.4),
    blur=12.0,
    offset_y=4.0,
)
```

!!! tip "Dica — `Color` com canal alpha"
    `Color(r=0, g=0, b=0, a=0.85)` é preto com 85% de opacidade — ideal para o overlay semitransparente do lightbox. O campo `a` aceita `float` entre `0.0` (transparente) e `1.0` (opaco).

---

## Passo 4 — Card de miniatura

Cada célula da grade é um `GestureDetector` que, ao ser tocado, define `state.selected = index`:

```python
from tempest_core import App, Style, Widget
from tempest_core.widgets import (
    Button,
    Column,
    Container,
    Dialog,
    GestureDetector,
    Image,
    ImageFit,
    LazyGrid,
    Row,
    Text,
)


def _build_thumbnail_card(app: App[GalleryState], index: int) -> Widget:
    """Build a thumbnail card for one gallery image.

    Creates a tappable card containing the thumbnail image and a short caption
    overlay.  Tapping it opens the lightbox by setting ``state.selected``.

    Args:
        app: The application handle.
        index: The zero-based index of the image in ``state.images``.

    Returns:
        A :class:`GestureDetector` wrapping the thumbnail card.
    """
    img: GalleryImage = app.state.images[index]

    def open_lightbox() -> None:
        """Open the lightbox for this thumbnail."""
        app.set_state(lambda s: setattr(s, "selected", index))

    return GestureDetector(
        key=f"thumb-{index}",
        on_tap=open_lightbox,
        child=Container(
            style=Style(
                radius=8.0,
                shadow=_CARD_SHADOW,
                background=_CARD_BG,
            ),
            child=Column(
                children=[
                    Image(
                        src=img.thumb,
                        fit=ImageFit.COVER,
                        alt=img.caption,
                        style=Style(
                            height=180.0,
                            radius=8.0,
                        ),
                    ),
                    Container(
                        style=Style(
                            padding=Edge.symmetric(vertical=6.0, horizontal=8.0),
                        ),
                        child=Text(
                            content=img.caption,
                            style=Style(
                                font_size=12.0,
                                color=_MUTED,
                                max_lines=1,
                            ),
                        ),
                    ),
                ],
            ),
        ),
    )
```

Veja os pontos-chave:

| Trecho | O que faz |
|---|---|
| `key=f"thumb-{index}"` | Garante identidade estável no reconciliador para cada card |
| `ImageFit.COVER` | Recorta a imagem para preencher o espaço sem distorção |
| `max_lines=1` | Trunca captions longos com reticências |
| `open_lightbox` (closure) | Captura `index` da iteração — cada card lembra seu próprio índice |

!!! warning "Atenção — closure em loop"
    `open_lightbox` é criada **dentro** de `_build_thumbnail_card`, que recebe `index` como parâmetro. Isso garante que cada closure captura o valor correto. Se você definir o handler diretamente dentro de um `for i in range(N)`, use `def handler(i=i)` para fixar o valor.

---

## Passo 5 — Dialog lightbox

O lightbox é um `Dialog` com três seções: imagem full-res, bloco de legenda e faixa de navegação:

```python
def _build_lightbox(app: App[GalleryState], index: int) -> Widget:
    """Build the full-screen lightbox Dialog for the selected image.

    Renders the full-resolution image with caption, author credit and
    Previous / Next / Close navigation controls.

    Args:
        app: The application handle.
        index: The zero-based index of the currently selected image.

    Returns:
        A :class:`Dialog` widget that floats above the gallery grid.
    """
    images: list[GalleryImage] = app.state.images
    img: GalleryImage = images[index]
    total: int = len(images)

    def close() -> None:
        """Close the lightbox."""
        app.set_state(lambda s: setattr(s, "selected", None))

    def go_prev() -> None:
        """Navigate to the previous image, wrapping around."""
        app.set_state(lambda s: setattr(s, "selected", (index - 1) % total))

    def go_next() -> None:
        """Navigate to the next image, wrapping around."""
        app.set_state(lambda s: setattr(s, "selected", (index + 1) % total))

    counter_text: str = f"{index + 1} / {total}"

    return Dialog(
        key="lightbox",
        title=None,
        on_dismiss=close,
        children=[
            Column(
                style=Style(
                    gap=12.0,
                    padding=Edge.all(0.0),
                    background=_OVERLAY_BG,
                    radius=12.0,
                    min_width=320.0,
                    max_width=900.0,
                ),
                children=[
                    # Full-resolution image.
                    Image(
                        src=img.src,
                        fit=ImageFit.CONTAIN,
                        alt=img.caption,
                        style=Style(
                            height=480.0,
                            radius=12.0,
                            background=_DARK_BG,
                        ),
                        key="lightbox-img",
                    ),
                    # Caption + author credit.
                    Container(
                        style=Style(
                            padding=Edge.symmetric(vertical=8.0, horizontal=16.0),
                            background=_CAPTION_BG,
                        ),
                        child=Column(
                            style=Style(gap=4.0),
                            children=[
                                Text(
                                    content=img.caption,
                                    style=Style(
                                        font_size=16.0,
                                        font_weight=FontWeight.SEMIBOLD,
                                        color=_WHITE,
                                        text_align=TextAlign.CENTER,
                                    ),
                                    key="lb-caption",
                                ),
                                Text(
                                    content=f"Photo by {img.author}",
                                    style=Style(
                                        font_size=12.0,
                                        color=_MUTED,
                                        text_align=TextAlign.CENTER,
                                    ),
                                    key="lb-author",
                                ),
                            ],
                        ),
                    ),
                    # Navigation row: Prev · counter · Next · Close.
                    Row(
                        style=Style(
                            gap=8.0,
                            padding=Edge.symmetric(vertical=8.0, horizontal=16.0),
                            justify=JustifyContent.CENTER,
                            align=AlignItems.CENTER,
                        ),
                        children=[
                            Button(
                                label="◀ Prev",
                                on_click=go_prev,
                                key="lb-prev",
                                style=Style(
                                    background=_ACCENT,
                                    color=_DARK_BG,
                                    radius=6.0,
                                    padding=Edge.symmetric(
                                        vertical=8.0, horizontal=14.0
                                    ),
                                ),
                            ),
                            Text(
                                content=counter_text,
                                style=Style(
                                    font_size=13.0,
                                    color=_MUTED,
                                    min_width=56.0,
                                    text_align=TextAlign.CENTER,
                                ),
                                key="lb-counter",
                            ),
                            Button(
                                label="Next ▶",
                                on_click=go_next,
                                key="lb-next",
                                style=Style(
                                    background=_ACCENT,
                                    color=_DARK_BG,
                                    radius=6.0,
                                    padding=Edge.symmetric(
                                        vertical=8.0, horizontal=14.0
                                    ),
                                ),
                            ),
                            Button(
                                label="✕ Close",
                                on_click=close,
                                key="lb-close",
                                style=Style(
                                    background=Color(r=220, g=53, b=69),
                                    color=_WHITE,
                                    radius=6.0,
                                    padding=Edge.symmetric(
                                        vertical=8.0, horizontal=14.0
                                    ),
                                ),
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
```

Três detalhes importantes:

| Detalhe | Por quê |
|---|---|
| `(index - 1) % total` | Wrap-around automático: da foto 0, "Prev" vai para a última |
| `ImageFit.CONTAIN` | Mostra a imagem inteira dentro do espaço disponível sem recortar |
| `on_dismiss=close` | Clique fora do Dialog (no overlay) também fecha o lightbox |

!!! info "Nota — como o Dialog flutua"
    O renderer do tempestweb promove nós `Dialog` automaticamente para a **camada de overlay** do DOM — você não precisa gerenciar `z-index` ou portais manualmente. Inclua o `Dialog` como filho normal na árvore e o runtime cuida do resto.

---

## Passo 6 — A função `view` e o `LazyGrid`

```python
def view(app: App[GalleryState]) -> Widget:
    """Render the gallery UI from the current state.

    When ``state.selected`` is ``None`` the plain grid is rendered.  When an
    index is set a :class:`Dialog` lightbox is included in the widget tree as
    a sibling at the column level; renderers promote ``Dialog`` nodes to the
    overlay layer automatically.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """
    state: GalleryState = app.state
    total: int = len(state.images)

    def build_thumb(index: int) -> Widget:
        """Materialize one thumbnail card for the lazy grid.

        Args:
            index: The item's absolute position in the grid.

        Returns:
            The thumbnail card widget.
        """
        return _build_thumbnail_card(app, index)

    grid: Widget = LazyGrid(
        key="gallery-grid",
        item_count=total,
        item_builder=build_thumb,
        columns=3,
        window_size=12,
        style=Style(
            gap=12.0,
            padding=Edge.all(16.0),
            background=_DARK_BG,
        ),
    )

    children: list[Widget] = [
        Text(
            content="Image Gallery",
            style=Style(
                font_size=24.0,
                font_weight=FontWeight.BOLD,
                color=_WHITE,
                padding=Edge(top=20.0, left=20.0, bottom=4.0),
            ),
            key="gallery-title",
        ),
        Text(
            content=f"{total} photos — tap any thumbnail to view full size",
            style=Style(
                font_size=13.0,
                color=_MUTED,
                padding=Edge(bottom=8.0, left=20.0),
            ),
            key="gallery-subtitle",
        ),
        grid,
    ]

    # When a thumbnail is selected, append the lightbox Dialog to the tree.
    # The renderer hoists Dialog nodes onto the overlay layer.
    if state.selected is not None:
        children.append(_build_lightbox(app, state.selected))

    return Column(
        key="gallery-root",
        style=Style(
            background=_DARK_BG,
            gap=0.0,
        ),
        children=children,
    )
```

O ponto central está nas últimas linhas de `view`:

```python
if state.selected is not None:
    children.append(_build_lightbox(app, state.selected))
```

Quando `selected` é `None`, a lista `children` tem apenas o título, subtítulo e a grade. Quando o usuário clica em uma miniatura, `selected` vira um inteiro e o `Dialog` é adicionado como irmão — o renderer o eleva para o overlay.

!!! tip "Dica — `LazyGrid` e `item_builder`"
    O `LazyGrid` aceita um callable `item_builder(index: int) -> Widget`. Ele **não** materializa todos os filhos de uma vez — apenas os itens dentro da janela `window_size` são construídos. Para 12 fotos neste exemplo o ganho é pequeno, mas o padrão escala para centenas de itens sem custo extra.

---

## O app completo

Aqui está o arquivo completo, pronto para copiar:

```python
"""Image gallery with lightbox — demonstrates LazyGrid, Image, and Dialog overlays.

A virtualized grid of photo thumbnails; tapping any thumbnail opens a full-screen
:class:`~tempest_core.widgets.Dialog` lightbox showing the selected image,
its caption and navigation controls (Previous / Next / Close).  The selected index
lives in state, and ``None`` means the lightbox is closed.

Run unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb run --mode server   # Python on the server (FastAPI + WebSocket)

The application never names a transport — that is the whole point.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Style, Widget
from tempest_core.style import (
    AlignItems,
    Color,
    Edge,
    FontWeight,
    JustifyContent,
    Shadow,
    TextAlign,
)
from tempest_core.widgets import (
    Button,
    Column,
    Container,
    Dialog,
    GestureDetector,
    Image,
    ImageFit,
    LazyGrid,
    Row,
    Text,
)


@dataclass
class GalleryImage:
    """A single gallery entry.

    Attributes:
        src: URL of the full-resolution image.
        thumb: URL of the thumbnail image (lower resolution).
        caption: Short descriptive caption shown in the lightbox.
        author: Photographer / attribution credit.
    """

    src: str
    thumb: str
    caption: str
    author: str


# ---------------------------------------------------------------------------
# Sample data — public domain / CC0 images via picsum.photos
# ---------------------------------------------------------------------------
_IMAGES: list[GalleryImage] = [
    GalleryImage(
        src="https://picsum.photos/id/10/1200/800",
        thumb="https://picsum.photos/id/10/400/300",
        caption="Mountain stream at dawn",
        author="Unsplash / Lorenzo Spoleti",
    ),
    GalleryImage(
        src="https://picsum.photos/id/20/1200/800",
        thumb="https://picsum.photos/id/20/400/300",
        caption="City lights after rain",
        author="Unsplash / Alejandro Escamilla",
    ),
    GalleryImage(
        src="https://picsum.photos/id/30/1200/800",
        thumb="https://picsum.photos/id/30/400/300",
        caption="Autumn forest trail",
        author="Unsplash / Ales Krivec",
    ),
    GalleryImage(
        src="https://picsum.photos/id/40/1200/800",
        thumb="https://picsum.photos/id/40/400/300",
        caption="Desert sunrise",
        author="Unsplash / Luca Bravo",
    ),
    GalleryImage(
        src="https://picsum.photos/id/50/1200/800",
        thumb="https://picsum.photos/id/50/400/300",
        caption="Ocean cliff at dusk",
        author="Unsplash / Emile Perron",
    ),
    GalleryImage(
        src="https://picsum.photos/id/60/1200/800",
        thumb="https://picsum.photos/id/60/400/300",
        caption="Snow-capped peaks",
        author="Unsplash / Luca Bravo",
    ),
    GalleryImage(
        src="https://picsum.photos/id/70/1200/800",
        thumb="https://picsum.photos/id/70/400/300",
        caption="Wheat field at noon",
        author="Unsplash / Lukasz Lada",
    ),
    GalleryImage(
        src="https://picsum.photos/id/80/1200/800",
        thumb="https://picsum.photos/id/80/400/300",
        caption="Misty lake reflection",
        author="Unsplash / Ales Krivec",
    ),
    GalleryImage(
        src="https://picsum.photos/id/90/1200/800",
        thumb="https://picsum.photos/id/90/400/300",
        caption="Redwood forest canopy",
        author="Unsplash / Gian Luca Pilia",
    ),
    GalleryImage(
        src="https://picsum.photos/id/100/1200/800",
        thumb="https://picsum.photos/id/100/400/300",
        caption="Cobblestone alley, Porto",
        author="Unsplash / Micah Hallahan",
    ),
    GalleryImage(
        src="https://picsum.photos/id/110/1200/800",
        thumb="https://picsum.photos/id/110/400/300",
        caption="Tuscan vineyards at harvest",
        author="Unsplash / Roberta Sorge",
    ),
    GalleryImage(
        src="https://picsum.photos/id/120/1200/800",
        thumb="https://picsum.photos/id/120/400/300",
        caption="Neon night market",
        author="Unsplash / Viktor Hanacek",
    ),
]


@dataclass
class GalleryState:
    """Runtime state for the image gallery.

    Attributes:
        images: The full ordered list of gallery images.
        selected: Index of the image currently open in the lightbox,
            or ``None`` when the lightbox is closed.
    """

    images: list[GalleryImage] = field(default_factory=lambda: list(_IMAGES))
    selected: int | None = None


def make_state() -> GalleryState:
    """Build the initial gallery state.

    Returns:
        A fresh :class:`GalleryState` with all sample images and no selection.
    """
    return GalleryState()


# ---------------------------------------------------------------------------
# Style constants
# ---------------------------------------------------------------------------
_WHITE: Color = Color(r=255, g=255, b=255)
_DARK_BG: Color = Color(r=18, g=18, b=18)
_OVERLAY_BG: Color = Color(r=0, g=0, b=0, a=0.85)
_CAPTION_BG: Color = Color(r=30, g=30, b=30)
_ACCENT: Color = Color(r=99, g=179, b=237)
_MUTED: Color = Color(r=160, g=160, b=160)
_CARD_BG: Color = Color(r=38, g=38, b=38)
_HOVER_BORDER: Color = Color(r=99, g=179, b=237)

_CARD_SHADOW: Shadow = Shadow(
    color=Color(r=0, g=0, b=0, a=0.4),
    blur=12.0,
    offset_y=4.0,
)


def _build_thumbnail_card(app: App[GalleryState], index: int) -> Widget:
    """Build a thumbnail card for one gallery image.

    Creates a tappable card containing the thumbnail image and a short caption
    overlay.  Tapping it opens the lightbox by setting ``state.selected``.

    Args:
        app: The application handle.
        index: The zero-based index of the image in ``state.images``.

    Returns:
        A :class:`GestureDetector` wrapping the thumbnail card.
    """
    img: GalleryImage = app.state.images[index]

    def open_lightbox() -> None:
        """Open the lightbox for this thumbnail."""
        app.set_state(lambda s: setattr(s, "selected", index))

    return GestureDetector(
        key=f"thumb-{index}",
        on_tap=open_lightbox,
        child=Container(
            style=Style(
                radius=8.0,
                shadow=_CARD_SHADOW,
                background=_CARD_BG,
            ),
            child=Column(
                children=[
                    Image(
                        src=img.thumb,
                        fit=ImageFit.COVER,
                        alt=img.caption,
                        style=Style(
                            height=180.0,
                            radius=8.0,
                        ),
                    ),
                    Container(
                        style=Style(
                            padding=Edge.symmetric(vertical=6.0, horizontal=8.0),
                        ),
                        child=Text(
                            content=img.caption,
                            style=Style(
                                font_size=12.0,
                                color=_MUTED,
                                max_lines=1,
                            ),
                        ),
                    ),
                ],
            ),
        ),
    )


def _build_lightbox(app: App[GalleryState], index: int) -> Widget:
    """Build the full-screen lightbox Dialog for the selected image.

    Renders the full-resolution image with caption, author credit and
    Previous / Next / Close navigation controls.

    Args:
        app: The application handle.
        index: The zero-based index of the currently selected image.

    Returns:
        A :class:`Dialog` widget that floats above the gallery grid.
    """
    images: list[GalleryImage] = app.state.images
    img: GalleryImage = images[index]
    total: int = len(images)

    def close() -> None:
        """Close the lightbox."""
        app.set_state(lambda s: setattr(s, "selected", None))

    def go_prev() -> None:
        """Navigate to the previous image, wrapping around."""
        app.set_state(lambda s: setattr(s, "selected", (index - 1) % total))

    def go_next() -> None:
        """Navigate to the next image, wrapping around."""
        app.set_state(lambda s: setattr(s, "selected", (index + 1) % total))

    counter_text: str = f"{index + 1} / {total}"

    return Dialog(
        key="lightbox",
        title=None,
        on_dismiss=close,
        children=[
            Column(
                style=Style(
                    gap=12.0,
                    padding=Edge.all(0.0),
                    background=_OVERLAY_BG,
                    radius=12.0,
                    min_width=320.0,
                    max_width=900.0,
                ),
                children=[
                    # Full-resolution image.
                    Image(
                        src=img.src,
                        fit=ImageFit.CONTAIN,
                        alt=img.caption,
                        style=Style(
                            height=480.0,
                            radius=12.0,
                            background=_DARK_BG,
                        ),
                        key="lightbox-img",
                    ),
                    # Caption + author credit.
                    Container(
                        style=Style(
                            padding=Edge.symmetric(vertical=8.0, horizontal=16.0),
                            background=_CAPTION_BG,
                        ),
                        child=Column(
                            style=Style(gap=4.0),
                            children=[
                                Text(
                                    content=img.caption,
                                    style=Style(
                                        font_size=16.0,
                                        font_weight=FontWeight.SEMIBOLD,
                                        color=_WHITE,
                                        text_align=TextAlign.CENTER,
                                    ),
                                    key="lb-caption",
                                ),
                                Text(
                                    content=f"Photo by {img.author}",
                                    style=Style(
                                        font_size=12.0,
                                        color=_MUTED,
                                        text_align=TextAlign.CENTER,
                                    ),
                                    key="lb-author",
                                ),
                            ],
                        ),
                    ),
                    # Navigation row: Prev · counter · Next · Close.
                    Row(
                        style=Style(
                            gap=8.0,
                            padding=Edge.symmetric(vertical=8.0, horizontal=16.0),
                            justify=JustifyContent.CENTER,
                            align=AlignItems.CENTER,
                        ),
                        children=[
                            Button(
                                label="◀ Prev",
                                on_click=go_prev,
                                key="lb-prev",
                                style=Style(
                                    background=_ACCENT,
                                    color=_DARK_BG,
                                    radius=6.0,
                                    padding=Edge.symmetric(
                                        vertical=8.0, horizontal=14.0
                                    ),
                                ),
                            ),
                            Text(
                                content=counter_text,
                                style=Style(
                                    font_size=13.0,
                                    color=_MUTED,
                                    min_width=56.0,
                                    text_align=TextAlign.CENTER,
                                ),
                                key="lb-counter",
                            ),
                            Button(
                                label="Next ▶",
                                on_click=go_next,
                                key="lb-next",
                                style=Style(
                                    background=_ACCENT,
                                    color=_DARK_BG,
                                    radius=6.0,
                                    padding=Edge.symmetric(
                                        vertical=8.0, horizontal=14.0
                                    ),
                                ),
                            ),
                            Button(
                                label="✕ Close",
                                on_click=close,
                                key="lb-close",
                                style=Style(
                                    background=Color(r=220, g=53, b=69),
                                    color=_WHITE,
                                    radius=6.0,
                                    padding=Edge.symmetric(
                                        vertical=8.0, horizontal=14.0
                                    ),
                                ),
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def view(app: App[GalleryState]) -> Widget:
    """Render the gallery UI from the current state.

    When ``state.selected`` is ``None`` the plain grid is rendered.  When an
    index is set a :class:`Dialog` lightbox is included in the widget tree as
    a sibling at the column level; renderers promote ``Dialog`` nodes to the
    overlay layer automatically.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """
    state: GalleryState = app.state
    total: int = len(state.images)

    def build_thumb(index: int) -> Widget:
        """Materialize one thumbnail card for the lazy grid.

        Args:
            index: The item's absolute position in the grid.

        Returns:
            The thumbnail card widget.
        """
        return _build_thumbnail_card(app, index)

    grid: Widget = LazyGrid(
        key="gallery-grid",
        item_count=total,
        item_builder=build_thumb,
        columns=3,
        window_size=12,
        style=Style(
            gap=12.0,
            padding=Edge.all(16.0),
            background=_DARK_BG,
        ),
    )

    children: list[Widget] = [
        Text(
            content="Image Gallery",
            style=Style(
                font_size=24.0,
                font_weight=FontWeight.BOLD,
                color=_WHITE,
                padding=Edge(top=20.0, left=20.0, bottom=4.0),
            ),
            key="gallery-title",
        ),
        Text(
            content=f"{total} photos — tap any thumbnail to view full size",
            style=Style(
                font_size=13.0,
                color=_MUTED,
                padding=Edge(bottom=8.0, left=20.0),
            ),
            key="gallery-subtitle",
        ),
        grid,
    ]

    # When a thumbnail is selected, append the lightbox Dialog to the tree.
    # The renderer hoists Dialog nodes onto the overlay layer.
    if state.selected is not None:
        children.append(_build_lightbox(app, state.selected))

    return Column(
        key="gallery-root",
        style=Style(
            background=_DARK_BG,
            gap=0.0,
        ),
        children=children,
    )
```

---

## Rodando o exemplo ▶

### Modo A — Python no browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm --path examples/image-gallery
```

O Python roda **dentro do browser** via Pyodide. Nenhum servidor necessário.

### Modo B — Python no servidor (FastAPI + WebSocket)

```bash
tempestweb run --mode server --path examples/image-gallery
```

O Python roda no servidor; o browser recebe patches JSON pelo WebSocket e aplica ao DOM.

!!! check "Verificação"
    Em qualquer modo, confirme:

    1. Grade 3×4 de fotos com fundo escuro
    2. Cada card mostra miniatura + legenda truncada embaixo
    3. Clicar em qualquer card abre o lightbox com a imagem grande
    4. Lightbox exibe legenda, crédito e contador `1 / 12`
    5. Botões **◀ Prev** e **Next ▶** navegam entre as fotos (com wrap-around)
    6. Botão **✕ Close** e clique fora do Dialog fecham o lightbox
    7. Após fechar, a grade volta sem recarregar a página

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

Todos devem passar em verde. O exemplo foi projetado para ser `mypy --strict` clean — toda variável, parâmetro e retorno é anotado explicitamente.

---

## Como funciona por dentro

### O ciclo completo de uma abertura de lightbox

```
Usuário clica na miniatura
          │
          ▼
GestureDetector.on_tap → open_lightbox()
          │
          ▼
app.set_state(lambda s: setattr(s, "selected", index))
          │
          ▼
state.selected: None → 2  (exemplo: terceira foto)
          │
          ▼
view(app) chamada novamente
          │
          ├─ Constrói grade normalmente
          └─ state.selected is not None → append(_build_lightbox(app, 2))
                    │
                    ▼
          Reconciliador calcula diff:
          único patch novo = INSERT Dialog
                    │
                    ▼
          Renderer eleva Dialog para overlay
```

### Por que `None` e não `False`?

Usar `selected: int | None` ao invés de `is_open: bool + current_index: int` tem duas vantagens:

1. **Um único campo** descreve os dois estados possíveis — galeria fechada e foto selecionada.
2. A função `view` pode testar `if state.selected is not None` e passar o índice diretamente para `_build_lightbox` sem precisar de `state.current_index`.

### `LazyGrid` vs. lista de widgets

| Abordagem | Custo na render inicial | Custo ao rolar |
|---|---|---|
| `LazyGrid(item_builder=...)` | Constrói apenas `window_size` itens | Constrói sob demanda |
| `Column(children=[...])` | Constrói **todos** os itens | Nenhum (já construídos) |

Para 12 fotos a diferença é imperceptível. Para 500+ itens, `LazyGrid` mantém a UI responsiva.

---

## Recapitulando

Neste tutorial você aprendeu:

- ✅ Modelar um **estado de sobreposição** com `int | None` — um campo para dois estados
- ✅ Usar **`LazyGrid`** com `item_builder` para grades virtualizadas
- ✅ Usar **`GestureDetector`** para capturar toques e abrir overlays
- ✅ Usar **`Dialog`** como overlay nativo — sem `z-index` manual
- ✅ Navegar circularmente com aritmética de módulo `(index ± 1) % total`
- ✅ Separar builders em funções privadas (`_build_thumbnail_card`, `_build_lightbox`) para manter `view` legível
- ✅ Usar `ImageFit.COVER` em miniaturas e `ImageFit.CONTAIN` no lightbox

---

## Próximos passos

Experimente estender o exemplo:

- 💡 Adicione um campo de **pesquisa** que filtra `state.images` por caption
- 💡 Implemente **arrastar para fechar** com `GestureDetector.on_pan_end`
- 💡 Explore o exemplo [Data Table](./data-table.md) para ver outro padrão de lista grande com seleção de linha
- 💡 Explore o exemplo [Tabs Profile](./tabs-profile.md) para navegação por abas dentro de overlays
- 💡 Volte ao [Tutorial básico](../tutorial/index.md) para ver como o reconciliador calcula os diffs que tornam tudo isso eficiente
