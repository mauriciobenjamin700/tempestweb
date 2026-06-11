"""Mode A (WASM/Pyodide) runtime glue — the Python half of the in-browser bridge.

In Mode A the whole application runs **inside the browser** on Pyodide: the
vendored reconciler builds and diffs the widget tree, and the resulting patches
cross to the JS DOM renderer in-process via ``pyodide.ffi`` (no network). This
module is the Python-side glue that:

#. owns the :class:`~tempestweb._core.App`,
#. **serializes** each freshly built :class:`~tempestweb._core.core.ir.Node`
   tree (and every patch) into the plain JSON-able shape the client expects,
   stripping the non-serializable handler callables,
#. keeps a **handler registry** keyed by widget ``key`` so an event arriving
   from the client (``{"type", "key", "payload"}``) is routed back to the right
   Python handler, validated, and invoked (sync or ``async``).

The serialization here is renderer-agnostic and identical to what the Mode B
server sends, so the JS client cannot tell the two modes apart — only the
transport differs. See ``docs/contract.md`` for the wire format and
``tests/fixtures/`` for the golden shapes this module reproduces.

The runtime is deliberately decoupled from Pyodide: it talks to a
:class:`~tempestweb.transports.base.PatchTransport`, so the pure-Python logic
(serialization, event routing, the rebuild loop) is unit-testable headless and
the live ``pyodide.ffi`` wiring is confined to
:mod:`tempestweb.transports.wasm`.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from typing import Any, Generic, TypeVar

from tempestweb._core import App, Node, Scene, Widget
from tempestweb._core.core.ir import Patch
from tempestweb.transports.base import (
    Event,
    PatchTransport,
    TransportClosedError,
)
from tempestweb.transports.base import Patch as WirePatch

__all__ = ["WasmRuntime", "serialize_node", "serialize_patches"]

S = TypeVar("S")

#: Prefix that marks a widget prop as an event handler (``on_click`` → ``click``).
#: The wire event's ``type`` (e.g. ``"click"``) maps to the prop ``on_<type>``,
#: mirroring the widget field naming used across the core.
_HANDLER_PREFIX = "on_"


def _is_handler(name: str, value: object) -> bool:
    """Whether a prop is an event handler that must not cross the boundary.

    A handler is a prop whose name starts with ``on_`` and whose value is
    callable. Such props carry Python functions, which have no JSON
    representation, so they are stripped during serialization and resolved
    in-process when an event arrives.

    Args:
        name: The prop name.
        value: The prop value.

    Returns:
        ``True`` if the prop is a (present) event handler, ``False`` otherwise.
    """
    return name.startswith(_HANDLER_PREFIX) and callable(value)


def _serialize_props(props: dict[str, Any]) -> dict[str, Any]:
    """Serialize a node's props, nulling out handler callables.

    Per ``docs/contract.md``, handlers do not cross the boundary: the client
    only needs to know a handler exists (so it can attach a DOM listener), never
    the function itself. A present handler serializes to ``null`` — the same
    shape the golden fixtures record — and the real callable stays on the Python
    side, addressable by the node's ``key``.

    Args:
        props: The node's raw props, possibly carrying callables.

    Returns:
        A JSON-able props dict with every handler replaced by ``None``.
    """
    out: dict[str, Any] = {}
    for name, value in props.items():
        out[name] = None if _is_handler(name, value) else value
    return out


def serialize_node(node: Node) -> dict[str, Any]:
    """Serialize an IR node tree into the JSON-able client shape.

    Recurses the tree, dumping each node to ``{"type", "key", "props",
    "children"}`` with handler callables nulled out (see :func:`_serialize_props`)
    and ``Style``/``Color``/``Edge`` objects lowered to plain dicts via Pydantic.

    Args:
        node: The root IR node to serialize.

    Returns:
        The JSON-able node dict, ready to hand to the client.
    """
    # Dump a *shallow* copy (children dropped) with sanitized props, so
    # ``mode="json"`` never recurses into a child whose props still carry a raw
    # handler callable — children are serialized separately below.
    shallow = node.model_copy(
        update={"props": _serialize_props(node.props), "children": []}
    )
    # ``mode="json"`` lowers Style/Color/Edge (themselves Pydantic models) and
    # leaves the already-sanitized props as plain JSON-able values.
    dumped: dict[str, Any] = shallow.model_dump(mode="json")
    dumped["children"] = [serialize_node(child) for child in node.children]
    return dumped


def serialize_patches(patches: list[Patch]) -> list[WirePatch]:
    """Serialize a reconciler patch list into JSON-able wire patches.

    Each patch is dumped to its contract shape; any ``node`` payload it carries
    (``Insert``/``Replace``) is serialized via :func:`serialize_node` so the
    embedded subtree is sanitized exactly like the initial tree. ``path`` lists
    keep the core's ``int | "overlay"`` steps unchanged.

    Args:
        patches: The patches emitted by ``diff``/``diff_scene``.

    Returns:
        A list of JSON-able patch dicts, in apply order.
    """
    wire: list[WirePatch] = []
    for patch in patches:
        # Sanitize the two prop-carrying payloads (``node`` subtree and
        # ``set_props``) *before* dumping, so ``mode="json"`` never meets a raw
        # handler callable.
        node = getattr(patch, "node", None)
        set_props = getattr(patch, "set_props", None)
        updates: dict[str, Any] = {}
        if node is not None:
            updates["node"] = Node(type=node.type, key=node.key)
        if isinstance(set_props, dict):
            updates["set_props"] = _serialize_props(set_props)
        stripped = patch.model_copy(update=updates) if updates else patch
        dumped: dict[str, Any] = stripped.model_dump(mode="json")
        if node is not None:
            dumped["node"] = serialize_node(node)
        wire.append(dumped)
    return wire


def _collect_handlers(
    node: Node, registry: dict[str, dict[str, Callable[..., Any]]]
) -> None:
    """Record every keyed node's handler callables into ``registry``.

    Walks the IR tree; for each node that has a ``key``, stores its handler
    props (``on_*`` callables) under that key so an incoming event can resolve
    its handler by ``(key, on_<type>)``. Nodes without a key cannot receive
    events (the wire event addresses widgets by key) and are skipped.

    Args:
        node: The root IR node to walk.
        registry: The accumulator mapping ``key`` → ``{prop: handler}``.
    """
    if node.key is not None:
        handlers = {
            name: value
            for name, value in node.props.items()
            if _is_handler(name, value)
        }
        if handlers:
            registry[node.key] = handlers
    for child in node.children:
        _collect_handlers(child, registry)


class WasmRuntime(Generic[S]):
    """Drives a tempestweb app in Mode A, bridging the core to a transport.

    The runtime wires the vendored :class:`~tempestweb._core.App` to a
    :class:`~tempestweb.transports.base.PatchTransport`: the app's coalesced
    rebuild loop produces patches, which the runtime serializes and pushes to the
    client via :meth:`PatchTransport.send_patches`; the client's events flow back
    through :meth:`PatchTransport.recv_event` and are routed to the matching
    Python handler.

    The same ``view`` runs unchanged in Mode B — only the transport differs — so
    this class never names Pyodide. The live ``pyodide.ffi`` wiring lives in
    :class:`tempestweb.transports.wasm.WasmTransport`.

    Type Args:
        S: The application state type.

    Methods:
        start: Build the initial scene, register handlers, return the JSON node.
        dispatch_event: Route one client event to its Python handler.
        run: Await client events forever, dispatching each (the event loop).
    """

    def __init__(
        self,
        state: S,
        view: Callable[[App[S]], Widget],
        transport: PatchTransport,
    ) -> None:
        """Initialize the runtime.

        Args:
            state: The initial application state.
            view: Builds the widget tree from the app (reads ``app.state``).
            transport: The patch transport carrying patches out and events in.
        """
        self._transport: PatchTransport = transport
        self._handlers: dict[str, dict[str, Callable[..., Any]]] = {}
        self._app: App[S] = App(
            state=state,
            view=view,
            apply_patches=self._apply_patches,
        )

    @property
    def app(self) -> App[S]:
        """The underlying core app.

        Returns:
            The :class:`~tempestweb._core.App` this runtime drives.
        """
        return self._app

    def start(self) -> dict[str, Any]:
        """Build the initial scene and return its serialized root node.

        Registers the initial tree's handlers and returns the JSON-able root
        node the client mounts. Patches emitted by later rebuilds reach the
        client through the transport, not this method.

        Returns:
            The serialized initial root node (``{"type", "key", "props",
            "children"}``).
        """
        scene = self._app.start()
        self._refresh_handlers(scene)
        return serialize_node(scene.root)

    def _refresh_handlers(self, scene: Scene) -> None:
        """Rebuild the handler registry from the current scene.

        Called after every build so the registry always reflects the live tree:
        a node removed by a patch can no longer fire, and a freshly inserted
        node's handler becomes reachable.

        Args:
            scene: The most recently built scene.
        """
        registry: dict[str, dict[str, Callable[..., Any]]] = {}
        _collect_handlers(scene.root, registry)
        for overlay in scene.overlays:
            _collect_handlers(overlay, registry)
        self._handlers = registry

    def _apply_patches(self, patches: list[Patch]) -> None:
        """App callback: serialize patches and push them to the client.

        The core calls this synchronously from its rebuild loop. Because the
        transport's :meth:`send_patches` is ``async``, the delivery is scheduled
        as a task on the running loop; the handler registry is refreshed eagerly
        against the now-current scene so the next event routes correctly.

        Args:
            patches: The patches produced by the core's diff for this tick.
        """
        scene = self._app.current_tree
        if scene is not None:
            self._refresh_handlers(scene)
        wire = serialize_patches(patches)
        asyncio.ensure_future(self._transport.send_patches(wire))

    async def dispatch_event(self, event: Event) -> None:
        """Route one client event to its Python handler and invoke it.

        Resolves the handler by ``(event["key"], "on_" + event["type"])`` against
        the current handler registry. A zero-argument handler is called bare; a
        handler that accepts a positional argument receives the raw payload dict.
        Async handlers are awaited. Unknown keys or event types are ignored (the
        widget may have been removed between dispatch and delivery).

        Args:
            event: The wire event ``{"type", "key", "payload"}``.
        """
        key = event.get("key")
        event_type = event.get("type")
        if not isinstance(key, str) or not isinstance(event_type, str):
            return
        handlers = self._handlers.get(key)
        if handlers is None:
            return
        handler = handlers.get(f"{_HANDLER_PREFIX}{event_type}")
        if handler is None:
            return
        payload: Any = event.get("payload", {})
        result = handler(payload) if _accepts_arg(handler) else handler()
        if inspect.isawaitable(result):
            await result

    async def run(self) -> None:
        """Run the client→Python event loop until the transport closes.

        Awaits events from the transport and dispatches each. Returns when the
        transport raises :class:`~tempestweb.transports.base.TransportClosedError`
        from :meth:`recv_event` (the page closed or the bridge tore down).
        """
        while True:
            try:
                event = await self._transport.recv_event()
            except TransportClosedError:
                return
            await self.dispatch_event(event)


def _accepts_arg(handler: Callable[..., Any]) -> bool:
    """Whether a handler accepts a positional argument.

    Mirrors the core's calling convention: value-bearing events pass the payload
    only when the handler declares a positional parameter; a zero-argument
    handler is called bare. A handler whose signature cannot be introspected
    (e.g. a builtin) is called bare.

    Args:
        handler: The handler callable to inspect.

    Returns:
        ``True`` if the handler takes at least one positional argument.
    """
    try:
        params = inspect.signature(handler).parameters
    except (TypeError, ValueError):
        return False
    return any(
        p.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.VAR_POSITIONAL,
        )
        for p in params.values()
    )
