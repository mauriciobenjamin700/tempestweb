"""Regression tests for the Mode B wire serializer (``runtime.serialize``).

The runtime path (:func:`node_to_wire` / :func:`scene_to_initial_patches`) is the
one the WebSocket and SSE transports actually call to lower the IR to JSON before
``send_json``. It must produce a JSON-serializable payload for **styled** nodes:
``Style``/``Color``/``Edge`` are Pydantic models and, unlowered, are not
JSON-serializable — which previously crashed the initial mount of any view that
set a ``style`` (e.g. the counter example), even though the unstyled test app and
the contract suite (which dumps via ``Node.model_dump``) stayed green.
"""

from __future__ import annotations

import json
from typing import Any

from tempestweb._core import Column, Style, Text, Widget, build
from tempestweb._core.style import Edge
from tempestweb.runtime import node_to_wire


def _styled_tree() -> Widget:
    """Build a styled widget tree mirroring the counter example."""
    return Column(
        style=Style(gap=8.0, padding=Edge.all(16)),
        children=[Text(content="Count: 0", key="label")],
    )


def test_node_to_wire_lowers_style_to_json() -> None:
    """A node carrying a ``Style`` prop serializes to a JSON-able dict."""
    wire = node_to_wire(build(_styled_tree()))
    # The whole payload must round-trip through json without raising.
    dumped = json.dumps(wire)
    assert "Count: 0" in dumped


def test_node_to_wire_style_has_contract_shape() -> None:
    """The lowered ``style`` matches the contract wire shape (Edge → dict)."""
    wire = node_to_wire(build(_styled_tree()))
    style: dict[str, Any] = wire["props"]["style"]
    assert style["gap"] == 8.0
    # Edge lowers to {top,right,bottom,left}, not a live Edge object.
    assert style["padding"] == {
        "top": 16.0,
        "right": 16.0,
        "bottom": 16.0,
        "left": 16.0,
    }
