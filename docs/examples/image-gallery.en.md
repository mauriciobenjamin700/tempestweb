# Image Gallery with Lightbox 🚀

Build a virtualized 12-photo gallery where tapping any thumbnail opens a Dialog lightbox with the full-resolution image, caption, credit and Prev / Next / Close navigation — **all in pure Python**.

---

## What you'll build

A dark-themed gallery featuring:

- 🖼 3-column grid rendered by **`LazyGrid`** (automatic virtualization)
- 👆 Each thumbnail is a **`GestureDetector`** that opens the lightbox on tap
- 💬 **`Dialog`** lightbox with full-res image, caption, author and 4 navigation buttons
- ↔ Circular navigation (Prev / Next with wrap-around)
- 🔢 `1 / 12` counter centred between the buttons

!!! note "Note — one state, two modes"
    The field `selected: int | None` is the only piece of state. `None` = gallery open; an integer = lightbox open. tempestweb runs this same code unchanged in Mode A (WASM/Pyodide) and Mode B (server + WebSocket).

---

## Prerequisites

Make sure tempestweb is installed:

```bash
pip install tempestweb
```

Recommended reading (optional but helpful):

- [Basic tutorial](../tutorial/index.en.md) — first steps with `App`, `view`, and `set_state`
- [Managing state](../tutorial/state.en.md) — how `set_state` works
- [Execution modes](../tutorial/modes.en.md) — WASM vs. server

---

## Creating the project

```bash
mkdir -p examples/image-gallery
touch examples/image-gallery/app.py
```

---

## Step 1 — Modelling the data

Before any UI, think about the data. Each photo has four attributes:

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

Two separate URLs — `thumb` for the grid (400×300 px) and `src` for the lightbox (1200×800 px) — avoid downloading heavy images until the user actually clicks.

!!! tip "Tip — picsum.photos"
    The example uses `https://picsum.photos/id/<N>/<width>/<height>` to serve CC0 images without any API key. Any public URL works as a replacement.

---

## Step 2 — Defining the state

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

