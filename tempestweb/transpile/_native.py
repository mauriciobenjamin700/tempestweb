"""GENERATED from the Mode C client and the native package.

Regenerate: ``python -m tests.conformance._transpile_native``.

The shape of the native facade ``client/transpile/native.js`` exposes, plus how
a bare name re-exported by ``tempestweb.native`` resolves onto it. The compiler
maps every import form onto the same facade and refuses an unknown member by its
own name. Do not edit by hand.
"""

from __future__ import annotations

from collections.abc import Mapping

__all__: list[str] = [
    "NATIVE_ENUMS",
    "NATIVE_EXPORTS",
    "NATIVE_FLAT",
    "NATIVE_GROUPS",
    "NATIVE_MEMBERS",
    "NATIVE_TYPES",
]

#: Top-level exports of ``native.js`` — importable straight from the module.
NATIVE_EXPORTS: frozenset[str] = frozenset(
    {
        "NativeError",
        "native",
    }
)

#: Facade group to the members it serves, by generation from the JS itself.
NATIVE_MEMBERS: Mapping[str, frozenset[str]] = {
    "audio": frozenset(
        {
            "play",
            "stop",
        }
    ),
    "badge": frozenset(
        {
            "clear",
            "set",
        }
    ),
    "battery": frozenset(
        {
            "watch",
        }
    ),
    "bgsync": frozenset(
        {
            "register",
            "register_periodic",
        }
    ),
    "bluetooth": frozenset(
        {
            "is_supported",
            "read",
            "request",
            "write",
        }
    ),
    "clipboard": frozenset(
        {
            "read",
            "read_image",
            "write",
            "write_image",
        }
    ),
    "contacts": frozenset(
        {
            "is_supported",
            "select",
        }
    ),
    "cookies": frozenset(
        {
            "all",
            "get",
            "remove",
            "set",
        }
    ),
    "device": frozenset(
        {
            "profile",
        }
    ),
    "eyedropper": frozenset(
        {
            "open",
        }
    ),
    "file": frozenset(
        {
            "pick",
            "save",
        }
    ),
    "filesystem": frozenset(
        {
            "open_file",
            "save_file",
            "write_file",
        }
    ),
    "fullscreen": frozenset(
        {
            "enter",
            "exit",
            "state",
        }
    ),
    "gamepad": frozenset(
        {
            "state",
            "watch",
        }
    ),
    "geolocation": frozenset(
        {
            "get_position",
            "watch",
        }
    ),
    "hid": frozenset(
        {
            "is_supported",
            "request",
        }
    ),
    "http": frozenset(
        {
            "request",
            "upload",
        }
    ),
    "idle": frozenset(
        {
            "watch",
        }
    ),
    "install": frozenset(
        {
            "prompt",
            "state",
        }
    ),
    "midi": frozenset(
        {
            "is_supported",
            "messages",
            "request_access",
            "send",
        }
    ),
    "network": frozenset(
        {
            "state",
            "watch",
        }
    ),
    "nfc": frozenset(
        {
            "is_supported",
            "scan",
            "write",
        }
    ),
    "notifications": frozenset(
        {
            "notify",
            "push_state",
            "request_permission",
            "subscribe",
            "unsubscribe",
        }
    ),
    "offline": frozenset(
        {
            "conflicts",
            "enqueue",
            "failed",
            "pending",
            "replay",
            "size",
        }
    ),
    "orientation": frozenset(
        {
            "lock",
            "state",
            "unlock",
            "watch",
        }
    ),
    "payment": frozenset(
        {
            "is_supported",
            "request",
        }
    ),
    "pip": frozenset(
        {
            "exit",
            "request",
        }
    ),
    "pointerlock": frozenset(
        {
            "exit",
            "request",
        }
    ),
    "quota": frozenset(
        {
            "estimate",
            "persist",
            "persisted",
        }
    ),
    "recorder": frozenset(
        {
            "start",
            "stop",
        }
    ),
    "sensors": frozenset(
        {
            "motion",
            "orientation",
        }
    ),
    "serial": frozenset(
        {
            "is_supported",
            "request",
        }
    ),
    "share": frozenset(
        {
            "is_supported",
            "share",
        }
    ),
    "speech": frozenset(
        {
            "cancel",
            "listen",
            "speak",
            "voices",
        }
    ),
    "storage": frozenset(
        {
            "configure",
            "get",
            "list_keys",
            "put",
            "remove",
        }
    ),
    "sync": frozenset(
        {
            "configure",
            "now",
            "status",
            "watch",
        }
    ),
    "tabs": frozenset(
        {
            "broadcast",
            "lock",
            "receive",
            "unlock",
        }
    ),
    "usb": frozenset(
        {
            "is_supported",
            "request",
        }
    ),
    "vibration": frozenset(
        {
            "vibrate",
        }
    ),
    "visibility": frozenset(
        {
            "state",
            "watch",
        }
    ),
    "wakelock": frozenset(
        {
            "release",
            "request",
        }
    ),
    "webaudio": frozenset(
        {
            "sequence",
            "stop",
            "tone",
            "watch_levels",
        }
    ),
    "webauthn": frozenset(
        {
            "create",
            "get",
            "get_otp",
        }
    ),
}

