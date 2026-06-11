"""O3 — Feature flags: runtime feature toggles behind a swappable adapter.

Application code asks :meth:`FeatureFlagsProvider.is_enabled` /
:meth:`FeatureFlagsProvider.get` and subscribes with
:meth:`FeatureFlagsProvider.on_change`. The actual flag source — an in-memory
dict for tests/local dev, GrowthBook, LaunchDarkly, … — lives behind a tiny
:class:`FeatureFlagsAdapter`. Swapping the backend never changes a call site.

Flags are **not secrets**, and the provider is built to fail safe: when a flag is
unknown (or the backend is unreachable and the adapter says so) the caller's
``default`` is returned rather than raising.

Example:
    >>> adapter = InMemoryFeatureFlagsAdapter({"new_ui": True})
    >>> flags = FeatureFlagsProvider(adapter)
    >>> flags.is_enabled("new_ui")
    True
    >>> flags.get("missing", default="off")
    'off'

Subscribers registered with :meth:`on_change` are notified whenever the adapter
reports a change, which is how a flag flip re-renders the part of the UI that
depends on it::

    flags.on_change(lambda: app.schedule_rebuild())
    adapter.set("new_ui", False)  # listeners fire
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "FlagValue",
    "ChangeListener",
    "FeatureFlagsAdapter",
    "FeatureFlagsProvider",
    "InMemoryFeatureFlagsAdapter",
    "GrowthBookFeatureFlagsAdapter",
    "LaunchDarklyFeatureFlagsAdapter",
]

#: A flag value. Booleans gate features; other JSON-able values carry config.
FlagValue = bool | str | int | float | dict[str, Any] | list[Any] | None

#: A zero-argument callback fired when any flag changes.
ChangeListener = Callable[[], None]


@runtime_checkable
class FeatureFlagsAdapter(Protocol):
    """The minimal contract every feature-flag backend must satisfy.

    The interface is intentionally tiny (roughly twenty lines to implement):
    fetch a value, and register a change subscription. ``get`` must never raise
    for an unknown key — it returns the provided ``default`` — so the provider
    can stay fail-safe.
    """

    def get(self, key: str, default: FlagValue = None) -> FlagValue:
        """Return the value of a flag, or ``default`` if unknown.

        Args:
            key: The flag key.
            default: The value to return when the flag is not present.

        Returns:
            The flag value, or ``default`` when unknown.
        """
        ...

    def subscribe(self, listener: ChangeListener) -> Callable[[], None]:
        """Register a listener fired whenever any flag changes.

        Args:
            listener: A zero-argument callback invoked on change.

        Returns:
            An unsubscribe callable that removes the listener.
        """
        ...


class FeatureFlagsProvider:
    """A backend-agnostic facade application code calls to read flags.

    The provider forwards reads to its :class:`FeatureFlagsAdapter` and fans the
    adapter's change notifications out to its own subscribers. ``is_enabled``
    coerces any value to a boolean so a gate check is uniform regardless of the
    underlying value type. Swapping the adapter changes the flag source while
    leaving every ``is_enabled`` / ``get`` / ``on_change`` call untouched.
    """

    def __init__(self, adapter: FeatureFlagsAdapter) -> None:
        """Initialize the provider and bridge the adapter's change stream.

        Args:
            adapter: The flag backend to read from and subscribe to.
        """
        self._adapter: FeatureFlagsAdapter = adapter
        self._listeners: list[ChangeListener] = []
        # Bridge the adapter's single change stream to our fan-out so callers
        # subscribe to the provider, not the concrete adapter.
        self._adapter.subscribe(self._notify)

    @property
    def adapter(self) -> FeatureFlagsAdapter:
        """The adapter currently backing this provider.

        Returns:
            The active :class:`FeatureFlagsAdapter`.
        """
        return self._adapter

    def get(self, key: str, default: FlagValue = None) -> FlagValue:
        """Return a flag's value, or ``default`` when unknown.

        Args:
            key: The flag key.
            default: The value returned when the flag is absent.

        Returns:
            The flag value, or ``default``.
        """
        return self._adapter.get(key, default)

    def is_enabled(self, key: str, *, default: bool = False) -> bool:
        """Return whether a flag is truthy, defaulting safely when unknown.

        Args:
            key: The flag key.
            default: The boolean returned when the flag is absent.

        Returns:
            ``bool(value)`` for a present flag, otherwise ``default``.
        """
        value: FlagValue = self._adapter.get(key, default)
        return bool(value)

    def on_change(self, listener: ChangeListener) -> Callable[[], None]:
        """Register a listener fired whenever any flag changes.

        Args:
            listener: A zero-argument callback invoked on change.

        Returns:
            An unsubscribe callable that removes ``listener``.
        """
        self._listeners.append(listener)

        def unsubscribe() -> None:
            """Remove the registered listener if still present."""
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def _notify(self) -> None:
        """Fan a change notification out to every registered listener.

        Returns:
            None.
        """
        for listener in list(self._listeners):
            listener()


class InMemoryFeatureFlagsAdapter:
    """A dependency-free adapter backed by an in-process dict.

    Ideal for tests, local development and a safe default when no remote backend
    is configured. Mutating a flag through :meth:`set` notifies subscribers,
    which is how a flag flip drives a re-render in unit tests.
    """

    def __init__(self, flags: dict[str, FlagValue] | None = None) -> None:
        """Initialize the adapter with optional seed flags.

        Args:
            flags: Initial flag values. A copy is stored so later mutation of the
                caller's dict has no effect.
        """
        self._flags: dict[str, FlagValue] = dict(flags or {})
        self._listeners: list[ChangeListener] = []

    def get(self, key: str, default: FlagValue = None) -> FlagValue:
        """Return a flag's value, or ``default`` when unknown.

        Args:
            key: The flag key.
            default: The value returned when the flag is absent.

        Returns:
            The flag value, or ``default``.
        """
        return self._flags.get(key, default)

    def set(self, key: str, value: FlagValue) -> None:
        """Set a flag and notify subscribers.

        Args:
            key: The flag key.
            value: The new value.

        Returns:
            None.
        """
        self._flags[key] = value
        self._emit()

    def subscribe(self, listener: ChangeListener) -> Callable[[], None]:
        """Register a change listener.

        Args:
            listener: A zero-argument callback invoked on change.

        Returns:
            An unsubscribe callable.
        """
        self._listeners.append(listener)

        def unsubscribe() -> None:
            """Remove the listener if still registered."""
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def _emit(self) -> None:
        """Notify every subscriber of a change.

        Returns:
            None.
        """
        for listener in list(self._listeners):
            listener()


class GrowthBookFeatureFlagsAdapter:
    """An adapter that maps flag reads onto an injected GrowthBook instance.

    ``growthbook`` is not a tempestweb dependency; the caller injects a client
    exposing ``is_on(key)`` / ``get_feature_value(key, default)``. GrowthBook
    does not push change events in this minimal wrapper, so :meth:`refresh`
    re-evaluates and notifies subscribers after the caller reloads features.
    """

    def __init__(self, client: Any) -> None:  # noqa: ANN401 - injected third-party GrowthBook client
        """Initialize the adapter.

        Args:
            client: A GrowthBook-compatible client exposing ``is_on(key)`` and
                ``get_feature_value(key, default)``.
        """
        self._client: Any = client
        self._listeners: list[ChangeListener] = []

    def get(self, key: str, default: FlagValue = None) -> FlagValue:
        """Return a feature value from GrowthBook.

        Args:
            key: The feature key.
            default: The value returned when the feature is absent.

        Returns:
            The feature value, or ``default``.
        """
        value: FlagValue = self._client.get_feature_value(key, default)
        return value

    def subscribe(self, listener: ChangeListener) -> Callable[[], None]:
        """Register a change listener fired by :meth:`refresh`.

        Args:
            listener: A zero-argument callback invoked on change.

        Returns:
            An unsubscribe callable.
        """
        self._listeners.append(listener)

        def unsubscribe() -> None:
            """Remove the listener if still registered."""
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def refresh(self) -> None:
        """Notify subscribers after the caller reloads GrowthBook features.

        Returns:
            None.
        """
        for listener in list(self._listeners):
            listener()


class LaunchDarklyFeatureFlagsAdapter:
    """An adapter that maps flag reads onto an injected LaunchDarkly client.

    ``launchdarkly-server-sdk`` is not a tempestweb dependency; the caller
    injects a client exposing ``variation(key, context, default)`` plus a stored
    evaluation context. LaunchDarkly streams updates, so the caller wires the
    SDK's update callback to :meth:`notify`.
    """

    def __init__(self, client: Any, context: Any) -> None:  # noqa: ANN401 - injected third-party LaunchDarkly client/context
        """Initialize the adapter.

        Args:
            client: A LaunchDarkly-compatible client exposing
                ``variation(key, context, default)``.
            context: The evaluation context (user/device) passed to every
                ``variation`` call.
        """
        self._client: Any = client
        self._context: Any = context
        self._listeners: list[ChangeListener] = []

    def get(self, key: str, default: FlagValue = None) -> FlagValue:
        """Return a flag variation from LaunchDarkly.

        Args:
            key: The flag key.
            default: The value returned when evaluation falls back.

        Returns:
            The evaluated variation, or ``default``.
        """
        value: FlagValue = self._client.variation(key, self._context, default)
        return value

    def subscribe(self, listener: ChangeListener) -> Callable[[], None]:
        """Register a change listener fired by :meth:`notify`.

        Args:
            listener: A zero-argument callback invoked on change.

        Returns:
            An unsubscribe callable.
        """
        self._listeners.append(listener)

        def unsubscribe() -> None:
            """Remove the listener if still registered."""
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def notify(self) -> None:
        """Notify subscribers when LaunchDarkly streams a flag update.

        Returns:
            None.
        """
        for listener in list(self._listeners):
            listener()
