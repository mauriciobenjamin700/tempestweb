"""Dispatch native Web-capability calls across the client/Python seam (Track N).

Native Web capabilities (``http``, ``audio``, ``share``, ``geolocation``,
``clipboard``, ``storage``, ``camera``, ``notifications``) are the web sibling of
:mod:`tempestroid.native`. Every capability is a **typed Python awaitable** that
application code calls without caring which execution mode it runs under. The one
seam that differs between the modes is the installed :class:`NativeBridge`. **That
single seam is the whole Mode-A vs Mode-B split:**

* **Mode A (WASM / browser).** Python runs in the browser under Pyodide. The
  installed bridge is an in-process FFI bridge
  (:class:`~tempestweb.native.bridges.FFIBridge`): it hands the call straight to
  ``client/native/*.js``, which calls ``fetch``,
  ``navigator.geolocation``, ``navigator.clipboard``, ``navigator.share`` and the
  rest directly. The result comes back as the resolved value of the FFI promise —
  no network hop, no wire format.

* **Mode B (server).** Python runs on the server; the browser is a thin client
  reached over a WebSocket (or SSE + POST). The installed bridge
  (:class:`~tempestweb.native.bridges.ProxyBridge`) serializes the call into the
  ``native_call`` envelope from ``docs/contract.md``, ships it down the patch
  transport, then suspends on an :class:`asyncio.Future`. ``client/native/*.js``
  runs the same Web API call in the browser and posts a ``native_result`` envelope
  back up the channel; :func:`resolve_native_result` matches it to the pending
  future by ``call_id``. **The Web API always executes in the browser** — Mode B
  simply proxies the call there and back over one round-trip.

The wire format (identical in both modes' *contract*, only transported differently)
is pinned by ``docs/contract.md``::

    // server -> client (Mode B): request a native capability
    { "kind": "native_call", "call_id": "c1",
      "capability": "geolocation.get", "args": {} }

    // client -> server (Mode B): typed result, or error
    { "kind": "native_result", "call_id": "c1", "ok": true,  "value": {} }
    { "kind": "native_result", "call_id": "c1", "ok": false,
      "error": "permission_denied" }

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
    "native_call",
    "resolve_native_result",
    "send_native_call",
    "uninstall_bridge",
]

#: Reserved token prefix the client uses (over the event channel, in Mode B) to
#: deliver a ``native_result`` back to its matching pending future when the
#: transport multiplexes native results onto the event lane.
NATIVE_RESULT_PREFIX = "__native_result__:"

#: Monotonic source of call ids (deterministic; avoids ``random``/``uuid`` so
#: envelopes are reproducible in tests). Each id is prefixed with ``"c"`` to match
#: the ``call_id`` convention in ``docs/contract.md`` (``"c1"``, ``"c2"``, ...).
_call_ids: itertools.count[int] = itertools.count(1)


class NativeError(RuntimeError):
    """A native Web-capability call failed in the browser.

    Attributes:
        code: A short machine-readable error code (e.g. ``"permission_denied"``,
            ``"unavailable"``, ``"not_found"``, ``"insecure_context"``,
            ``"http_error"``, ``"timeout"``).
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
    :func:`install_bridge`. The capability modules call :meth:`call` without
    knowing which concrete bridge backs them.

    Implementations must be safe to drive from an asyncio event loop.
    """

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Deliver a ``native_call`` envelope and await its ``native_result``.

        Args:
            envelope: A ``native_call`` envelope carrying a ``call_id``,
                ``capability`` and ``args``.

        Returns:
            The result envelope ``{"ok": bool, "value"/"error": ...}`` as produced
            by ``client/native/*.js``.

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


def native_call(capability: str, args: dict[str, Any], call_id: str) -> dict[str, Any]:
    """Build a ``native_call`` envelope matching ``docs/contract.md``.

    Args:
        capability: The stable dotted capability name (e.g. ``"geolocation.get"``,
            ``"http.request"``, ``"clipboard.read"``).
        args: JSON-able arguments for the capability.
        call_id: The correlation id the client echoes back with the result.

    Returns:
        The serializable ``native_call`` envelope.
    """
    return {
        "kind": "native_call",
        "call_id": call_id,
        "capability": capability,
        "args": args,
    }


async def send_native_call(capability: str, args: dict[str, Any]) -> dict[str, Any]:
    """Send a ``native_call`` and await the browser's typed result.

    Builds an envelope with a fresh ``call_id``, hands it to the installed bridge,
    and unwraps the result: a successful ``value`` payload is returned; a failure
    (``ok`` is false) is raised as :class:`NativeError`. Must be called from the
    asyncio loop the app runs on (i.e. inside a widget handler).

    Args:
        capability: The stable dotted capability name.
        args: JSON-able arguments for the capability.

    Returns:
        The ``value`` payload of a successful result, as a ``dict``.

    Raises:
        BrowserUnavailableError: If no bridge is installed (off-platform).
        NativeError: If the browser reports the call failed (``ok`` is false).
    """
    call_id = f"c{next(_call_ids)}"
    result = await current_bridge().call(native_call(capability, args, call_id))
    if not result.get("ok", False):
        raise NativeError(
            str(result.get("error", "unknown")),
            str(result.get("message", "")),
        )
    value = result.get("value", {})
    return cast("dict[str, Any]", value) if isinstance(value, dict) else {}


def resolve_native_result(
    call_id: str,
    payload: dict[str, Any],
    pending: dict[str, asyncio.Future[dict[str, Any]]],
) -> bool:
    """Resolve a pending native call with the client's ``native_result`` (Mode B).

    Called (on the loop thread) by a Mode-B transport bridge when a
    ``native_result`` envelope tagged with ``call_id`` arrives back over the
    channel. Mode A has no use for this — its FFI bridge resolves its own promise
    inline.

    Args:
        call_id: The correlation id parsed from the ``native_result`` envelope.
        payload: The result envelope (``{"ok": ..., "value"/"error": ...}``).
        pending: The bridge's ``call_id -> Future`` registry.

    Returns:
        ``True`` if a matching pending future was resolved, ``False`` otherwise
        (unknown or already-settled id).
    """
    future = pending.get(call_id)
    if future is None or future.done():
        return False
    future.set_result(payload)
    return True
