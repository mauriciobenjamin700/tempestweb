"""Dispatch native Web-capability commands across the client/Python seam (A5).

Native Web capabilities (geolocation, clipboard, notifications, storage) are the
web sibling of :mod:`tempestroid.native`. They split into two shapes over a single
abstraction — the :class:`NativeBridge` — exactly as the renderer's patches do:

* **Fire-and-forget** — a one-way ``{"kind": "native", ...}`` envelope (e.g.
  ``notify``, clipboard ``set``). :func:`native_command` builds it;
  :func:`send_native` ships it. No reply.
* **Request/response** — a capability that returns a value (geolocation fix,
  clipboard read, storage read/list). :func:`send_native_request` ships an
  envelope carrying a ``request_id`` and awaits the bridge for the result.

The capability modules never know *which* execution mode they run under — they
call :func:`send_native`/:func:`send_native_request` and the installed
:class:`NativeBridge` decides how the envelope reaches the Web API. **That single
seam is the whole Mode-A vs Mode-B split:**

* **Mode A (WASM / browser).** Python runs in the browser under Pyodide. The
  installed bridge is an in-process FFI bridge: it hands the envelope straight to
  ``client/native.js``, which calls ``navigator.geolocation``,
  ``navigator.clipboard``, ``Notification``, ``localStorage`` directly. A
  request/response result comes back as the resolved value of the FFI promise —
  no network hop.

* **Mode B (server).** Python runs on the server; the browser is a thin client
  reached over a WebSocket. The installed bridge serializes the envelope and
  ships it down the existing patch transport (a "native" frame), then suspends on
  an :class:`asyncio.Future`. ``client/native.js`` runs the same
  ``navigator.*`` call in the browser and posts a result frame back up the
  socket; :func:`resolve_native_request` matches it to the pending future by
  ``request_id``. **The Web API always executes in the browser** — Mode B simply
  proxies the call there and back over one WS round-trip.

The envelope builders are pure (and therefore trivially testable); the bridge is
injected with :func:`install_bridge`, so this module imports cleanly with no
browser, no Pyodide, and no server present.
"""

from __future__ import annotations

import asyncio
import itertools
from typing import Any, Protocol, cast, runtime_checkable

__all__ = [
    "NATIVE_RESULT_PREFIX",
    "BrowserUnavailableError",
    "NativeBridge",
    "NativeError",
    "current_bridge",
    "install_bridge",
    "native_command",
    "native_request",
    "resolve_native_request",
    "send_native",
    "send_native_request",
    "uninstall_bridge",
]

#: Reserved token prefix the client uses (over the event channel, in Mode B) to
#: deliver a native request/response result back to its matching pending future.
NATIVE_RESULT_PREFIX = "__native_result__:"

#: Monotonic source of request ids (deterministic; avoids ``random``/``uuid`` so
#: envelopes are reproducible in tests).
_request_ids: itertools.count[int] = itertools.count(1)


class NativeError(RuntimeError):
    """A native Web-capability call failed in the browser.

    Attributes:
        code: A short machine-readable error code (e.g. ``"permission_denied"``,
            ``"unavailable"``, ``"not_found"``, ``"insecure_context"``).
    """

    def __init__(self, code: str, message: str = "") -> None:
        """Initialize the error.

        Args:
            code: The machine-readable error code.
            message: A human-readable detail (optional).
        """
        self.code: str = code
        super().__init__(f"{code}: {message}" if message else code)


class BrowserUnavailableError(RuntimeError):
    """Raised when a native call is made with no :class:`NativeBridge` installed.

    The capability modules always reach the browser through an installed bridge.
    Off-platform (a plain Python process, a unit test that forgot to install a
    bridge), there is no browser to call, so dispatch fails fast with this error
    instead of silently no-op-ing.
    """


