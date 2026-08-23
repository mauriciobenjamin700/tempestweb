"""Regenerate the Mode C lazy-scroller parity fixture from the real core.

Run as a module to (re)write the golden::

    python -m tests.conformance._transpile_lazy

A generated widget builder is a passthrough, and a lazy scroller is the one
widget whose children do not exist until something *runs*: the core resolves a
visible window and calls ``item_builder(index)`` over it, re-keying each item by
its absolute index. Mode C reproduces that in ``lazyChildren``
(``client/transpile/widget-support.js``), and nothing checks a reimplementation
is faithful — so this fixture pins the expected IR, built from the **real** core
over a matrix of windows, and a JS test diffs the builder against it.

The matrix matters: one sample per widget would pin the happy path and let the
clamping drift silently, which is exactly where a window slid by a scroll event
goes wrong — a stale pair addressing items that no longer exist.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tempest_core import (
    LazyColumn,
    LazyGrid,
    LazyRow,
    Style,
    Text,
    Widget,
    build,
)
from tempestweb.runtime.wasm import serialize_node

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
LAZY_FIXTURE: Path = REPO_ROOT / "tests" / "fixtures" / "transpile_lazy_samples.json"


def _item(index: int) -> Widget:
    """Build the item at `index`, carrying a key the core must override.

    Args:
        index: The item's absolute index.

    Returns:
        A text widget keyed by something other than the index, so a fixture that
        matched by accident would still show the re-keying.
    """
    return Text(content=f"row {index}", key=f"mine-{index}")


def _cases() -> dict[str, Widget]:
    """Return the parity matrix: scenario name → the widget the core builds.

    Returns:
        A name-sorted mapping covering the default window, an explicit one, both
        clamping directions, the empty list, and the props that ride along
        (``refreshing``, ``end_reached_threshold``, ``columns``, ``style``).
    """
    return {
        "column_default_window": LazyColumn(item_count=5, item_builder=_item),
        "column_window_size_below_count": LazyColumn(
            item_count=100, item_builder=_item, window_size=3
        ),
        "column_count_below_window_size": LazyColumn(
            item_count=2, item_builder=_item, window_size=20
        ),
        "column_explicit_window": LazyColumn(
            item_count=100, item_builder=_item, window=(30, 34)
        ),
        "column_window_past_the_end": LazyColumn(
            item_count=5, item_builder=_item, window=(3, 99)
        ),
        "column_window_out_of_range": LazyColumn(
            item_count=5, item_builder=_item, window=(50, 60)
        ),
        "column_window_negative_start": LazyColumn(
            item_count=5, item_builder=_item, window=(-3, 2)
        ),
        "column_window_inverted": LazyColumn(
            item_count=10, item_builder=_item, window=(6, 2)
        ),
        "column_empty": LazyColumn(item_count=0, item_builder=_item),
        "column_refreshing_and_threshold": LazyColumn(
            item_count=8,
            item_builder=_item,
            window_size=4,
            refreshing=True,
            end_reached_threshold=0.5,
        ),
        "column_styled": LazyColumn(
            item_count=3, item_builder=_item, style=Style(height=300.0)
        ),
        "row_default_window": LazyRow(item_count=4, item_builder=_item),
        "row_explicit_window": LazyRow(
            item_count=50, item_builder=_item, window=(10, 13)
        ),
        "grid_default_window": LazyGrid(item_count=7, item_builder=_item, columns=3),
        "grid_window_size_below_count": LazyGrid(
            item_count=40, item_builder=_item, columns=4, window_size=6
        ),
        "grid_explicit_window": LazyGrid(
            item_count=40, item_builder=_item, columns=2, window=(12, 15)
        ),
    }


def build_samples() -> dict[str, Any]:
    """Build each scenario to its serialized IR.

    The serializer is the runtime's own, so ``item_builder`` and the handler
    props are ``null`` here exactly as they are on the wire — which is what the
    JS builder emits.

    Returns:
        A scenario → serialized IR node map.
    """
    return {name: serialize_node(build(widget)) for name, widget in _cases().items()}


def render_fixture_text() -> str:
    """Render the lazy-parity fixture as canonical JSON text.

    Returns:
        The fixture's full text, with a trailing newline.
    """
    return (
        json.dumps(build_samples(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )


def write_fixture() -> Path:
    """Write the lazy-parity fixture to disk.

    Returns:
        The path written.
    """
    LAZY_FIXTURE.write_text(render_fixture_text(), encoding="utf-8")
    return LAZY_FIXTURE


def main() -> None:
    """Regenerate the lazy-parity fixture and print its path."""
    print(f"wrote {write_fixture()}")


if __name__ == "__main__":
    main()
