"""PWA icon emitter (P0).

Generates the icon set referenced by the manifest at build time, using only the
standard library — no Pillow, no external image deps. The generated icons are
solid-color placeholders (valid PNGs) so a freshly-scaffolded app is installable
out of the box; a project replaces them with branded artwork.

Each PNG is a real, byte-valid 8-bit RGBA image written with ``zlib`` + manual
chunk framing, so browsers and Lighthouse accept it as a genuine icon.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class IconSpec:
    """Specification for one icon file to emit.

    Attributes:
        filename: File name written under the icons directory.
        size: Square edge length in pixels (e.g. 192, 512).
        maskable: Whether this icon is intended as a maskable icon. Maskable
            icons get a larger safe-zone inset so the OS mask never clips art.
    """

    filename: str
    size: int
    maskable: bool = False


#: The default icon set emitted by ``tempestweb build`` — the four files the
#: manifest's ``DEFAULT_ICONS`` references, plus the apple-touch icon.
DEFAULT_ICON_SPECS: tuple[IconSpec, ...] = (
    IconSpec("icon-192.png", 192, maskable=False),
    IconSpec("icon-512.png", 512, maskable=False),
    IconSpec("maskable-192.png", 192, maskable=True),
    IconSpec("maskable-512.png", 512, maskable=True),
    IconSpec("apple-touch-icon.png", 180, maskable=False),
)


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    """Frame one PNG chunk (length, tag, data, CRC).

    Args:
        tag: The 4-byte chunk type.
        data: The chunk payload.

    Returns:
        The framed chunk bytes.
    """
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def placeholder_png(
    size: int,
    color: tuple[int, int, int, int] = (17, 17, 17, 255),
    inset: int = 0,
    inset_color: tuple[int, int, int, int] = (255, 255, 255, 255),
) -> bytes:
    """Build a valid 8-bit RGBA PNG of a solid color with an optional inset.

    The inset draws a centered square of ``inset_color`` to mimic a maskable
    icon's safe zone, so the generated maskable variants look intentional.

    Args:
        size: Square edge length in pixels (> 0).
        color: Background RGBA (0-255 each).
        inset: Border width in pixels left as ``color`` around an inner square.
        inset_color: RGBA of the inner square.

    Returns:
        The complete PNG file bytes.

    Raises:
        ValueError: If ``size`` is not positive.
    """
    if size <= 0:
        raise ValueError("size must be a positive integer")

    bg = bytes(color)
    fg = bytes(inset_color)
    lo = inset
    hi = size - inset

    raw = bytearray()
    for y in range(size):
        raw.append(0)  # filter type 0 (None) per scanline
        for x in range(size):
            if inset and lo <= x < hi and lo <= y < hi:
                raw += fg
            else:
                raw += bg

    ihdr = struct.pack(
        ">IIBBBBB",
        size,  # width
        size,  # height
        8,  # bit depth
        6,  # color type: RGBA
        0,  # compression
        0,  # filter
        0,  # interlace
    )
    idat = zlib.compress(bytes(raw), 9)

    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", idat)
        + _png_chunk(b"IEND", b"")
    )


def emit_icons(
    dest_dir: Path,
    specs: tuple[IconSpec, ...] = DEFAULT_ICON_SPECS,
    color: tuple[int, int, int, int] = (17, 17, 17, 255),
) -> list[Path]:
    """Write the icon set to ``dest_dir`` (e.g. ``<build>/icons``).

    Maskable specs get a ~10% safe-zone inset so the OS mask never clips the art.

    Args:
        dest_dir: Output directory (created if missing).
        specs: Icon specifications to emit.
        color: Base color for the icons.

    Returns:
        The list of paths written, in spec order.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for spec in specs:
        # Maskable safe zone: keep art within the central 80% (10% inset each side).
        inset = round(spec.size * 0.1) if spec.maskable else 0
        png = placeholder_png(spec.size, color=color, inset=inset)
        path = dest_dir / spec.filename
        path.write_bytes(png)
        written.append(path)
    return written