@runtime_checkable
class NativeBridge(Protocol):
    """The seam between a native capability and the browser's Web API.

    A bridge is installed once per running app (Mode A or Mode B) via
    :func:`install_bridge`. The capability modules call :meth:`send` and
    :meth:`request` without knowing which concrete bridge backs them.

    Implementations must be safe to drive from an asyncio event loop.
    """

    def send(self, envelope: dict[str, Any]) -> None:
        """Deliver a fire-and-forget native envelope to the browser.

        Args:
            envelope: A ``native_command`` envelope. Must reach a ``navigator.*``
                (or equivalent) call in the browser; no reply is expected.
        """
        ...

    async def request(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Deliver a request/response native envelope and await its result.

        Args:
            envelope: A ``native_request`` envelope carrying a ``request_id``.

        Returns:
            The result envelope ``{"ok": bool, "data"/"error"/"message": ...}``
            as produced by ``client/native.js``.

        Raises:
            BrowserUnavailableError: If the browser channel is gone.
        """
        ...


#: The process-wide installed bridge, or ``None`` off-platform.
_bridge: NativeBridge | None = None


def install_bridge(bridge: NativeBridge) -> None:
    """Install the process-wide native bridge for the current execution mode.

    Called once during app bootstrap — by the WASM runtime (Mode A) with an
    in-process FFI bridge, or by the server session (Mode B) with a transport
    bridge.

    Args:
        bridge: The :class:`NativeBridge` implementation to route native calls
            through.
    """
    global _bridge
    _bridge = bridge


def uninstall_bridge() -> None:
    """Remove the installed bridge, restoring the off-platform state.

    Used by tests and by session teardown so a stale bridge never leaks across
    apps.
    """
    global _bridge
    _bridge = None


def current_bridge() -> NativeBridge:
    """Return the installed bridge, raising if none is present.

    Returns:
        The process-wide :class:`NativeBridge`.

    Raises:
        BrowserUnavailableError: If no bridge has been installed.
    """
    if _bridge is None:
        raise BrowserUnavailableError(
            "no native bridge installed (off-platform, or bootstrap incomplete)"
        )
    return _bridge


def native_command(module: str, action: str, args: dict[str, Any]) -> dict[str, Any]:
    """Build a fire-and-forget native-command envelope.

    Args:
        module: The native module name (e.g. ``"notifications"``).
        action: The action on that module (e.g. ``"notify"``).
        args: JSON-able arguments for the action.

    Returns:
        The serializable command envelope.
    """
    return {"kind": "native", "module": module, "action": action, "args": args}


def native_request(
    module: str, action: str, args: dict[str, Any], request_id: str
) -> dict[str, Any]:
    """Build a request/response native-command envelope.

    Args:
        module: The native module name (e.g. ``"geolocation"``).
        action: The action on that module (e.g. ``"get_position"``).
        args: JSON-able arguments for the action.
        request_id: The correlation id the client echoes back with the result.

    Returns:
        The serializable command envelope, carrying ``request_id``.
    """
    return {
        "kind": "native",
        "module": module,
        "action": action,
        "args": args,
        "request_id": request_id,
    }


def send_native(module: str, action: str, args: dict[str, Any]) -> None:
    """Send a fire-and-forget native command to the browser.

    Args:
        module: The native module name.
        action: The action on that module.
        args: JSON-able arguments for the action.

    Raises:
        BrowserUnavailableError: If no bridge is installed (off-platform).
    """
    current_bridge().send(native_command(module, action, args))


async def send_native_request(
    module: str, action: str, args: dict[str, Any]
) -> dict[str, Any]:
    """Send a request/response native command and await the browser's result.

    Builds an envelope with a fresh ``request_id``, hands it to the installed
    bridge, and unwraps the result: a successful ``data`` payload is returned;
    a failure (``ok`` is false) is raised as :class:`NativeError`. Must be called
    from the asyncio loop the app runs on (i.e. inside a widget handler).

    Args:
        module: The native module name.
        action: The action on that module.
        args: JSON-able arguments for the action.

    Returns:
        The ``data`` payload of a successful result.

    Raises:
        BrowserUnavailableError: If no bridge is installed (off-platform).
        NativeError: If the browser reports the call failed (``ok`` is false).
    """
    request_id = str(next(_request_ids))
    result = await current_bridge().request(
        native_request(module, action, args, request_id)
    )
    if not result.get("ok", False):
        raise NativeError(
            str(result.get("error", "unknown")),
            str(result.get("message", "")),
        )
    data = result.get("data", {})
    return cast("dict[str, Any]", data) if isinstance(data, dict) else {}


def resolve_native_request(
    request_id: str,
    payload: dict[str, Any],
    pending: dict[str, asyncio.Future[dict[str, Any]]],
) -> bool:
    """Resolve a pending native request with the client's result payload (Mode B).

    Called (on the loop thread) by a Mode-B transport bridge when a result frame
    tagged with :data:`NATIVE_RESULT_PREFIX` + ``request_id`` arrives back over
    the socket. Mode A has no use for this — its FFI bridge resolves its own
    promise inline.

    Args:
        request_id: The correlation id parsed from the result frame.
        payload: The result envelope (``{"ok": ..., "data"/"error": ...}``).
        pending: The bridge's ``request_id -> Future`` registry.

    Returns:
        ``True`` if a matching pending future was resolved, ``False`` otherwise
        (unknown or already-settled id).
    """
    future = pending.get(request_id)
    if future is None or future.done():
        return False
    future.set_result(payload)
    return True
