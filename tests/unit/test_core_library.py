"""Tests for the re-exported tempest-core component library.

Two guarantees: the re-export is faithful (every name in
:mod:`tempestweb.components.library` is the very class from
:mod:`tempest_core.components`), and the components lower to node types the web
client renders (the renderer-agnostic primitives or a ``Canvas`` draw-command
list).
"""

from __future__ import annotations

from typing import Any

import tempest_core.components as core_components
import tempestweb.components as tw_components
from tempest_core import Node, Text, build
from tempest_core.components import (
    Alert,
    BarChart,
    Card,
    ChartSeries,
    Chip,
    Divider,
    EmptyState,
    LineChart,
    ListTile,
    Stat,
)
from tempestweb.components import library

# Node types the web DOM renderer (client/dom.js) knows how to render: the
# renderer-agnostic primitives plus Canvas (executed onto a 2D context).
RENDERABLE_TYPES: frozenset[str] = frozenset(
    {
        "Column",
        "Row",
        "Container",
        "Stack",
        "Text",
        "Button",
        "Input",
        "Checkbox",
        "Image",
        "Canvas",
        "LazyColumn",
        "LazyRow",
        "LazyGrid",
        "Icon",
    }
)


def test_library_reexports_are_the_core_classes() -> None:
    """Every library export is the identical object from tempest_core.components."""
    for name in library.__all__:
        assert hasattr(core_components, name), f"{name} missing from core"
        assert getattr(library, name) is getattr(core_components, name), name


def test_library_is_reachable_from_the_components_package() -> None:
    """The whole library surface is importable from tempestweb.components."""
    for name in library.__all__:
        assert name in tw_components.__all__, f"{name} not exported by package"
        assert getattr(tw_components, name) is getattr(library, name), name


def _leaf_types(node: Node) -> set[str]:
    """Collect the types of every leaf node in a built tree.

    Args:
        node: The built IR root.

    Returns:
        The set of node types that have no children.
    """
    seen: set[str] = set()

    def walk(n: Node) -> None:
        if not n.children:
            seen.add(n.type)
        for child in n.children:
            walk(child)

    walk(node)
    return seen


def test_sampled_components_lower_to_renderable_leaves() -> None:
    """A representative sample of components lowers to renderable node types."""
    samples: list[Any] = [
        Card(children=[Text(content="body")]),
        Alert(message="heads up"),
        Chip(label="tag"),
        Divider(),
        EmptyState(title="nothing here"),
        Stat(label="Users", value="42"),
        ListTile(title="Row"),
    ]
    for widget in samples:
        leaves = _leaf_types(build(widget))
        name = type(widget).__name__
        assert leaves, f"{name} produced no leaves"
        assert leaves <= RENDERABLE_TYPES, (
            f"{name} lowers to unrenderable {leaves - RENDERABLE_TYPES}"
        )


def test_charts_lower_to_a_canvas_leaf() -> None:
    """BarChart/LineChart lower to a Canvas the web client now renders."""
    series = [ChartSeries(points=[1.0, 3.0, 2.0, 5.0], label="a")]
    for chart in (BarChart(series=series), LineChart(series=series)):
        leaves = _leaf_types(build(chart))
        assert "Canvas" in leaves, f"{type(chart).__name__} has no Canvas leaf"
        assert leaves <= RENDERABLE_TYPES
