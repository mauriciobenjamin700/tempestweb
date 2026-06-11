"""Typed events and the boundary validation contract.

Without a WebView there is no JS↔Python frontier; the typed contract lives at
the Python↔Kotlin boundary. Events that come back from the native side (a tap, a
text change) arrive as raw payloads and must be validated *before* they enter a
Python handler — exactly like FastAPI validates a request body. These Pydantic
models are that contract, and :func:`parse_event` is the validation gate that
turns a raw payload into a typed event or raises a structured error.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any, TypeVar, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from tempestweb._core.theme import ThemeMode

__all__ = [
    "Event",
    "TapEvent",
    "TextChangeEvent",
    "ToggleEvent",
    "SlideEvent",
    "DateChangeEvent",
    "FileSelectEvent",
    "SwipeDirection",
    "LongPressEvent",
    "SwipeEvent",
    "RouteChangeEvent",
    "ScrollEvent",
    "RefreshEvent",
    "EndReachedEvent",
    "DismissEvent",
    "MenuSelectEvent",
    "PanEvent",
    "ScaleEvent",
    "DragEvent",
    "ReorderEvent",
    "SelectEvent",
    "TimeChangeEvent",
    "RangeChangeEvent",
    "SubmitEvent",
    "ValidationEvent",
    "PageChangeEvent",
    "QrScanEvent",
    "AppState",
    "LifecycleEvent",
    "SensorType",
    "SensorEvent",
    "ConnectivityState",
    "ConnectivityEvent",
    "DeepLinkEvent",
    "ThemeChangeEvent",
    "LocaleChangeEvent",
    "EventValidationError",
    "parse_event",
]


class Event(BaseModel):
    """Base class for all events crossing the native boundary."""

    model_config = ConfigDict(frozen=True)


class TapEvent(Event):
    """A tap/click on a widget.

    Attributes:
        x: Optional x position of the tap, in logical pixels.
        y: Optional y position of the tap, in logical pixels.
    """

    x: float | None = Field(
        default=None, description="Optional x position of the tap, in logical pixels."
    )
    y: float | None = Field(
        default=None, description="Optional y position of the tap, in logical pixels."
    )


class TextChangeEvent(Event):
    """A text input's value changed.

    Attributes:
        value: The new text value.
        valid: Whether the value satisfies the input's ``pattern`` (regex), or
            ``None`` when the input declares no pattern. The renderer computes
            this against the widget's pattern before dispatch.
    """

    value: str = Field(description="The new text value.")
    valid: bool | None = Field(
        default=None,
        description="Whether the value satisfies the input's ``pattern`` (regex), or "
        "``None`` when the input declares no pattern. The renderer computes this "
        "against the widget's pattern before dispatch.",
    )


class ToggleEvent(Event):
    """A checkbox/switch toggled.

    Attributes:
        checked: The new checked state.
    """

    checked: bool = Field(description="The new checked state.")


class SlideEvent(Event):
    """A slider's value changed.

    Attributes:
        value: The new slider value, in the widget's ``[min, max]`` range.
    """

    value: float = Field(
        description="The new slider value, in the widget's ``[min, max]`` range."
    )


class DateChangeEvent(Event):
    """A date picker's value changed.

    Attributes:
        value: The new date as an ISO ``yyyy-mm-dd`` string (empty when cleared).
    """

    value: str = Field(
        description="The new date as an ISO ``yyyy-mm-dd`` string (empty when cleared)."
    )


class FileSelectEvent(Event):
    """A file was selected from a file picker.

    Attributes:
        uri: The selected file's URI (Android ``content://``) or path.
        name: The display name, if the platform reports one.
    """

    uri: str = Field(
        description="The selected file's URI (Android ``content://``) or path."
    )
    name: str | None = Field(
        default=None, description="The display name, if the platform reports one."
    )


class SwipeDirection(StrEnum):
    """The cardinal direction of a swipe gesture.

    Attributes:
        LEFT: The pointer travelled predominantly toward the left edge of the
            screen (decreasing x).
        RIGHT: The pointer travelled predominantly toward the right edge of the
            screen (increasing x).
        UP: The pointer travelled predominantly toward the top of the screen
            (decreasing y).
        DOWN: The pointer travelled predominantly toward the bottom of the
            screen (increasing y).
    """

    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"


class LongPressEvent(Event):
    """A press held past the long-press threshold.

    Attributes:
        x: Optional x position of the press, in logical pixels.
        y: Optional y position of the press, in logical pixels.
    """

    x: float | None = Field(
        default=None, description="Optional x position of the press, in logical pixels."
    )
    y: float | None = Field(
        default=None, description="Optional y position of the press, in logical pixels."
    )


class SwipeEvent(Event):
    """A directional swipe (a press-drag-release past the distance threshold).

    Attributes:
        direction: The dominant cardinal direction of the swipe.
        dx: Total horizontal travel from press to release, in logical pixels.
        dy: Total vertical travel from press to release, in logical pixels.
    """

    direction: SwipeDirection = Field(
        description="The dominant cardinal direction of the swipe."
    )
    dx: float = Field(
        default=0.0,
        description="Total horizontal travel from press to release, in logical pixels.",
    )
    dy: float = Field(
        default=0.0,
        description="Total vertical travel from press to release, in logical pixels.",
    )


class RouteChangeEvent(Event):
    """The active route changed (a push/pop/replace happened).

    This is the typed payload a navigation host emits when it settles on a new
    screen, so handlers (analytics, focus management) can react to navigation
    across the native boundary.

    Attributes:
        name: The destination route name.
        params: The destination route's typed parameters.
    """

    name: str = Field(description="The destination route name.")
    params: dict[str, Any] = Field(
        description="The destination route's typed parameters.", default_factory=dict
    )


class ScrollEvent(Event):
    """A scrollable container scrolled.

    Emitted by virtualized lists as the user scrolls, so the application can
    recompute the visible window and request new items.

    Attributes:
        offset: The current scroll position, in logical pixels.
        direction: The scroll axis (``"vertical"`` or ``"horizontal"``).
    """

    offset: float = Field(description="The current scroll position, in logical pixels.")
    direction: str = Field(
        description='The scroll axis (``"vertical"`` or ``"horizontal"``).'
    )


class RefreshEvent(Event):
    """A pull-to-refresh gesture completed.

    Carries no payload: the gesture itself is the signal. The handler typically
    reloads the list's data and clears the widget's ``refreshing`` flag.
    """


class EndReachedEvent(Event):
    """The list scrolled past its end-reached threshold.

    Carries no payload. The handler typically paginates — loading the next page
    of items and growing the list's ``item_count``.
    """


class DismissEvent(Event):
    """An overlay was dismissed (barrier tap, swipe-down, or system back).

    The renderer emits this when the user dismisses an overlay through a gesture
    the host owns (tapping the scrim behind a dialog, dragging a sheet down). The
    bridge routes it to ``App.dismiss``; the optional ``overlay_id`` lets the
    host name the overlay, while ``None`` lets a renderer fire it without one
    (the bridge then falls back to the token-encoded id).

    Attributes:
        overlay_id: The dismissed overlay's stable id, or ``None`` when the
            renderer dispatches without one.
    """

    overlay_id: str | None = Field(
        default=None,
        description="The dismissed overlay's stable id, or ``None`` when the renderer "
        "dispatches without one.",
    )


class MenuSelectEvent(Event):
    """The user selected an item from a menu or action sheet.

    Attributes:
        value: The selected item's stable value.
        label: The selected item's display label.
    """

    value: str = Field(description="The selected item's stable value.")
    label: str = Field(description="The selected item's display label.")


class PanEvent(Event):
    """A pan/drag gesture reported continuously and on release.

    Emitted by ``PanHandler`` as the pointer drags over its child, carrying the
    per-frame delta and — at release — the fling velocity, so handlers can drive
    momentum scrolling or kinetic movement.

    Attributes:
        dx: Horizontal travel since the previous report, in logical pixels.
        dy: Vertical travel since the previous report, in logical pixels.
        vx: Horizontal velocity at release, in logical pixels per second.
        vy: Vertical velocity at release, in logical pixels per second.
    """

    dx: float = Field(
        default=0.0,
        description="Horizontal travel since the previous report, in logical pixels.",
    )
    dy: float = Field(
        default=0.0,
        description="Vertical travel since the previous report, in logical pixels.",
    )
    vx: float = Field(
        default=0.0,
        description="Horizontal velocity at release, in logical pixels per second.",
    )
    vy: float = Field(
        default=0.0,
        description="Vertical velocity at release, in logical pixels per second.",
    )


class ScaleEvent(Event):
    """A pinch (scale + rotation) gesture, anchored at a focal point.

    Emitted by ``ScaleHandler`` and ``InteractiveViewer`` as the user pinches or
    rotates two pointers over the child. The focal point is reported as two
    top-level floats (never a raw tuple) so the payload stays JSON-serializable
    across the bridge.

    Attributes:
        scale: The cumulative scale factor (``1.0`` is no change).
        focus_x: The x coordinate of the pinch focal point, in logical pixels.
        focus_y: The y coordinate of the pinch focal point, in logical pixels.
        rotation: The cumulative rotation, in degrees.
    """

    scale: float = Field(
        default=1.0, description="The cumulative scale factor (``1.0`` is no change)."
    )
    focus_x: float = Field(
        default=0.0,
        description="The x coordinate of the pinch focal point, in logical pixels.",
    )
    focus_y: float = Field(
        default=0.0,
        description="The y coordinate of the pinch focal point, in logical pixels.",
    )
    rotation: float = Field(
        default=0.0, description="The cumulative rotation, in degrees."
    )


class DragEvent(Event):
    """A drag-and-drop interaction: an item picked up and (maybe) dropped.

    Emitted by ``Draggable`` (on release) and ``DragTarget`` (on drop). The
    ``data`` field is the opaque label declared by the ``Draggable`` so the drop
    target can identify what landed on it; ``x``/``y`` report the drop position
    when the renderer can measure it.

    Attributes:
        data: The opaque payload carried from ``Draggable.drag_data``.
        x: Optional x position of the drop, in logical pixels.
        y: Optional y position of the drop, in logical pixels.
    """

    data: str = Field(
        default="",
        description="The opaque payload carried from ``Draggable.drag_data``.",
    )
    x: float | None = Field(
        default=None, description="Optional x position of the drop, in logical pixels."
    )
    y: float | None = Field(
        default=None, description="Optional y position of the drop, in logical pixels."
    )


class ReorderEvent(Event):
    """A list item dragged from one position to another.

    Emitted by ``ReorderableList`` when the user drags an item to a new slot. The
    handler typically mutates its backing list (``items.insert(to_index,
    items.pop(from_index))``); a keyed child list then diffs to a ``Reorder``
    patch (the A2 mechanism), so no new patch kind is needed.

    Attributes:
        from_index: The item's original index.
        to_index: The item's destination index.
    """

    from_index: int = Field(description="The item's original index.")
    to_index: int = Field(description="The item's destination index.")


class SelectEvent(Event):
    """An option was selected from a dropdown / select control.

    Attributes:
        value: The selected option string.
        index: The 0-based index of the option in the control's options list.
    """

    value: str = Field(description="The selected option string.")
    index: int = Field(
        description="The 0-based index of the option in the control's options list."
    )


class TimeChangeEvent(Event):
    """A time picker's value changed.

    Attributes:
        value: The new time as a 24-hour ``"HH:MM"`` string (``""`` when cleared).
    """

    value: str = Field(
        description='The new time as a 24-hour ``"HH:MM"`` string (``""`` when '
        "cleared).",
    )


class RangeChangeEvent(Event):
    """A range slider's bounds changed.

    The two bounds cross the boundary as separate top-level floats (never a raw
    tuple) so the payload stays JSON-serializable.

    Attributes:
        low: The lower bound of the selected range.
        high: The upper bound of the selected range.
    """

    low: float = Field(description="The lower bound of the selected range.")
    high: float = Field(description="The upper bound of the selected range.")


class SubmitEvent(Event):
    """A form (or completable input) was submitted.

    Carries the raw field values captured at submit time as a flat
    ``dict[str, str]`` — no nested models — so the payload is JSON-serializable.

    Attributes:
        values: A mapping of field name to its raw string value at submit time.
    """

    values: dict[str, str] = Field(
        description="A mapping of field name to its raw string value at submit time.",
        default_factory=dict,
    )


class ValidationEvent(Event):
    """A single form field was validated.

    Emitted by ``FormField`` when its validators run, so a handler can react to
    a per-field validation result without re-running the rules.

    Attributes:
        field: The field's name.
        value: The field's raw string value at validation time.
        error: The validation message, or ``None`` when the field is valid.
    """

    field: str = Field(description="The field's name.")
    value: str = Field(description="The field's raw string value at validation time.")
    error: str | None = Field(
        default=None,
        description="The validation message, or ``None`` when the field is valid.",
    )


class PageChangeEvent(Event):
    """The active page of a ``PageView`` carousel changed.

    Emitted when the user swipes to a new page (or a renderer's prev/next control
    settles on one). The application keeps the active page in its own state and
    reacts by storing the new index; a handler should guard against re-emitting
    the same index to avoid a feedback loop.

    Attributes:
        page: The new active page index (0-based).
        previous: The page index that was active before the change.
    """

    page: int = Field(description="The new active page index (0-based).")
    previous: int = Field(
        default=0, description="The page index that was active before the change."
    )


class QrScanEvent(Event):
    """A QR/barcode scan result.

    Emitted by ``QrScanner`` for each decoded code. The decoded payload and its
    symbology cross the boundary as plain strings.

    Attributes:
        data: The decoded code contents.
        format: The barcode symbology (e.g. ``"QR_CODE"``).
    """

    data: str = Field(description="The decoded code contents.")
    format: str = Field(
        default="QR_CODE", description='The barcode symbology (e.g. ``"QR_CODE"``).'
    )


def _empty_floats() -> list[float]:
    """Provide a fresh, typed empty list of floats for default factories.

    Returns:
        A new empty list of floats.
    """
    return []


def _empty_str_map() -> dict[str, str]:
    """Provide a fresh, typed empty string mapping for default factories.

    Returns:
        A new empty ``str -> str`` mapping.
    """
    return {}


class AppState(StrEnum):
    """The lifecycle state of the application process.

    Attributes:
        FOREGROUND: The app is visible and receiving user input — it is the
            active task in front of the user and may run UI work freely.
        BACKGROUND: The app is no longer visible (the user switched away or the
            screen is off); it should pause UI work and release scarce
            resources, as the OS may suspend or reclaim it.
        INACTIVE: The app is in a transitional, partially-obscured state where
            it is visible but not receiving input — e.g. during an incoming
            call, the app switcher, a system permission prompt, or a split-screen
            transition.
    """

    FOREGROUND = "foreground"
    BACKGROUND = "background"
    INACTIVE = "inactive"


class LifecycleEvent(Event):
    """The application moved between lifecycle states.

    Emitted by the host's lifecycle observer (Android ``ProcessLifecycleOwner``,
    or the Qt simulator's ``QApplication.applicationStateChanged``) and routed
    over the reserved lifecycle token, so application code can react to the app
    entering the foreground or background.

    Attributes:
        state: The new lifecycle state.
    """

    state: AppState = Field(description="The new lifecycle state.")


class SensorType(StrEnum):
    """A device hardware sensor a continuous stream can be opened on.

    Attributes:
        ACCELEROMETER: Reports linear acceleration along the device's x/y/z
            axes (including gravity), in metres per second squared.
        GYROSCOPE: Reports the device's angular velocity (rate of rotation)
            about its x/y/z axes, in radians per second.
        MAGNETOMETER: Reports the ambient geomagnetic field strength along the
            device's x/y/z axes, in microtesla — the basis for a compass.
        PRESSURE: Reports ambient atmospheric (barometric) pressure, in
            hectopascals, used for altitude estimation and weather sensing.
        LIGHT: Reports ambient illuminance at the screen, in lux — used to drive
            automatic screen-brightness adjustment.
        PROXIMITY: Reports nearness of an object to the front of the device
            (e.g. an ear during a call); typically a near/far distance in
            centimetres.
        STEP_COUNTER: Reports the cumulative number of steps the user has taken
            since the device last booted, as counted by the hardware pedometer.
    """

    ACCELEROMETER = "accelerometer"
    GYROSCOPE = "gyroscope"
    MAGNETOMETER = "magnetometer"
    PRESSURE = "pressure"
    LIGHT = "light"
    PROXIMITY = "proximity"
    STEP_COUNTER = "step_counter"


class SensorEvent(Event):
    """A single sample from a device sensor stream.

    Emitted continuously by the host while a sensor stream is open and routed
    over the reserved sensor token (``"__sensor__:<type>"``). The sample values
    cross the boundary as a flat list of floats (never a tuple) so the payload
    stays JSON-serializable.

    Attributes:
        sensor: Which sensor produced the sample.
        values: The sample values (e.g. ``[x, y, z]`` for the accelerometer).
        timestamp_ms: The sample timestamp in milliseconds since boot, or ``0``
            when the host does not report one.
    """

    sensor: SensorType = Field(description="Which sensor produced the sample.")
    values: list[float] = Field(
        description="The sample values (e.g. ``[x, y, z]`` for the accelerometer).",
        default_factory=_empty_floats,
    )
    timestamp_ms: int = Field(
        default=0,
        description="The sample timestamp in milliseconds since boot, or ``0`` when "
        "the host does not report one.",
    )


class ConnectivityState(StrEnum):
    """The device's current network connectivity state.

    Attributes:
        CONNECTED: The device has an active network link of an unspecified or
            generic transport — reachability is available but the kind of link
            is not distinguished.
        DISCONNECTED: The device has no active network link; requests will fail
            until connectivity is restored (airplane mode, no signal, Wi-Fi
            off).
        WIFI: The device is connected over a Wi-Fi network — typically
            unmetered, so larger transfers are acceptable.
        MOBILE: The device is connected over a cellular (mobile data) network —
            typically metered, so handlers may choose to defer heavy transfers.
    """

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    WIFI = "wifi"
    MOBILE = "mobile"


class ConnectivityEvent(Event):
    """The device's network connectivity changed.

    Emitted by the host's connectivity callback and routed over the reserved
    connectivity token (``"__connectivity__:<state>"``), so application code can
    react to the device going online/offline or switching transports.

    Attributes:
        state: The new connectivity state.
    """

    state: ConnectivityState = Field(description="The new connectivity state.")


class DeepLinkEvent(Event):
    """The app was opened (or resumed) via a deep link.

    Carries the link target and its parsed query parameters as a flat
    ``dict[str, str]`` so the payload stays JSON-serializable.

    Attributes:
        url: The full deep-link URL.
        params: The parsed query parameters (empty when the link carries none).
    """

    url: str = Field(description="The full deep-link URL.")
    params: dict[str, str] = Field(
        description="The parsed query parameters (empty when the link carries none).",
        default_factory=_empty_str_map,
    )


class ThemeChangeEvent(Event):
    """The active theme mode changed (e.g. the user toggled dark/light).

    Not emitted by a widget handler: the host fires it when the OS color scheme
    changes (or app code requests a switch), and the bridge routes it over the
    reserved theme token (``"__theme__"``) to ``App.set_theme``.

    Attributes:
        mode: The new theme mode.
    """

    mode: ThemeMode = Field(description="The new theme mode.")


class LocaleChangeEvent(Event):
    """The active locale / layout direction changed.

    Not emitted by a widget handler: the host fires it when the device locale
    changes (or app code requests a switch), and the bridge routes it over the
    reserved locale token (``"__locale__"``) to ``App.set_locale``.

    Attributes:
        language: The new BCP-47 language tag.
        region: The optional region/country subtag.
        rtl: Whether the new locale lays out right-to-left.
    """

    language: str = Field(description="The new BCP-47 language tag.")
    region: str | None = Field(
        default=None, description="The optional region/country subtag."
    )
    rtl: bool = Field(
        default=False, description="Whether the new locale lays out right-to-left."
    )


E = TypeVar("E", bound=Event)


class EventValidationError(Exception):
    """Raised when a raw event payload fails validation at the boundary.

    Attributes:
        event_type: The expected event type.
        errors: The structured Pydantic error list (JSON-serializable).
    """

    def __init__(self, event_type: type[Event], errors: list[dict[str, Any]]) -> None:
        """Initialize the error.

        Args:
            event_type: The expected event type.
            errors: The structured validation errors.
        """
        self.event_type: type[Event] = event_type
        self.errors: list[dict[str, Any]] = errors
        super().__init__(f"invalid {event_type.__name__} payload: {errors}")


def parse_event(event_type: type[E], raw: Mapping[str, Any]) -> E:
    """Validate a raw payload into a typed event.

    This is the boundary gate: native code sends an untyped mapping, and only a
    valid payload becomes a typed event the handler can trust.

    Args:
        event_type: The expected event type.
        raw: The raw payload from the native boundary.

    Returns:
        The validated, typed event.

    Raises:
        EventValidationError: If the payload does not match ``event_type``, with
            the structured field errors attached.
    """
    try:
        return event_type.model_validate(dict(raw))
    except ValidationError as exc:
        errors = cast("list[dict[str, Any]]", exc.errors())
        raise EventValidationError(event_type, errors) from exc
