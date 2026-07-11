"""Unit tests for the Tier-3 native capability Python facades (Track N).

Each capability is driven through a scripted fake bridge that records the outgoing
``native_call`` envelopes and returns a canned result. The tests assert that every
Python awaitable dispatches the right dotted capability with the right args and
unwraps the result dict into the documented Python return shape.
"""

from __future__ import annotations

from typing import Any

import pytest

from tempestweb import native
from tempestweb.native import (
    BluetoothDevice,
    MidiPorts,
    UsbDevice,
    install_bridge,
    uninstall_bridge,
)


class _ScriptedBridge:
    """Fake bridge returning canned values per capability, recording every call."""

    def __init__(self, responses: dict[str, dict[str, Any]]) -> None:
        """Initialize the bridge.

        Args:
            responses: Mapping of dotted capability name to the ``value`` payload
                the browser handler would return.
        """
        self.responses: dict[str, dict[str, Any]] = responses
        self.calls: list[dict[str, Any]] = []

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Record the envelope and return the canned success result.

        Args:
            envelope: The ``native_call`` envelope to dispatch.

        Returns:
            A success result envelope wrapping the scripted value.
        """
        self.calls.append(envelope)
        cap = envelope["capability"]
        return {"ok": True, "value": self.responses.get(cap, {})}


@pytest.fixture(autouse=True)
def _clean_bridge() -> Any:  # noqa: ANN401
    """Ensure each test starts and ends with no bridge installed."""
    uninstall_bridge()
    yield
    uninstall_bridge()


def _install(responses: dict[str, dict[str, Any]]) -> _ScriptedBridge:
    """Install a scripted bridge with the given canned responses.

    Args:
        responses: Mapping of capability name to its canned ``value`` payload.

    Returns:
        The installed bridge, so tests can inspect ``calls``.
    """
    bridge = _ScriptedBridge(responses)
    install_bridge(bridge)
    return bridge


# --- bluetooth -------------------------------------------------------------


async def test_bluetooth_is_supported() -> None:
    bridge = _install({"bluetooth.is_supported": {"supported": True}})
    assert await native.bluetooth.is_supported() is True
    assert bridge.calls[0]["capability"] == "bluetooth.is_supported"
    assert bridge.calls[0]["args"] == {}


async def test_bluetooth_request_defaults() -> None:
    bridge = _install({"bluetooth.request": {"id": "dev-1", "name": "Heart Rate"}})
    result = await native.bluetooth.request()
    assert result == BluetoothDevice(id="dev-1", name="Heart Rate")
    assert bridge.calls[0]["capability"] == "bluetooth.request"
    assert bridge.calls[0]["args"] == {"filters": [], "optional_services": []}


async def test_bluetooth_request_explicit() -> None:
    bridge = _install({"bluetooth.request": {"id": "dev-2", "name": ""}})
    filters: list[dict[str, Any]] = [{"services": ["heart_rate"]}]
    result = await native.bluetooth.request(filters, ["battery_service"])
    assert result == BluetoothDevice(id="dev-2", name="")
    assert bridge.calls[0]["args"] == {
        "filters": filters,
        "optional_services": ["battery_service"],
    }


async def test_bluetooth_read() -> None:
    bridge = _install({"bluetooth.read": {"data_base64": "aGk="}})
    result = await native.bluetooth.read("dev-1", "svc", "char")
    assert result == "aGk="
    assert bridge.calls[0]["capability"] == "bluetooth.read"
    assert bridge.calls[0]["args"] == {
        "id": "dev-1",
        "service": "svc",
        "characteristic": "char",
    }


async def test_bluetooth_write() -> None:
    bridge = _install({"bluetooth.write": {}})
    result = await native.bluetooth.write("dev-1", "svc", "char", "aGk=")
    assert result is None
    assert bridge.calls[0]["capability"] == "bluetooth.write"
    assert bridge.calls[0]["args"] == {
        "id": "dev-1",
        "service": "svc",
        "characteristic": "char",
        "data_base64": "aGk=",
    }


# --- contacts --------------------------------------------------------------


async def test_contacts_is_supported() -> None:
    bridge = _install({"contacts.is_supported": {"supported": False}})
    assert await native.contacts.is_supported() is False
    assert bridge.calls[0]["capability"] == "contacts.is_supported"
    assert bridge.calls[0]["args"] == {}


async def test_contacts_select_defaults() -> None:
    bridge = _install(
        {"contacts.select": {"contacts": [{"name": ["Ana"], "email": ["a@x.com"]}]}}
    )
    result = await native.contacts.select()
    assert result == [{"name": ["Ana"], "email": ["a@x.com"]}]
    assert bridge.calls[0]["capability"] == "contacts.select"
    assert bridge.calls[0]["args"] == {
        "properties": ["name", "email", "tel"],
        "multiple": False,
    }


async def test_contacts_select_explicit() -> None:
    bridge = _install({"contacts.select": {}})
    result = await native.contacts.select(["name"], multiple=True)
    assert result == []
    assert bridge.calls[0]["args"] == {"properties": ["name"], "multiple": True}


# --- eyedropper ------------------------------------------------------------


async def test_eyedropper_open() -> None:
    bridge = _install({"eyedropper.open": {"srgb_hex": "#3366ff"}})
    assert await native.eyedropper.open() == "#3366ff"
    assert bridge.calls[0]["capability"] == "eyedropper.open"
    assert bridge.calls[0]["args"] == {}


async def test_eyedropper_open_cancelled() -> None:
    _install({"eyedropper.open": {}})
    assert await native.eyedropper.open() == ""


# --- gamepad ---------------------------------------------------------------


async def test_gamepad_state() -> None:
    bridge = _install(
        {"gamepad.state": {"gamepads": [{"id": "pad", "axes": [0.0], "buttons": []}]}}
    )
    result = await native.gamepad.state()
    assert result == [{"id": "pad", "axes": [0.0], "buttons": []}]
    assert bridge.calls[0]["capability"] == "gamepad.state"
    assert bridge.calls[0]["args"] == {}


async def test_gamepad_state_empty() -> None:
    _install({"gamepad.state": {}})
    assert await native.gamepad.state() == []


# --- hid -------------------------------------------------------------------


async def test_hid_is_supported() -> None:
    bridge = _install({"hid.is_supported": {"supported": True}})
    assert await native.hid.is_supported() is True
    assert bridge.calls[0]["capability"] == "hid.is_supported"
    assert bridge.calls[0]["args"] == {}


async def test_hid_request_defaults() -> None:
    bridge = _install({"hid.request": {"devices": [{"productName": "Pad"}]}})
    result = await native.hid.request()
    assert result == [{"productName": "Pad"}]
    assert bridge.calls[0]["capability"] == "hid.request"
    assert bridge.calls[0]["args"] == {"filters": []}


async def test_hid_request_explicit() -> None:
    bridge = _install({"hid.request": {}})
    filters: list[dict[str, Any]] = [{"vendorId": 1234}]
    result = await native.hid.request(filters)
    assert result == []
    assert bridge.calls[0]["args"] == {"filters": filters}


# --- midi ------------------------------------------------------------------


async def test_midi_is_supported() -> None:
    bridge = _install({"midi.is_supported": {"supported": True}})
    assert await native.midi.is_supported() is True
    assert bridge.calls[0]["capability"] == "midi.is_supported"
    assert bridge.calls[0]["args"] == {}


async def test_midi_request_access_defaults() -> None:
    bridge = _install(
        {
            "midi.request_access": {
                "inputs": [{"id": "in-1", "name": "Keyboard"}],
                "outputs": [{"id": "out-1", "name": "Synth"}],
            }
        }
    )
    result = await native.midi.request_access()
    assert result == MidiPorts(
        inputs=[{"id": "in-1", "name": "Keyboard"}],
        outputs=[{"id": "out-1", "name": "Synth"}],
    )
    assert bridge.calls[0]["capability"] == "midi.request_access"
    assert bridge.calls[0]["args"] == {"sysex": False}


async def test_midi_request_access_sysex() -> None:
    bridge = _install({"midi.request_access": {}})
    result = await native.midi.request_access(sysex=True)
    assert result == MidiPorts(inputs=[], outputs=[])
    assert bridge.calls[0]["args"] == {"sysex": True}


async def test_midi_send() -> None:
    bridge = _install({"midi.send": {}})
    result = await native.midi.send("out-1", [144, 60, 127])
    assert result is None
    assert bridge.calls[0]["capability"] == "midi.send"
    assert bridge.calls[0]["args"] == {"output_id": "out-1", "data": [144, 60, 127]}


# --- nfc -------------------------------------------------------------------


async def test_nfc_is_supported() -> None:
    bridge = _install({"nfc.is_supported": {"supported": True}})
    assert await native.nfc.is_supported() is True
    assert bridge.calls[0]["capability"] == "nfc.is_supported"
    assert bridge.calls[0]["args"] == {}


async def test_nfc_write() -> None:
    bridge = _install({"nfc.write": {}})
    records: list[dict[str, Any]] = [{"recordType": "text", "data": "hi"}]
    result = await native.nfc.write(records)
    assert result is None
    assert bridge.calls[0]["capability"] == "nfc.write"
    assert bridge.calls[0]["args"] == {"records": records}


# --- payment ---------------------------------------------------------------


async def test_payment_is_supported() -> None:
    bridge = _install({"payment.is_supported": {"supported": True}})
    assert await native.payment.is_supported() is True
    assert bridge.calls[0]["capability"] == "payment.is_supported"
    assert bridge.calls[0]["args"] == {}


async def test_payment_request_defaults() -> None:
    bridge = _install({"payment.request": {"response": {"methodName": "basic-card"}}})
    methods: list[dict[str, Any]] = [{"supportedMethods": "basic-card"}]
    details: dict[str, Any] = {"total": {"label": "Total", "amount": {"value": "1"}}}
    result = await native.payment.request(methods, details)
    assert result == {"methodName": "basic-card"}
    assert bridge.calls[0]["capability"] == "payment.request"
    assert bridge.calls[0]["args"] == {
        "methods": methods,
        "details": details,
        "options": {},
    }


async def test_payment_request_with_options() -> None:
    bridge = _install({"payment.request": {}})
    methods: list[dict[str, Any]] = [{"supportedMethods": "basic-card"}]
    details: dict[str, Any] = {"total": {}}
    options: dict[str, Any] = {"requestShipping": True}
    result = await native.payment.request(methods, details, options)
    assert result == {}
    assert bridge.calls[0]["args"] == {
        "methods": methods,
        "details": details,
        "options": options,
    }


# --- pip -------------------------------------------------------------------


async def test_pip_request_defaults() -> None:
    bridge = _install({"pip.request": {"active": True}})
    assert await native.pip.request() is True
    assert bridge.calls[0]["capability"] == "pip.request"
    assert bridge.calls[0]["args"] == {"selector": "video"}


async def test_pip_request_selector() -> None:
    bridge = _install({"pip.request": {"active": True}})
    assert await native.pip.request("#player") is True
    assert bridge.calls[0]["args"] == {"selector": "#player"}


async def test_pip_exit() -> None:
    bridge = _install({"pip.exit": {"active": False}})
    assert await native.pip.exit() is False
    assert bridge.calls[0]["capability"] == "pip.exit"
    assert bridge.calls[0]["args"] == {}


# --- pointerlock -----------------------------------------------------------


async def test_pointerlock_request_defaults() -> None:
    bridge = _install({"pointerlock.request": {}})
    result = await native.pointerlock.request()
    assert result is None
    assert bridge.calls[0]["capability"] == "pointerlock.request"
    assert bridge.calls[0]["args"] == {"selector": ""}


async def test_pointerlock_request_selector() -> None:
    bridge = _install({"pointerlock.request": {}})
    await native.pointerlock.request("#canvas")
    assert bridge.calls[0]["args"] == {"selector": "#canvas"}


async def test_pointerlock_exit() -> None:
    bridge = _install({"pointerlock.exit": {}})
    result = await native.pointerlock.exit()
    assert result is None
    assert bridge.calls[0]["capability"] == "pointerlock.exit"
    assert bridge.calls[0]["args"] == {}


# --- serial ----------------------------------------------------------------


async def test_serial_is_supported() -> None:
    bridge = _install({"serial.is_supported": {"supported": True}})
    assert await native.serial.is_supported() is True
    assert bridge.calls[0]["capability"] == "serial.is_supported"
    assert bridge.calls[0]["args"] == {}


async def test_serial_request_defaults() -> None:
    bridge = _install({"serial.request": {"id": "port-1"}})
    assert await native.serial.request() == "port-1"
    assert bridge.calls[0]["capability"] == "serial.request"
    assert bridge.calls[0]["args"] == {"filters": []}


async def test_serial_request_filters() -> None:
    bridge = _install({"serial.request": {"id": "port-2"}})
    filters: list[dict[str, Any]] = [{"usbVendorId": 4660}]
    assert await native.serial.request(filters) == "port-2"
    assert bridge.calls[0]["args"] == {"filters": filters}


# --- usb -------------------------------------------------------------------


async def test_usb_is_supported() -> None:
    bridge = _install({"usb.is_supported": {"supported": True}})
    assert await native.usb.is_supported() is True
    assert bridge.calls[0]["capability"] == "usb.is_supported"
    assert bridge.calls[0]["args"] == {}


async def test_usb_request_defaults() -> None:
    bridge = _install(
        {
            "usb.request": {
                "id": "usb-1",
                "vendor_id": 4660,
                "product_id": 22136,
                "product_name": "Widget",
            }
        }
    )
    result = await native.usb.request()
    assert result == UsbDevice(
        id="usb-1",
        vendor_id=4660,
        product_id=22136,
        product_name="Widget",
    )
    assert bridge.calls[0]["capability"] == "usb.request"
    assert bridge.calls[0]["args"] == {"filters": []}


async def test_usb_request_filters() -> None:
    bridge = _install({"usb.request": {}})
    filters: list[dict[str, Any]] = [{"vendorId": 4660}]
    result = await native.usb.request(filters)
    assert result == UsbDevice(id="", vendor_id=0, product_id=0, product_name="")
    assert bridge.calls[0]["args"] == {"filters": filters}


# --- webaudio --------------------------------------------------------------


async def test_webaudio_tone_defaults() -> None:
    bridge = _install({"webaudio.tone": {}})
    result = await native.webaudio.tone()
    assert result is None
    assert bridge.calls[0]["capability"] == "webaudio.tone"
    assert bridge.calls[0]["args"] == {
        "frequency": 440.0,
        "duration_ms": 200,
        "type": "sine",
        "volume": 0.5,
    }


async def test_webaudio_tone_explicit() -> None:
    bridge = _install({"webaudio.tone": {}})
    await native.webaudio.tone(880.0, 500, "square", 0.25)
    assert bridge.calls[0]["args"] == {
        "frequency": 880.0,
        "duration_ms": 500,
        "type": "square",
        "volume": 0.25,
    }