!!! info "Note — `int | None`"
    `selected` is `None` while the lightbox is closed and an integer (the photo's index) when it is open. This is the **"UI state as optional value"** pattern — simple, without extra boolean flags.

---

## Step 3 — Style constants

We centralise colours in named constants to avoid scattering raw numbers throughout the code:

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

!!! tip "Tip — `Color` with an alpha channel"
    `Color(r=0, g=0, b=0, a=0.85)` is black at 85% opacity — ideal for the semi-transparent lightbox overlay. The `a` field accepts a `float` between `0.0` (transparent) and `1.0` (fully opaque).

---

## Step 4 — Thumbnail card

Each grid cell is a `GestureDetector` that sets `state.selected = index` on tap:

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

Key points:

| Snippet | What it does |
|---|---|
| `key=f"thumb-{index}"` | Gives each card a stable identity for the reconciler |
| `ImageFit.COVER` | Crops the image to fill the space without distortion |
| `max_lines=1` | Truncates long captions with an ellipsis |
| `open_lightbox` (closure) | Captures `index` as a parameter — each card remembers its own index |

!!! warning "Watch out — closures in loops"
    `open_lightbox` is created **inside** `_build_thumbnail_card`, which receives `index` as a parameter. That guarantees each closure captures the right value. If you were defining the handler directly inside a `for i in range(N)` loop, use `def handler(i=i)` to freeze the value.

---

## Step 5 — Dialog lightbox

The lightbox is a `Dialog` with three sections: full-res image, caption block, and navigation strip:

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

Three important details:

| Detail | Why |
|---|---|
| `(index - 1) % total` | Automatic wrap-around: Prev from photo 0 jumps to the last one |
| `ImageFit.CONTAIN` | Shows the whole image within the available space without cropping |
| `on_dismiss=close` | Clicking outside the Dialog (on the backdrop) also closes the lightbox |

!!! info "Note — how the Dialog floats"
    tempestweb's renderer automatically promotes `Dialog` nodes to the **overlay layer** of the DOM — you don't need to manage `z-index` or portals manually. Include the `Dialog` as a regular child in the tree and the runtime handles the rest.

---

## Step 6 — The `view` function and `LazyGrid`

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

The key lies in the final lines of `view`:

```python
if state.selected is not None:
    children.append(_build_lightbox(app, state.selected))
```

When `selected` is `None`, `children` contains only the title, subtitle, and grid. When the user taps a thumbnail, `selected` becomes an integer and the `Dialog` is appended as a sibling — the renderer elevates it to the overlay.

!!! tip "Tip — `LazyGrid` and `item_builder`"
    `LazyGrid` accepts a callable `item_builder(index: int) -> Widget`. It does **not** materialise all children at once — only items within the `window_size` window are built. For 12 photos the gain is small, but the pattern scales to hundreds of items with no extra cost.

---

## The complete app

Here is the full file, ready to copy:

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

## Running the example ▶

### Mode A — Python in the browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm --path examples/image-gallery
```

Python runs **inside the browser** via Pyodide. No server required.

### Mode B — Python on the server (FastAPI + WebSocket)

```bash
tempestweb run --mode server --path examples/image-gallery
```

Python runs on the server; the browser receives JSON patches over the WebSocket and applies them to the DOM.

!!! check "Verification"
    In either mode, confirm:

    1. 3×4 photo grid on a dark background
    2. Each card shows a thumbnail with a truncated caption below
    3. Clicking any card opens the lightbox with the large image
    4. Lightbox shows caption, credit, and a `1 / 12` counter
    5. **◀ Prev** and **Next ▶** buttons navigate between photos (with wrap-around)
    6. **✕ Close** button and clicking outside the Dialog close the lightbox
    7. After closing, the grid is back without a page reload

---

## Automated verification ✅

Run the four checks before committing:

```bash
# Lint
ruff check .

# Formatting
ruff format --check .

# Types
mypy --strict tempestweb

# Tests
pytest -q
```

All must pass green. The example was designed to be `mypy --strict` clean — every variable, parameter, and return type is explicitly annotated.

---

## How it works under the hood

### The full cycle of opening a lightbox

```
User clicks thumbnail
          │
          ▼
GestureDetector.on_tap → open_lightbox()
          │
          ▼
app.set_state(lambda s: setattr(s, "selected", index))
          │
          ▼
state.selected: None → 2  (example: third photo)
          │
          ▼
view(app) called again
          │
          ├─ Builds grid normally
          └─ state.selected is not None → append(_build_lightbox(app, 2))
                    │
                    ▼
          Reconciler computes diff:
          single new patch = INSERT Dialog
                    │
                    ▼
          Renderer promotes Dialog to overlay layer
```

### Why `None` instead of `False`?

Using `selected: int | None` instead of `is_open: bool + current_index: int` has two advantages:

1. **A single field** describes both possible states — gallery closed and photo selected.
2. The `view` function can test `if state.selected is not None` and pass the index directly to `_build_lightbox` without needing a separate `state.current_index`.

### `LazyGrid` vs. list of widgets

| Approach | Cost on initial render | Cost while scrolling |
|---|---|---|
| `LazyGrid(item_builder=...)` | Builds only `window_size` items | Builds on demand |
| `Column(children=[...])` | Builds **all** items | None (already built) |

For 12 photos the difference is imperceptible. For 500+ items, `LazyGrid` keeps the UI responsive.

---

## Recap

In this tutorial you learned:

- ✅ Model an **overlay state** with `int | None` — one field for two states
- ✅ Use **`LazyGrid`** with `item_builder` for virtualised grids
- ✅ Use **`GestureDetector`** to capture taps and open overlays
- ✅ Use **`Dialog`** as a native overlay — no manual `z-index`
- ✅ Navigate circularly with modular arithmetic `(index ± 1) % total`
- ✅ Split builders into private functions (`_build_thumbnail_card`, `_build_lightbox`) to keep `view` readable
- ✅ Use `ImageFit.COVER` for thumbnails and `ImageFit.CONTAIN` in the lightbox

---

## Next steps

Try extending the example:

- 💡 Add a **search field** that filters `state.images` by caption
- 💡 Implement **swipe to dismiss** with `GestureDetector.on_pan_end`
- 💡 Explore the [Data Table](./data-table.en.md) example for another pattern of large lists with row selection
- 💡 Explore the [Tabs Profile](./tabs-profile.en.md) example for tab navigation inside overlays
- 💡 Return to the [Basic tutorial](../tutorial/index.en.md) to see how the reconciler computes the diffs that make all of this efficient
