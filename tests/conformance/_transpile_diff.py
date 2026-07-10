"""Regenerate the Mode C (transpile) diff-conformance fixture from the real core.

Run as a module to (re)write the golden::

    python -m tests.conformance._transpile_diff

The fixture is a list of ``{name, before, after, patches}`` cases where ``before``
and ``after`` are serialized IR trees and ``patches`` is the batch the *real* core
``diff`` emits between them. The JS ``client/transpile/diff.js`` is asserted to
reproduce ``patches`` from ``diff(before, after)`` — the same regenerable-golden
guarantee as the wire-contract fixtures. Nothing is hand-typed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tempest_core import Button, Column, Row, Text, Widget, build, diff

FIXTURES_DIR: Path = Path(__file__).resolve().parents[1] / "fixtures"
DIFF_FIXTURE: Path = FIXTURES_DIR / "transpile_diff_cases.json"


def _counter(count: int) -> Widget:
    """Counter view at a given count (exercises Update: Text content)."""
    return Column(
        key="root",
        children=[
            Text(content=f"Count: {count}", key="label"),
            Row(
                children=[
                    Button(label="-", key="dec"),
                    Button(label="+", key="inc"),
                ]
            ),
        ],
    )


def _list(items: list[str]) -> Widget:
    """A keyed list (exercises Insert/Remove/Reorder)."""
    return Column(
        key="root",
        children=[Text(content=item, key=item) for item in items],
    )


def _cases() -> list[tuple[str, Widget, Widget]]:
    """Return ``(name, before, after)`` triples covering all five patch kinds."""
    return [
        ("update", _counter(0), _counter(1)),
        ("insert", _list(["a"]), _list(["a", "b"])),
        ("remove", _list(["a", "b"]), _list(["a"])),
        ("reorder", _list(["a", "b"]), _list(["b", "a"])),
        (
            "replace",
            Column(key="root", children=[Text(content="x", key="x")]),
            Column(key="root", children=[Button(label="x", key="x")]),
        ),
        ("noop", _counter(2), _counter(2)),
    ]


def build_diff_cases() -> list[dict[str, Any]]:
    """Build the diff-conformance cases from the real core.

    Returns:
        One dict per case with serialized ``before``/``after`` trees and the
        golden ``patches`` batch the core ``diff`` emits between them.
    """
    cases: list[dict[str, Any]] = []
    for name, before, after in _cases():
        before_node = build(before)
        after_node = build(after)
        patches = [p.model_dump(mode="json") for p in diff(before_node, after_node)]
        cases.append(
            {
                "name": name,
                "before": before_node.model_dump(mode="json"),
                "after": after_node.model_dump(mode="json"),
                "patches": patches,
            }
        )
    return cases


def render_fixture_text() -> str:
    """Render the diff-cases golden as canonical, diff-stable JSON text."""
    return (
        json.dumps(build_diff_cases(), indent=2, sort_keys=True, ensure_ascii=False)
        + "\n"
    )


def write_fixture() -> Path:
    """Write the diff-cases golden fixture to disk.

    Returns:
        The path the fixture was written to.
    """
    DIFF_FIXTURE.write_text(render_fixture_text(), encoding="utf-8")
    return DIFF_FIXTURE


def main() -> None:
    """Regenerate the diff-cases fixture and print its path."""
    print(f"wrote {write_fixture()}")


if __name__ == "__main__":
    main()
