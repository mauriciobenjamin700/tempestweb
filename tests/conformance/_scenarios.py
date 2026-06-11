"""Canonical conformance scenarios, built from the *real* vendored core.

Every fixture this harness commits is derived here from :func:`build` and
:func:`diff` over real widgets — nothing is hand-typed. Changing the wire format
means regenerating the fixtures from these scenarios (see :mod:`._generate`), so
the goldens can never silently drift from the core.

A *scenario* is an ordered list of trees. Consecutive trees are diffed to produce
one patch batch per "tick"; applying every batch in order to the rendered first
tree must reproduce the final tree's DOM. That property is what the A-vs-B test
and the wire-contract test both lean on.
"""

from __future__ import annotations

from typing import Any

from tempest_core import Button, Column, Row, Text, Widget, build, diff


def counter_views() -> list[Widget]:
    """Return the counter app's view at counts 0, 1, 2.

    Returns:
        Three :class:`Widget` trees exercising the Update patch (Text content).
    """
    return [_counter(0), _counter(1), _counter(2)]


def _counter(count: int) -> Widget:
    """Build the counter view for a given count.

    Args:
        count: The current counter value.

    Returns:
        The counter view tree.
    """
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


def list_views() -> list[Widget]:
    """Return a list-mutation sequence exercising insert, reorder and remove.

    Returns:
        Four :class:`Widget` trees: ``[a] -> [a, b] -> [b, a] -> [b]``.
    """
    return [
        _list(["a"]),
        _list(["a", "b"]),
        _list(["b", "a"]),
        _list(["b"]),
    ]


def _list(items: list[str]) -> Widget:
    """Build a Column of keyed Text children.

    Args:
        items: Stable keys/content for the children, in order.

    Returns:
        The list view tree.
    """
    return Column(
        key="root",
        children=[Text(content=item, key=item) for item in items],
    )


def replace_views() -> list[Widget]:
    """Return a sequence exercising the Replace patch (type change, same key slot).

    Returns:
        Two :class:`Widget` trees swapping a Text for a Button at the same path.
    """
    return [
        Column(key="root", children=[Text(content="a", key="x")]),
        Column(key="root", children=[Button(label="a", key="x")]),
    ]


# Every scenario the harness knows about, keyed by a stable name used in the
# golden fixture file. Order within each value is "tick order".
SCENARIOS: dict[str, list[Widget]] = {
    "counter": counter_views(),
    "list": list_views(),
    "replace": replace_views(),
}


def scenario_to_fixture(name: str, views: list[Widget]) -> dict[str, Any]:
    """Serialize one scenario into a JSON-able golden fixture.

    Args:
        name: The scenario's stable name.
        views: The ordered view trees for the scenario.

    Returns:
        A dict with the serialized initial node, the serialized final node, and
        the list of per-tick patch batches diffed from consecutive views.
    """
    built = [build(v) for v in views]
    ticks: list[list[dict[str, Any]]] = []
    for older, newer in zip(built[:-1], built[1:], strict=True):
        batch = [patch.model_dump(mode="json") for patch in diff(older, newer)]
        ticks.append(batch)
    return {
        "name": name,
        "initial": built[0].model_dump(mode="json"),
        "final": built[-1].model_dump(mode="json"),
        "ticks": ticks,
    }


def build_all_fixtures() -> dict[str, Any]:
    """Serialize every known scenario into the conformance golden payload.

    Returns:
        A mapping ``{scenario_name: fixture}`` covering all of :data:`SCENARIOS`.
    """
    return {name: scenario_to_fixture(name, views) for name, views in SCENARIOS.items()}
