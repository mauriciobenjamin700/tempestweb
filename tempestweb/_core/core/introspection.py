"""Introspection: a self-describing catalog of widgets, handlers and events.

Analogous to FastAPI's ``/docs``: it publishes the typed contract as plain,
JSON-serializable data — every widget's prop schema, the event each handler
emits, and every event payload schema. Tooling, the device bridge, and editors
can consume this to validate and autocomplete against the framework without
importing it.
"""

from __future__ import annotations

from typing import Any

from tempestweb._core.widgets import (
    ActionSheet,
    Animated,
    AnimatedList,
    AspectRatio,
    Autocomplete,
    BackdropFilter,
    Blur,
    BottomSheet,
    Button,
    CameraPreview,
    Canvas,
    Checkbox,
    ClipPath,
    Column,
    ConnectivityEvent,
    Container,
    DateChangeEvent,
    DatePicker,
    DeepLinkEvent,
    Dialog,
    DismissEvent,
    Dismissible,
    DoubleTapHandler,
    DragEvent,
    Draggable,
    DragTarget,
    Dropdown,
    EndReachedEvent,
    Event,
    FilePicker,
    FileSelectEvent,
    Form,
    FormField,
    GestureDetector,
    Hero,
    Icon,
    Image,
    Input,
    InteractiveViewer,
    KeyboardAvoidingView,
    LazyColumn,
    LazyGrid,
    LazyRow,
    LifecycleEvent,
    LocaleChangeEvent,
    LongPressEvent,
    MapView,
    MaskedInput,
    Menu,
    MenuSelectEvent,
    Navigator,
    PageChangeEvent,
    PageView,
    PanEvent,
    PanHandler,
    PinInput,
    Popover,
    ProgressBar,
    QrScanEvent,
    QrScanner,
    RangeChangeEvent,
    RangeSlider,
    RefreshControl,
    RefreshEvent,
    ReorderableList,
    ReorderEvent,
    RouteChangeEvent,
    RouteDrawer,
    Row,
    ScaleEvent,
    ScaleHandler,
    ScrollEvent,
    ScrollView,
    SectionList,
    SelectEvent,
    SensorEvent,
    Shimmer,
    Skeleton,
    SlideEvent,
    Slider,
    Spinner,
    Stack,
    SubmitEvent,
    Svg,
    SwipeEvent,
    Switch,
    TabBar,
    TabView,
    TapEvent,
    Text,
    TextArea,
    TextChangeEvent,
    ThemeChangeEvent,
    TimeChangeEvent,
    TimePicker,
    Toast,
    ToggleEvent,
    Tooltip,
    ValidationEvent,
    VideoPlayer,
    WebView,
    Widget,
    Wrap,
)

__all__ = [
    "WIDGET_TYPES",
    "EVENT_TYPES",
    "widget_catalog",
    "event_catalog",
    "introspect",
]

#: The widget types exposed by the framework, in a stable order.
WIDGET_TYPES: tuple[type[Widget], ...] = (
    Text,
    Button,
    Column,
    Row,
    Container,
    ScrollView,
    Stack,
    Wrap,
    PageView,
    AspectRatio,
    KeyboardAvoidingView,
    Animated,
    AnimatedList,
    Hero,
    Shimmer,
    Skeleton,
    GestureDetector,
    PanHandler,
    ScaleHandler,
    DoubleTapHandler,
    Draggable,
    DragTarget,
    Dismissible,
    ReorderableList,
    InteractiveViewer,
    Navigator,
    TabView,
    TabBar,
    RouteDrawer,
    Input,
    TextArea,
    Checkbox,
    Switch,
    Slider,
    DatePicker,
    FilePicker,
    Dropdown,
    TimePicker,
    RangeSlider,
    Autocomplete,
    PinInput,
    MaskedInput,
    FormField,
    Form,
    Image,
    Icon,
    ProgressBar,
    Spinner,
    LazyColumn,
    LazyRow,
    LazyGrid,
    SectionList,
    RefreshControl,
    Dialog,
    BottomSheet,
    Toast,
    Tooltip,
    Menu,
    Popover,
    ActionSheet,
    Canvas,
    VideoPlayer,
    WebView,
    Svg,
    CameraPreview,
    QrScanner,
    MapView,
    Blur,
    BackdropFilter,
    ClipPath,
)

#: The event payload types crossing the native boundary.
EVENT_TYPES: tuple[type[Event], ...] = (
    TapEvent,
    TextChangeEvent,
    ToggleEvent,
    SlideEvent,
    DateChangeEvent,
    FileSelectEvent,
    LongPressEvent,
    SwipeEvent,
    RouteChangeEvent,
    ScrollEvent,
    RefreshEvent,
    EndReachedEvent,
    DismissEvent,
    MenuSelectEvent,
    PanEvent,
    ScaleEvent,
    DragEvent,
    ReorderEvent,
    SelectEvent,
    TimeChangeEvent,
    RangeChangeEvent,
    SubmitEvent,
    ValidationEvent,
    PageChangeEvent,
    QrScanEvent,
    LifecycleEvent,
    SensorEvent,
    ConnectivityEvent,
    DeepLinkEvent,
    ThemeChangeEvent,
    LocaleChangeEvent,
)


def widget_catalog() -> dict[str, Any]:
    """Describe every widget: its prop schema and the events it emits.

    Returns:
        A mapping of widget name to ``{"schema": <json schema>, "events":
        {handler_prop: event_type_name}}``.
    """
    catalog: dict[str, Any] = {}
    for widget in WIDGET_TYPES:
        catalog[widget.__name__] = {
            "schema": widget.model_json_schema(),
            "events": {
                prop: event.__name__ for prop, event in widget.event_schemas.items()
            },
        }
    return catalog


def event_catalog() -> dict[str, Any]:
    """Describe every event payload schema.

    Returns:
        A mapping of event name to its JSON schema.
    """
    return {event.__name__: event.model_json_schema() for event in EVENT_TYPES}


def introspect() -> dict[str, Any]:
    """Produce the full, JSON-serializable framework contract.

    Returns:
        ``{"widgets": <widget catalog>, "events": <event catalog>}``.
    """
    return {"widgets": widget_catalog(), "events": event_catalog()}
