"""Native MIDI capability over the Web MIDI API.

:func:`request_access` sends a ``midi.request_access`` ``native_call`` and gets
back the available input/output ports; ``client/native/midi.js`` calls
``navigator.requestMIDIAccess`` and returns the enumerated ports, holding the live
``MIDIOutput`` objects in a registry keyed by port id. :func:`send` sends
``midi.send`` with an output id so the client can dispatch the bytes to the matching
port. The port shape is browser-defined, so ports pass through as ``dict[str, Any]``
within the :class:`MidiPorts` result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from tempestweb.native.dispatch import send_native_call

__all__ = ["MidiPorts", "is_supported", "request_access", "send"]


@dataclass(frozen=True)
class MidiPorts:
    """The MIDI input and output ports exposed by the Web MIDI API.

    Attributes:
        inputs: The available input ports as JSON-able dicts (id, name, …).
        outputs: The available output ports as JSON-able dicts; the client holds
            the live ``MIDIOutput`` objects keyed by their id.
    """

    inputs: list[dict[str, Any]]
    outputs: list[dict[str, Any]]


async def is_supported() -> bool:
    """Report whether the Web MIDI API is available.

    Returns:
        ``True`` if the browser exposes ``navigator.requestMIDIAccess``.

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("midi.is_supported", {})
    return bool(value.get("supported", False))


async def request_access(sysex: bool = False) -> MidiPorts:
    """Request access to the system's MIDI ports.

    Args:
        sysex: Whether to request permission to send and receive system-exclusive
            messages.

    Returns:
        The available :class:`MidiPorts` (empty lists when no ports exist).

    Raises:
        NativeError: If the API is unavailable (``unavailable``) or access is
            refused (``permission_denied``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("midi.request_access", {"sysex": sysex})
    return MidiPorts(
        inputs=cast("list[dict[str, Any]]", value.get("inputs", [])),
        outputs=cast("list[dict[str, Any]]", value.get("outputs", [])),
    )


async def send(output_id: str, data: list[int]) -> None:
    """Send a MIDI message to an output port.

    Args:
        output_id: The id of an output port from :func:`request_access`.
        data: The MIDI message bytes (0-255 each).

    Raises:
        NativeError: If the output id is unknown (``not_found``) or the API is
            unavailable (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    await send_native_call("midi.send", {"output_id": output_id, "data": data})
