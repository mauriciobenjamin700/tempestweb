"""Gap-demonstrating tests for issue #160 — a lost batch is permanent and silent.

**These tests are not part of the repo suite.** ``testpaths = ["tests"]`` in
``pyproject.toml`` means ``uv run pytest`` never collects this file; it lives
beside the reproduction app so the mechanism the browser run measured also has a
headless proof. Moving it into ``tests/`` is the maintainer's call — see
``README.md``.

Run:
    uv run --frozen pytest repro/issue-160/test_lost_batch_160.py -q

Two invariants, both currently broken:

1. **Every batch Mode A hands the client is valid JSON.** ``Style.width`` (and
   every other unbounded numeric field) accepts a float ``nan``; the wire batch
   then serializes with the bare token ``NaN``, which ``JSON.parse`` rejects — so
   the browser drops the whole batch inside the bootstrap's ``onPatches``, before
   the transport, before the renderer, before any diagnostics.
2. **A batch that fails to reach the client does not advance the baseline.**
   ``App._rebuild`` assigns ``self._current = new`` *before* calling
   ``self._apply(patches)``. When delivery raises, Python's idea of the rendered
   tree has already moved, so the next tick's patches are index-relative to a
   tree the client never received — which is exactly the
   ``patch path out of range`` the issue reports.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from tempest_core import App, Column, Patch, Style, Text
from tempest_core.core.reconciler import build, diff
from tempestweb.runtime.wasm import serialize_patches

sys.path.insert(0, str(Path(__file__).parent / "app"))

import app as panel  # noqa: E402 — the reproduction app, imported after the path fix


def _wire_json(patches: list[Patch]) -> str:
    """Serialize a patch batch exactly as the Mode A bridge does.

    Args:
        patches: The batch the core's diff produced.

    Returns:
        The JSON string the bootstrap's ``onPatches`` receives.
    """
    return json.dumps(serialize_patches(patches))


def _panel_app(batches: list[list[Patch]]) -> App[Any]:
    """Start the reproduction panel on its login screen.

    Args:
        batches: Accumulator every emitted batch is appended to.

    Returns:
        The started app.
    """
    app: App[Any] = App(
        state=panel.make_state(), view=panel.view, apply_patches=batches.append
    )
    app.start()
    return app


@pytest.mark.xfail(
    strict=True,
    reason="issue #160: an unbounded numeric Style field accepts nan, and the "
    "batch then serializes as the bare token NaN, which JSON.parse rejects",
)
def test_a_delivered_batch_is_always_valid_json() -> None:
    """A batch carrying a ``nan`` style must still be valid JSON."""
    old = Column(key="root", children=[Text(content="a", key="t")])
    new = Column(
        key="root",
        children=[Text(content="a", key="t", style=Style(width=float("nan")))],
    )
    text = _wire_json(diff(build(old), build(new)))
    assert "NaN" in text
    # Python accepts NaN on the way back in; JSON.parse does not.
    json.dumps(json.loads(text), allow_nan=False)


@pytest.mark.xfail(
    strict=True,
    reason="issue #160: App._rebuild commits self._current before self._apply, "
    "so a delivery that raises leaves Python's baseline ahead of the client",
)
def test_a_failed_delivery_does_not_advance_the_baseline() -> None:
    """The reported failure, end to end, with no browser.

    The panel goes login → dashboard, then a poll tick both adds the second
    ``AppBar`` action and reports a non-finite ``load_pct``. That batch cannot
    cross the seam (invalid JSON), and the tick after it addresses
    ``[0, 1, 1]`` — ``appbar-actions``' second child — which the client never
    received.
    """
    batches: list[list[Patch]] = []
    app = _panel_app(batches)

    app.state.logged_in = True
    app.state.rows = [[f"r{row}c{col}" for col in range(8)] for row in range(40)]
    app.state.load_pct = 0.4
    app.set_state()
    app._rebuild()  # noqa: SLF001 — driving the loop synchronously, no asyncio
    assert _wire_json(batches[-1])

    app.state.alerts = 3
    app.state.load_pct = float("nan")
    app.state.tick = 2
    app._rebuild()  # noqa: SLF001
    lost = batches[-1]
    assert any(
        list(patch.path) == [0, 1] and getattr(patch, "index", None) == 1
        for patch in lost
    ), "the lost batch is the one that inserts the second AppBar action"
    with pytest.raises(ValueError, match="not JSON compliant"):
        json.dumps(serialize_patches(lost), allow_nan=False)

    app.state.alerts = 4
    app.state.load_pct = 0.55
    app.state.tick = 3
    app._rebuild()  # noqa: SLF001
    paths = [list(patch.path) for patch in batches[-1]]
    assert [0, 1, 1] not in paths, (
        "the tick after a lost batch addresses appbar-actions/1, a node the "
        f"client never received; paths were {paths[:4]}"
    )
