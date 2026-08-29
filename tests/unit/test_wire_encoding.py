"""The encode seam — the last place Python can still fail loud (issue #160).

A float that is ``nan`` or ``inf`` has no JSON token. Python's encoder writes the
bare words ``NaN``/``Infinity`` unless told otherwise, and every browser's
``JSON.parse`` rejects them — so the batch reached the client as a ``SyntaxError``
thrown inside the decode, **before** the transport, the renderer and any
diagnostic. The batch vanished whole, while the core's baseline had already moved
past it, so the next tick's index-relative patches addressed nodes the client
never received (``patch path out of range``).

Nothing pinned that. These tests pin it at each of the three seams that turn a
payload into wire text — Mode A's FFI string, Mode B's WebSocket frame and Mode
B's SSE frame — and check that a finite payload still encodes byte for byte what
it did before.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

import pytest
from starlette.websockets import WebSocketState

from tempest_core import App, Button, Column, Style, Text, Widget, build, diff
from tempestweb.runtime import serialize_patches
from tempestweb.runtime.wasm_main import bootstrap
from tempestweb.transports import NonFiniteWireValueError, encode_wire
from tempestweb.transports.sse import SSETransport
from tempestweb.transports.websocket import WebSocketTransport

# --------------------------------------------------------------------------- #
# encode_wire                                                                  #
# --------------------------------------------------------------------------- #


def test_finite_payloads_encode_exactly_as_before() -> None:
    """Each call site's arguments reproduce the encoder it replaced, byte for byte."""
    payload: dict[str, Any] = {"kind": "patches", "data": [{"w": 1.5, "s": "café"}]}
    assert encode_wire(payload) == json.dumps(payload)
    assert encode_wire(payload, separators=(",", ":")) == json.dumps(
        payload, separators=(",", ":")
    )
    compact_utf8 = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    assert (
        encode_wire(payload, separators=(",", ":"), ensure_ascii=False) == compact_utf8
    )


@pytest.mark.parametrize("offender", [float("nan"), float("inf"), float("-inf")])
def test_a_non_finite_float_raises_instead_of_encoding(offender: float) -> None:
    """All three non-finite floats are refused, not written as bare tokens."""
    with pytest.raises(NonFiniteWireValueError):
        encode_wire({"style": {"width": offender}})


def test_the_error_names_the_field_that_produced_it() -> None:
    """The message carries the path, because the value came from the app's data.

    ``Out of range float values are not JSON compliant`` — the stdlib's message —
    says a batch is bad without saying which of a few thousand props did it. The
    field path is what turns the failure into a fix.
    """
    payload = {
        "kind": "patches",
        "data": [{"set_props": {}}, {"style": {"width": float("nan")}}],
    }
    with pytest.raises(NonFiniteWireValueError, match=r"data\[1\]\.style\.width"):
        encode_wire(payload)


def test_a_non_finite_at_the_root_is_still_located() -> None:
    """A bare float payload has no path, and says so rather than naming nothing."""
    with pytest.raises(NonFiniteWireValueError, match="<root>"):
        encode_wire(float("nan"))


def test_a_type_json_cannot_encode_still_raises_its_own_error() -> None:
    """Only non-finite floats become this error; a bad type stays a TypeError."""
    with pytest.raises(TypeError):
        encode_wire({"when": object()})


# --------------------------------------------------------------------------- #
# The real core, the real serializer                                           #
# --------------------------------------------------------------------------- #


def test_a_style_carrying_nan_cannot_be_encoded() -> None:
    """The reported trigger, from the core down to the wire text.

    ``Style.width`` has no bound, so ``float("nan")`` passes validation (fields
    that do have one, like ``Style.opacity``, reject it). The batch then reaches
    this seam, which is where it has to stop.
    """
    old = Column(key="root", children=[Text(content="a", key="t")])
    new = Column(
        key="root",
        children=[Text(content="a", key="t", style=Style(width=float("nan")))],
    )
    patches = serialize_patches(diff(build(old), build(new)))
    with pytest.raises(NonFiniteWireValueError, match="width"):
        encode_wire(patches)


