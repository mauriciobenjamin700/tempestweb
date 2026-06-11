"""tempestweb.native — typed Python wrappers over browser Web APIs (A5).

The web sibling of ``tempestroid.native``: each device/web capability is a typed
Python awaitable that application code calls without caring whether its Python
runs in the browser (Mode A / WASM) or on the server (Mode B). The single seam
that differs between the modes is the installed :class:`NativeBridge` — see
:mod:`tempestweb.native.dispatch` for the full Mode-A vs Mode-B explanation and
``client/native.js`` for the browser glue calling ``navigator.*``.

Capabilities (names mirror tempestroid where they map):

* **geolocation** — :func:`get_position` → :class:`Position`.
* **clipboard** — :func:`set_text` (fire-and-forget), :func:`get_text`.
* **notifications** — :func:`notify` (fire-and-forget),
  :func:`request_permission` → :class:`NotificationPermission`.
* **storage** — :func:`read_file` / :func:`write_file` / :func:`delete_file` /
  :func:`list_files` (backed by ``localStorage``).
"""

from tempestweb.native.bridges import FFIBridge, ProxyBridge
from tempestweb.native.clipboard import get_text, set_text
from tempestweb.native.dispatch import (
    NATIVE_RESULT_PREFIX,
    BrowserUnavailableError,
    NativeBridge,
    NativeError,
    current_bridge,
    install_bridge,
    native_command,
    native_request,
    resolve_native_request,
    send_native,
    send_native_request,
    uninstall_bridge,
)
from tempestweb.native.geolocation import Position, get_position
from tempestweb.native.notifications import (
    NotificationPermission,
    notify,
    request_permission,
)
from tempestweb.native.storage import (
    delete_file,
    list_files,
    read_file,
    write_file,
)

__all__ = [
    # dispatch core + bridges (the Mode-A vs Mode-B seam)
    "NATIVE_RESULT_PREFIX",
    "BrowserUnavailableError",
    "FFIBridge",
    "NativeBridge",
    "NativeError",
    "ProxyBridge",
    "current_bridge",
    "install_bridge",
    "native_command",
    "native_request",
    "resolve_native_request",
    "send_native",
    "send_native_request",
    "uninstall_bridge",
    # geolocation
    "Position",
    "get_position",
    # clipboard
    "get_text",
    "set_text",
    # notifications
    "NotificationPermission",
    "notify",
    "request_permission",
    # storage
    "delete_file",
    "list_files",
    "read_file",
    "write_file",
]
