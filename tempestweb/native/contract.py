"""The native-capability contract — a single source of truth (Track N / N-C4).

Every native capability is a dotted name (``"http.request"``) implemented across
three surfaces that must agree:

* the **Python awaitable** wrapper (``tempestweb.native.http.request``, …),
* the browser **handler** registered in ``client/native/index.js`` (``HANDLERS``),
* the **Mode C facade** in ``client/transpile/native.js`` (the subset a
  transpiled, Python-free app can call in-process).

This module pins that agreement. :data:`CAPABILITIES` is the canonical set; each
:class:`Capability` records its group, whether it mutates or reads, and whether it
is exposed in the Mode C facade. Conformance tests (``tests/unit/
test_native_contract.py`` and ``tests/client/native.test.js``) assert the JS
surfaces match this contract, so a capability added to one surface but not the
others fails CI.

It lives here (platform layer), not in ``tempest_core`` (pure, renderer-agnostic).
It is the extraction candidate for a shared contract that ``tempestroid`` (mobile)
could mirror — see docs/native-modo-c.md (N-C4).
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "CAPABILITIES",
    "MODE_C_CAPABILITIES",
    "STREAMING_CAPABILITIES",
    "Capability",
    "capability_names",
    "mode_c_capability_names",
    "single_shot_capability_names",
    "streaming_capability_names",
]


@dataclass(frozen=True)
class Capability:
    """One native capability's contract entry.

    Attributes:
        name: The dotted capability name (``"group.verb"``), the dispatch key.
        group: The namespace it belongs to (``"http"``, ``"storage"``, …).
        mode_c: Whether the Mode C facade (``client/transpile/native.js``) exposes
            it — i.e. a transpiled, Python-free app can call it in-process.
        streaming: Whether it is a **streaming** capability served over the native
            event channel (T-EV) — many events per subscription — rather than a
            single-shot request/response call. Streaming capabilities register in
            the client's ``EVENT_HANDLERS`` (not ``HANDLERS``) and, in Python, are
            consumed via :func:`~tempestweb.native.native_events` /
            ``async for`` rather than ``await``.
    """

    name: str
    group: str
    mode_c: bool
    streaming: bool


def _cap(name: str, *, mode_c: bool = False, streaming: bool = False) -> Capability:
    """Build a :class:`Capability`, deriving its group from the dotted name."""
    group, _, _verb = name.partition(".")
    return Capability(name=name, group=group, mode_c=mode_c, streaming=streaming)


#: Every native capability, in dispatch-name order. The ``mode_c`` capabilities
#: are the subset the transpile facade serves in-process (no Python, no bridge).
CAPABILITIES: tuple[Capability, ...] = (
    _cap("audio.play", mode_c=True),
    _cap("audio.stop", mode_c=True),
    _cap("badge.clear", mode_c=True),
    _cap("badge.set", mode_c=True),
    _cap("battery.watch", mode_c=True, streaming=True),
    _cap("bgsync.register", mode_c=True),
    _cap("bgsync.register_periodic", mode_c=True),
    _cap("bluetooth.is_supported", mode_c=True),
    _cap("bluetooth.read", mode_c=True),
    _cap("bluetooth.request", mode_c=True),
    _cap("bluetooth.write", mode_c=True),
    _cap("camera.capture"),
    _cap("clipboard.read", mode_c=True),
    _cap("clipboard.read_image", mode_c=True),
    _cap("clipboard.write", mode_c=True),
    _cap("clipboard.write_image", mode_c=True),
    _cap("contacts.is_supported", mode_c=True),
    _cap("contacts.select", mode_c=True),
    _cap("cookies.all", mode_c=True),
    _cap("cookies.get", mode_c=True),
    _cap("cookies.remove", mode_c=True),
    _cap("cookies.set", mode_c=True),
    _cap("eyedropper.open", mode_c=True),
    _cap("file.pick", mode_c=True),
    _cap("file.save", mode_c=True),
    _cap("filesystem.open_file", mode_c=True),
    _cap("filesystem.save_file", mode_c=True),
    _cap("filesystem.write_file", mode_c=True),
    _cap("fullscreen.enter", mode_c=True),
    _cap("fullscreen.exit", mode_c=True),
    _cap("fullscreen.state", mode_c=True),
    _cap("gamepad.state", mode_c=True),
    _cap("gamepad.watch", mode_c=True, streaming=True),
    _cap("geolocation.get", mode_c=True),
    _cap("geolocation.watch", mode_c=True, streaming=True),
    _cap("hid.is_supported", mode_c=True),
    _cap("hid.request", mode_c=True),
    _cap("http.request", mode_c=True),
    _cap("http.upload", mode_c=True),
    _cap("idle.watch", mode_c=True, streaming=True),
    _cap("install.prompt", mode_c=True),
    _cap("install.state", mode_c=True),
    _cap("midi.is_supported", mode_c=True),
    _cap("midi.messages", mode_c=True, streaming=True),
    _cap("midi.request_access", mode_c=True),
    _cap("midi.send", mode_c=True),
    _cap("network.state", mode_c=True),
    _cap("network.watch", mode_c=True, streaming=True),
    _cap("nfc.is_supported", mode_c=True),
    _cap("nfc.scan", mode_c=True, streaming=True),
    _cap("nfc.write", mode_c=True),
    _cap("offline.enqueue", mode_c=True),
    _cap("offline.pending", mode_c=True),
    _cap("offline.replay", mode_c=True),
    _cap("offline.size", mode_c=True),
    _cap("offline.failed", mode_c=True),
    _cap("offline.conflicts", mode_c=True),
    _cap("notifications.notify", mode_c=True),
    _cap("notifications.push_state", mode_c=True),
    _cap("notifications.request_permission", mode_c=True),
    _cap("notifications.subscribe", mode_c=True),
    _cap("notifications.unsubscribe", mode_c=True),
    _cap("onnx.load"),
    _cap("onnx.run"),
    _cap("orientation.lock", mode_c=True),
    _cap("orientation.state", mode_c=True),
    _cap("orientation.unlock", mode_c=True),
    _cap("orientation.watch", mode_c=True, streaming=True),
    _cap("payment.is_supported", mode_c=True),
    _cap("payment.request", mode_c=True),
    _cap("pip.exit", mode_c=True),
    _cap("pip.request", mode_c=True),
    _cap("pointerlock.exit", mode_c=True),
    _cap("pointerlock.request", mode_c=True),
    _cap("quota.estimate", mode_c=True),
    _cap("quota.persist", mode_c=True),
    _cap("quota.persisted", mode_c=True),
    _cap("recorder.start", mode_c=True),
    _cap("recorder.stop", mode_c=True),
    _cap("sensors.motion", mode_c=True, streaming=True),
    _cap("sensors.orientation", mode_c=True, streaming=True),
    _cap("serial.is_supported", mode_c=True),
    _cap("serial.request", mode_c=True),
    _cap("share.is_supported", mode_c=True),
    _cap("share.share", mode_c=True),
    _cap("speech.cancel", mode_c=True),
    _cap("speech.listen", mode_c=True, streaming=True),
    _cap("speech.speak", mode_c=True),
    _cap("speech.voices", mode_c=True),
    _cap("storage.get", mode_c=True),
    _cap("storage.list", mode_c=True),
    _cap("storage.put", mode_c=True),
    _cap("storage.remove", mode_c=True),
    _cap("tabs.broadcast", mode_c=True),
    _cap("tabs.lock", mode_c=True),
    _cap("tabs.receive", mode_c=True, streaming=True),
    _cap("tabs.unlock", mode_c=True),
    _cap("usb.is_supported", mode_c=True),
    _cap("usb.request", mode_c=True),
    _cap("vibration.vibrate", mode_c=True),
    _cap("visibility.state", mode_c=True),
    _cap("visibility.watch", mode_c=True, streaming=True),
    _cap("wakelock.release", mode_c=True),
    _cap("wakelock.request", mode_c=True),
    _cap("webaudio.tone", mode_c=True),
    _cap("webauthn.create", mode_c=True),
    _cap("webauthn.get", mode_c=True),
    _cap("webauthn.get_otp", mode_c=True),
)

#: The Mode-C-exposed capabilities (a subset of :data:`CAPABILITIES`).
MODE_C_CAPABILITIES: tuple[Capability, ...] = tuple(
    cap for cap in CAPABILITIES if cap.mode_c
)

#: The streaming capabilities served over the native event channel (T-EV).
STREAMING_CAPABILITIES: tuple[Capability, ...] = tuple(
    cap for cap in CAPABILITIES if cap.streaming
)


def capability_names() -> frozenset[str]:
    """Return the full set of dotted capability names.

    Returns:
        Every capability's ``name``, as a set for order-agnostic comparison.
    """
    return frozenset(cap.name for cap in CAPABILITIES)


def mode_c_capability_names() -> frozenset[str]:
    """Return the set of dotted names the Mode C facade exposes.

    Returns:
        The ``mode_c`` capabilities' names, as a set.
    """
    return frozenset(cap.name for cap in MODE_C_CAPABILITIES)


def streaming_capability_names() -> frozenset[str]:
    """Return the set of streaming (event-channel) capability names.

    Returns:
        The ``streaming`` capabilities' names, as a set. These register in the
        client's ``EVENT_HANDLERS`` rather than ``HANDLERS``.
    """
    return frozenset(cap.name for cap in STREAMING_CAPABILITIES)


def single_shot_capability_names() -> frozenset[str]:
    """Return the set of single-shot (request/response) capability names.

    Returns:
        Every non-streaming capability's ``name`` — the ones the client serves
        from its ``HANDLERS`` registry.
    """
    return frozenset(cap.name for cap in CAPABILITIES if not cap.streaming)
