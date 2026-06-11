"""The A-vs-B guarantee: same patch stream, identical DOM, regardless of transport.

Two mock transports with deliberately different internals (in-process vs. a JSON
wire round trip) are fed the *same* patch stream derived from the real core. The
contract holds iff their rendered DOMs are byte-for-byte identical and equal to
the core's final view. This is the executable proof of transport-independence.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from tests.conformance._dom import DomNode, apply_batch
from tests.conformance._scenarios import SCENARIOS, scenario_to_fixture
from tests.conformance._transports import MockTransportA, MockTransportB


def _scenario_stream(scenario_name: str) -> dict[str, Any]:
    """Build the initial IR, per-tick batches and final IR for a scenario.

    Args:
        scenario_name: The scenario to materialize.

    Returns:
        The scenario fixture (``initial``/``ticks``/``final``).
    """
    return scenario_to_fixture(scenario_name, SCENARIOS[scenario_name])


@pytest.mark.parametrize("scenario_name", sorted(SCENARIOS))
def test_two_transports_render_identical_dom(scenario_name: str) -> None:
    """Mode-A and Mode-B doubles converge to identical DOM and to the core's final.

    Args:
        scenario_name: The scenario under test.
    """
    fixture = _scenario_stream(scenario_name)

    async def drive() -> tuple[DomNode, DomNode]:
        """Feed both transports the same stream and return their final trees."""
        transport_a = MockTransportA(DomNode.from_ir(fixture["initial"]))
        transport_b = MockTransportB(DomNode.from_ir(fixture["initial"]))
        for batch in fixture["ticks"]:
            await transport_a.send_patches(batch)
            await transport_b.send_patches(batch)
        return transport_a.root, transport_b.root

    final_a, final_b = asyncio.run(drive())

    # A-vs-B: the two transports produced the exact same DOM.
    assert final_a.to_ir() == final_b.to_ir()
    # And both match what the core says the final view is — proving the stream was
    # applied correctly, not merely that two identical bugs agreed.
    assert final_a.to_ir() == fixture["final"]


@pytest.mark.parametrize("scenario_name", sorted(SCENARIOS))
def test_applying_stream_to_initial_reproduces_final(scenario_name: str) -> None:
    """Sanity: applying every batch to the initial IR reproduces the final IR.

    This isolates the reference applicator from the transports, so a transport bug
    can be told apart from an applicator bug.

    Args:
        scenario_name: The scenario under test.
    """
    fixture = _scenario_stream(scenario_name)
    root = DomNode.from_ir(fixture["initial"])
    for batch in fixture["ticks"]:
        root = apply_batch(root, batch)
    assert root.to_ir() == fixture["final"]


def test_transports_satisfy_the_patch_transport_protocol() -> None:
    """Both doubles are runtime-instances of the PatchTransport Protocol.

    The harness must depend only on the seam (the Protocol), never on a concrete
    transport, so this guards against the doubles drifting from the contract.
    """
    from tempestweb.transports.base import PatchTransport

    node = DomNode(type="Column", key="root", props={}, children=[])
    assert isinstance(MockTransportA(node), PatchTransport)
    assert isinstance(MockTransportB(node), PatchTransport)


def test_empty_batch_is_a_noop_for_both_transports() -> None:
    """An empty patch batch leaves the DOM unchanged on either transport."""

    async def drive() -> None:
        """Send an empty batch through both transports and assert no mutation."""
        initial = {
            "type": "Column",
            "key": "root",
            "props": {"style": None},
            "children": [],
        }
        transport_a = MockTransportA(DomNode.from_ir(initial))
        transport_b = MockTransportB(DomNode.from_ir(initial))
        await transport_a.send_patches([])
        await transport_b.send_patches([])
        assert transport_a.root.to_ir() == initial
        assert transport_b.root.to_ir() == initial

    asyncio.run(drive())


def test_events_round_trip_through_both_transports() -> None:
    """Client events survive both transports; the JSON-wire one round-trips intact.

    Events flow client->Python; the contract shape is
    ``{type, key, payload}``. Mode B serializes them, so this also guards the
    event wire shape against JSON coercion.
    """

    async def drive() -> tuple[dict[str, Any], dict[str, Any]]:
        """Inject the same event into both transports and read it back."""
        node = DomNode(type="Column", key="root", props={}, children=[])
        event: dict[str, Any] = {"type": "click", "key": "inc", "payload": {}}
        transport_a = MockTransportA(node)
        transport_b = MockTransportB(node)
        transport_a.inject_event(event)
        transport_b.inject_event(event)
        return await transport_a.recv_event(), await transport_b.recv_event()

    got_a, got_b = asyncio.run(drive())
    assert got_a == got_b == {"type": "click", "key": "inc", "payload": {}}