#: Bare name re-exported by ``tempestweb.native`` to its ``group.member`` path.
NATIVE_FLAT: Mapping[str, str] = {
    "get_position": "geolocation.get_position",
    "list_keys": "storage.list_keys",
    "notify": "notifications.notify",
    "push_state": "notifications.push_state",
    "put": "storage.put",
    "read": "clipboard.read",
    "remove": "storage.remove",
    "request": "http.request",
    "request_permission": "notifications.request_permission",
    "share": "share.share",
    "subscribe": "notifications.subscribe",
    "unsubscribe": "notifications.unsubscribe",
    "upload": "http.upload",
    "write": "clipboard.write",
}

#: Group to the classes it exports, which carry no runtime value in Mode C:
#: the facade returns plain objects, so these names are annotation-only.
NATIVE_TYPES: Mapping[str, frozenset[str]] = {
    "audio": frozenset(
        {
            "PlayResult",
        }
    ),
    "battery": frozenset(
        {
            "BatteryStatus",
        }
    ),
    "bluetooth": frozenset(
        {
            "BluetoothDevice",
        }
    ),
    "bridges": frozenset(
        {
            "FFIBridge",
            "ProxyBridge",
        }
    ),
    "camera": frozenset(
        {
            "Photo",
        }
    ),
    "clipboard": frozenset(
        {
            "ClipboardImage",
        }
    ),
    "contract": frozenset(
        {
            "Capability",
        }
    ),
    "dispatch": frozenset(
        {
            "BrowserUnavailableError",
            "EventBridge",
            "NativeBridge",
            "NativeError",
        }
    ),
    "file": frozenset(
        {
            "PickedFile",
            "SaveResult",
        }
    ),
    "filesystem": frozenset(
        {
            "FileHandle",
        }
    ),
    "geolocation": frozenset(
        {
            "Position",
        }
    ),
    "http": frozenset(
        {
            "HttpResponse",
            "RetryOptions",
        }
    ),
    "idle": frozenset(
        {
            "IdleState",
        }
    ),
    "install": frozenset(
        {
            "InstallState",
        }
    ),
    "midi": frozenset(
        {
            "MidiMessage",
            "MidiPorts",
        }
    ),
    "network": frozenset(
        {
            "NetworkState",
        }
    ),
    "nfc": frozenset(
        {
            "NdefMessage",
        }
    ),
    "notifications": frozenset(
        {
            "NotificationPermission",
            "PushState",
        }
    ),
    "offline": frozenset(
        {
            "Mutation",
            "ReplayResult",
        }
    ),
    "onnx": frozenset(
        {
            "OnnxModel",
            "Tensor",
        }
    ),
    "orientation": frozenset(
        {
            "OrientationState",
        }
    ),
    "quota": frozenset(
        {
            "StorageEstimate",
        }
    ),
    "recorder": frozenset(
        {
            "Recording",
        }
    ),
    "sensors": frozenset(
        {
            "DeviceOrientation",
            "Motion",
        }
    ),
    "share": frozenset(
        {
            "ShareOutcome",
            "ShareResult",
        }
    ),
    "speech": frozenset(
        {
            "SpeechResult",
            "Voice",
        }
    ),
    "sync": frozenset(
        {
            "SyncState",
            "SyncSummary",
        }
    ),
    "usb": frozenset(
        {
            "UsbDevice",
        }
    ),
    "webaudio": frozenset(
        {
            "Level",
            "SequenceResult",
            "Step",
        }
    ),
}

#: String enum the package exports to its members. The facade speaks JSON, so
#: these cross the wire as their value and Mode C emits them as a frozen table.
NATIVE_ENUMS: Mapping[str, Mapping[str, str]] = {
    "NotificationPermission": {
        "DEFAULT": "default",
        "DENIED": "denied",
        "GRANTED": "granted",
    },
    "ShareOutcome": {
        "CANCELLED": "cancelled",
        "SHARED": "shared",
        "UNSUPPORTED": "unsupported",
    },
}

#: Every capability group the Python package has, served or not — so a real
#: group the facade does not carry is refused by name instead of by module.
NATIVE_GROUPS: frozenset[str] = frozenset(
    {
        "audio",
        "badge",
        "battery",
        "bgsync",
        "bluetooth",
        "bridges",
        "camera",
        "clipboard",
        "contacts",
        "contract",
        "cookies",
        "device",
        "dispatch",
        "eyedropper",
        "file",
        "filesystem",
        "fullscreen",
        "gamepad",
        "geolocation",
        "hid",
        "http",
        "idle",
        "install",
        "midi",
        "network",
        "nfc",
        "notifications",
        "offline",
        "onnx",
        "orientation",
        "payment",
        "pip",
        "pointerlock",
        "quota",
        "recorder",
        "sensors",
        "serial",
        "share",
        "speech",
        "storage",
        "sync",
        "tabs",
        "usb",
        "vibration",
        "visibility",
        "wakelock",
        "webaudio",
        "webauthn",
    }
)