# --------------------------------------------------------------------------- #
# Mode A — the FFI string                                                      #
# --------------------------------------------------------------------------- #


@dataclass
class DrainState:
    """State for an app whose backend reports a draining node."""

    width: float = 40.0
    log: list[str] = field(default_factory=list)


def drain_view(app: App[DrainState]) -> Widget:
    """Render a bar whose width comes straight from a reported metric."""

    def drain() -> None:
        app.set_state(lambda s: setattr(s, "width", float("nan")))

    return Column(
        key="root",
        children=[
            Text(content="load", key="bar", style=Style(width=app.state.width)),
            Button(label="drain", on_click=drain, key="drain"),
        ],
    )


@pytest.mark.asyncio
async def test_mode_a_never_hands_the_client_text_it_cannot_decode() -> None:
    """A batch Mode A cannot encode raises on the loop instead of crossing the FFI.

    The bridge hands JS a JSON string, so an unencodable batch used to cross as
    ``{"width": NaN}`` and die inside the client's decode. It now fails on the
    Python side, where the exception names the field and the client is never told
    a lie.
    """
    delivered: list[str] = []
    failures: list[BaseException] = []
    loop = asyncio.get_running_loop()
    previous = loop.get_exception_handler()
    loop.set_exception_handler(
        lambda _loop, context: failures.append(context.get("exception", RuntimeError()))
    )
    handle = bootstrap(DrainState(), drain_view, delivered.append)
    try:
        click = {"type": "click", "key": "drain", "payload": {}}
        handle.push_event_json(json.dumps(click))
        for _ in range(8):
            await asyncio.sleep(0)
    finally:
        loop.set_exception_handler(previous)
        await handle.close()

    assert not any("NaN" in text for text in delivered)
    assert any(isinstance(exc, NonFiniteWireValueError) for exc in failures), failures


@pytest.mark.asyncio
async def test_mode_a_refuses_an_initial_tree_json_cannot_express() -> None:
    """The mount path is guarded too: JS parses this string before anything runs."""
    handle = bootstrap(DrainState(width=float("nan")), drain_view, lambda _text: None)
    try:
        with pytest.raises(NonFiniteWireValueError, match="width"):
            handle.initial_node_json()
    finally:
        await handle.close()


# --------------------------------------------------------------------------- #
# Mode B — the WebSocket frame and the SSE frame                               #
# --------------------------------------------------------------------------- #


class RecordingWebSocket:
    """A socket duble recording every frame written to the wire."""

    def __init__(self) -> None:
        """Start connected, with nothing written."""
        self.client_state = WebSocketState.CONNECTED
        self.written: list[str] = []

    async def send_text(self, text: str) -> None:
        """Record one outbound frame."""
        self.written.append(text)


@pytest.mark.asyncio
async def test_mode_b_websocket_writes_nothing_it_cannot_encode() -> None:
    """The frame is encoded before the send, so a bad batch never reaches the wire."""
    socket = RecordingWebSocket()
    transport = WebSocketTransport(socket)  # type: ignore[arg-type]

    with pytest.raises(NonFiniteWireValueError, match=r"data\[0\]\.style\.width"):
        await transport.send_patches([{"style": {"width": float("inf")}}])

    assert socket.written == []
    await transport.send_patches([{"style": {"width": 1.0}}])
    assert json.loads(socket.written[0])["kind"] == "patches"


@pytest.mark.asyncio
async def test_mode_b_sse_refuses_a_frame_json_cannot_express() -> None:
    """SSE carries the same envelopes, so it stops at the same place.

    Unlike the WebSocket, SSE encodes at yield time — ``send_patches`` only
    queues the envelope, because the replay buffer that serves ``Last-Event-ID``
    holds envelopes, not text. The refusal therefore lands on the response body,
    which is still loud: the stream ends instead of writing a frame no browser
    would parse.
    """
    transport = SSETransport()
    stream = transport.stream()
    await transport.send_patches([{"style": {"width": float("nan")}}])
    with pytest.raises(NonFiniteWireValueError, match="width"):
        await anext(stream)
    await stream.aclose()
    await transport.close()
