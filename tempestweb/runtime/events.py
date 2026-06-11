"""Coerce wire event payloads into the typed events handlers expect.

The wire carries an event as ``{"type", "key", "payload"}`` where ``payload`` is a
plain JSON-able dict. A widget declares, per handler prop, the typed
:class:`~tempest_core.widgets.events.Event` its handler receives (e.g.
``GestureDetector.on_swipe`` → ``SwipeEvent``). This module bridges the two: given
the target node's widget type and the wire event type, it validates the payload
into the right typed event via :func:`~tempest_core.widgets.events.parse_event`, so
handlers get ``event.direction`` rather than ``payload["direction"]``.

Both runtimes (Mode A :class:`~tempestweb.runtime.wasm.WasmRuntime` and Mode B
:class:`~tempestweb.runtime.session.AppSession`) call :func:`coerce_event` before
invoking a handler.
"""

from __future__ import annotations

from typing import Any

from tempest_core import App, Widget
from tempest_core.navigation import routes_from_path
from tempest_core.widgets.events import Event, EventValidationError, parse_event

__all__ = ["coerce_event", "apply_scroll", "apply_navigate"]


def apply_navigate(app: App[Any], payload: Any) -> None:  # noqa: ANN401 — wire-shaped payload
    """Resolve a deep-link / browser navigation into the app's nav stack.

    The client reports the document path on load and on ``popstate`` (back/
    forward); this resets the app's navigation stack to the routes that path
    resolves to (``routes_from_path``), so ``view`` re-renders the linked screen
    with its back stack intact. A malformed payload is ignored.

    Args:
        app: The application whose navigation stack to reset.
        payload: The wire payload, expected to carry a string ``path``.
    """
    if not isinstance(payload, dict):
        return
    path = payload.get("path")
    if isinstance(path, str) and path:
        app.reset(routes_from_path(path))


def apply_scroll(app: App[Any], key: str, payload: Any) -> None:  # noqa: ANN401 — wire-shaped payload
    """Slide a virtualized list's visible window from a ``scroll`` wire event.

    The DOM client reports a list's visible ``[start, end)`` window as it scrolls;
    this drives :meth:`~tempest_core.core.state.App.slide_window`, which records
    the window and requests a rebuild so the list materializes the slid items.
    A malformed payload is ignored.

    Args:
        app: The application whose list window to slide.
        key: The ``key`` of the target virtualized list.
        payload: The wire payload, expected to carry int ``start`` and ``end``.
    """
    if not isinstance(payload, dict):
        return
    start = payload.get("start")
    end = payload.get("end")
    if isinstance(start, int) and isinstance(end, int) and end >= start:
        app.slide_window(key, start, end)


def _build_event_types() -> dict[str, dict[str, type[Event]]]:
    """Map each widget type tag to its ``{wire_event_type: Event class}``.

    Walks every :class:`~tempest_core.widgets.base.Widget` subclass and reads its
    ``event_schemas`` ClassVar (``{"on_<type>": EventClass}``), keying the result
    by the widget's type tag and the wire event type (the prop without ``on_``).

    Returns:
        ``{widget_type: {event_type: Event subclass}}``.
    """
    mapping: dict[str, dict[str, type[Event]]] = {}

    def walk(cls: type[Widget]) -> None:
        for subclass in cls.__subclasses__():
            schemas = getattr(subclass, "event_schemas", {})
            if schemas:
                mapping[subclass.__name__] = {
                    prop.removeprefix("on_"): event_type
                    for prop, event_type in schemas.items()
                }
            walk(subclass)

    walk(Widget)
    return mapping


# Built once at import: the widget-class hierarchy is fixed for a process.
_WIDGET_EVENT_TYPES: dict[str, dict[str, type[Event]]] = _build_event_types()


def coerce_event(node_type: str | None, event_type: str, payload: Any) -> Any:  # noqa: ANN401 — payload/return are wire-shaped
    """Validate a wire payload into the typed event for ``(node_type, event_type)``.

    Args:
        node_type: The target node's widget type tag (e.g. ``"GestureDetector"``),
            or ``None`` when unknown.
        event_type: The wire event type (e.g. ``"swipe"``, ``"change"``).
        payload: The raw JSON-able payload mapping from the wire event.

    Returns:
        The typed :class:`~tempest_core.widgets.events.Event` when the widget
        declares a schema for this event type and the payload validates; otherwise
        the raw ``payload`` unchanged (handlers with no typed schema — e.g. a bare
        ``on_click`` — keep receiving the plain dict).
    """
    if node_type is None:
        return payload
    event_cls = _WIDGET_EVENT_TYPES.get(node_type, {}).get(event_type)
    if event_cls is None:
        return payload
    if not isinstance(payload, dict):
        return payload
    try:
        return parse_event(event_cls, payload)
    except EventValidationError:
        # A malformed payload falls back to the raw dict rather than crashing the
        # event loop; the handler can still defend itself.
        return payload
