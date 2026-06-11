"""In-browser entrypoint for Mode A — the Python code Pyodide runs to start.

``public/index.html`` loads Pyodide, writes the ``tempestweb`` package and the
app module into the virtual filesystem, then calls :func:`bootstrap` to wire the
app to the JS client over ``pyodide.ffi``. This module is the Python end of that
seam:

#. construct a :class:`~tempestweb.transports.wasm.WasmTransport` whose
   ``deliver`` sink is the JS ``onPatches`` callback (passed in as a Pyodide
   proxy),
#. build a :class:`~tempestweb.runtime.wasm.WasmRuntime` around the app's
   ``state``/``view``,
#. return a small handle the JS side uses to push events and read the initial
   node, and start the runtime's event loop as a background task.

It depends on Pyodide only through the *values* JS passes in (callables and the
``asyncio`` loop Pyodide installs), never by importing a ``pyodide`` module, so
the surrounding glue stays importable and type-checkable off-browser. The live
path is exercised manually (see NOTES-T3.md); the pure logic it composes
(``WasmRuntime``/``WasmTransport``) is unit-tested headless.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any, Generic, TypeVar

from tempestweb._core import App, Widget
from tempestweb.native.bridges import FFIBridge
from tempestweb.native.dispatch import install_bridge, uninstall_bridge
from tempestweb.runtime.wasm import WasmRuntime
from tempestweb.transports.wasm import WasmTransport

__all__ = ["WasmAppHandle", "bootstrap"]

S = TypeVar("S")

#: The in-process FFI dispatch the JS side injects (the Pyodide proxy of
#: ``window.__tempestweb_native__(envelope)``). It forwards a ``native_call``
#: envelope to ``client/native/index.js`` and resolves to its ``native_result``.
#: Typed as a plain awaitable callable so this module stays Pyodide-free and
#: type-checkable off-browser; the live value is a ``pyodide.ffi`` proxy.
NativeDispatch = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class WasmAppHandle(Generic[S]):
    """The handle JS holds onto for a running Mode A app.

    Exposes just what the browser side needs: the JSON-able initial node to
    mount, a way to push DOM events into Python, and teardown. Everything else
    (the rebuild loop, serialization, event routing) is driven internally by the
    wrapped :class:`~tempestweb.runtime.wasm.WasmRuntime`.

    Methods:
        initial_node_json: The serialized initial root node, as a JSON string.
        push_event_json: Feed one DOM event (a JSON string) into the runtime.
        close: Tear the app down, stopping the event loop.
    """

    def __init__(
        self,
        runtime: WasmRuntime[S],
        transport: WasmTransport,
        *,
        bridge_installed: bool = False,
    ) -> None:
        """Initialize the handle.

        Args:
            runtime: The runtime driving the app.
            transport: The transport bridging Python and the JS client.
            bridge_installed: Whether :func:`bootstrap` installed an
                :class:`FFIBridge`; if so, :meth:`close` uninstalls it.
        """
        self._runtime: WasmRuntime[S] = runtime
        self._transport: WasmTransport = transport
        self._bridge_installed: bool = bridge_installed
        self._initial: dict[str, Any] = runtime.start()
        # Start the client->Python event loop as a background task on the loop
        # Pyodide runs; it drains transport events until close().
        self._task: asyncio.Future[None] = asyncio.ensure_future(runtime.run())

    def initial_node_json(self) -> str:
        """Return the serialized initial root node as a JSON string.

        JS parses this and hands it to the DOM renderer's ``mount``. A string is
        returned (rather than a dict) so the value crosses ``pyodide.ffi`` as a
        plain string and JS controls the parse.

        Returns:
            The initial root node, JSON-encoded.
        """
        return json.dumps(self._initial)

    def push_event_json(self, event_json: str) -> None:
        """Feed one DOM event into the runtime.

        Args:
            event_json: A JSON string of the wire event
                ``{"type", "key", "payload"}`` captured by the JS client.
        """
        self._transport.push_event(json.loads(event_json))

    async def close(self) -> None:
        """Tear the app down: close the transport and stop the event loop.

        Also uninstalls the in-process :class:`FFIBridge` if :func:`bootstrap`
        installed one, so a torn-down app never leaves a stale process-wide bridge.
        """
        await self._transport.close()
        self._task.cancel()
        if self._bridge_installed:
            uninstall_bridge()
            self._bridge_installed = False


def bootstrap(
    state: S,
    view: Callable[[App[S]], Widget],
    on_patches: Callable[[str], Any],
    dispatch: NativeDispatch | None = None,
) -> WasmAppHandle[S]:
    """Wire an app to the JS client and start it.

    When ``dispatch`` is provided, an :class:`FFIBridge` is installed so that
    ``await native.<capability>()`` inside a handler resolves **in-process** through
    ``client/native/index.js`` — no network hop. The dispatch callable is the one
    Pyodide-aware seam: the JS bootstrap glue (``public/index.html``) exposes
    ``window.__tempestweb_native__`` via :func:`installNativeBridge` and passes its
    Pyodide proxy in here, so this module never imports ``pyodide`` itself and stays
    type-checkable off-browser.

    Args:
        state: The app's initial state.
        view: The app's ``view`` function.
        on_patches: The JS callback that applies a patch batch in the DOM. It is
            called with a **JSON string** of the patch list, so the batch crosses
            ``pyodide.ffi`` as a plain string and JS owns the parse.
        dispatch: Optional in-process native dispatch (the Pyodide proxy of
            ``window.__tempestweb_native__``). When given, an :class:`FFIBridge`
            wrapping it is installed; when ``None`` (e.g. an app that uses no native
            capability), no bridge is installed and a native call would raise
            :class:`~tempestweb.native.dispatch.BrowserUnavailableError`.

    Returns:
        A :class:`WasmAppHandle` the JS side drives.
    """

    def deliver(patches: list[dict[str, Any]]) -> None:
        """Forward a patch batch to JS as a JSON string."""
        on_patches(json.dumps(patches))

    transport = WasmTransport(deliver)
    runtime: WasmRuntime[S] = WasmRuntime(state, view, transport)
    bridge_installed = False
    if dispatch is not None:
        install_bridge(FFIBridge(dispatch))
        bridge_installed = True
    return WasmAppHandle(runtime, transport, bridge_installed=bridge_installed)
