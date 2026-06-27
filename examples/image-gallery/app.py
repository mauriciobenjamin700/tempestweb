"""Image gallery with lightbox — demonstrates LazyGrid, Image, and Dialog overlays.

A virtualized grid of photo thumbnails; tapping any thumbnail opens a full-screen
:class:`~tempest_core.widgets.Dialog` lightbox showing the selected image,
its caption and navigation controls (Previous / Next / Close).  The selected index
lives in state, and ``None`` means the lightbox is closed.

Run unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

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
