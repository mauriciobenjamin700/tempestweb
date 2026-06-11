"""O0 — Telemetry: a pluggable analytics provider built on the adapter pattern.

Application code calls :meth:`TelemetryProvider.track` and
:meth:`TelemetryProvider.identify` against a tiny, stable interface. The actual
backend (the browser console, Sentry, PostHog, …) lives behind a
:class:`TelemetryAdapter`, so swapping the destination never touches a single
call site — you construct the provider with a different adapter and the rest of
the app is unchanged.

Third-party SDKs (``sentry_sdk``, ``posthog``) are **not** dependencies of
tempestweb. Each adapter wraps an instance the caller injects, so the adapters
stay test-friendly (inject a mock) and the framework stays dependency-light.

Example:
    >>> provider = TelemetryProvider(ConsoleTelemetryAdapter())
    >>> provider.identify("user-1", {"plan": "pro"})
    >>> provider.track("offline_replay", {"queued": 3})

To send the same events to PostHog instead, only the construction line changes::

    provider = TelemetryProvider(PostHogTelemetryAdapter(posthog_client))
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

__all__ = [
    "TelemetryAdapter",
    "TelemetryProvider",
    "ConsoleTelemetryAdapter",
    "SentryTelemetryAdapter",
    "PostHogTelemetryAdapter",
]


@runtime_checkable
class TelemetryAdapter(Protocol):
    """The minimal contract every telemetry backend must satisfy.

    An adapter is intentionally tiny: two methods that map the provider's
    vocabulary (``track`` / ``identify``) onto a concrete backend. Implementing a
    new backend is a handful of lines, which keeps the seam between application
    code and vendor SDK thin and swappable.
    """

    def track(self, event: str, props: dict[str, Any]) -> None:
        """Record a named event with arbitrary properties.

        Args:
            event: The event name (e.g. ``"push_subscribed"``).
            props: JSON-able properties describing the event. Must already be
                free of PII the caller does not want sent to the backend.

        Returns:
            None.
        """
        ...

    def identify(self, user_id: str, traits: dict[str, Any]) -> None:
        """Associate subsequent events with a user identity.

        Args:
            user_id: A stable identifier for the current user.
            traits: JSON-able traits to attach to the identity.

        Returns:
            None.
        """
        ...


class TelemetryProvider:
    """A backend-agnostic facade application code calls to emit telemetry.

    The provider holds exactly one :class:`TelemetryAdapter` and forwards every
    call to it. It also enforces two cross-cutting concerns that should never
    leak into call sites:

    * **Sampling** — a ``sample_rate`` in ``[0.0, 1.0]`` drops a fraction of
      ``track`` calls so a chatty event cannot flood the backend. ``identify`` is
      never sampled (identities must be reliable).
    * **Global properties** — ``default_props`` are merged into every tracked
      event (e.g. ``{"mode": "wasm"}``), without each call site repeating them.

    Swapping the adapter changes the destination of every event while leaving all
    ``track`` / ``identify`` calls untouched.
    """

    def __init__(
        self,
        adapter: TelemetryAdapter,
        *,
        default_props: dict[str, Any] | None = None,
        sample_rate: float = 1.0,
    ) -> None:
        """Initialize the provider.

        Args:
            adapter: The backend adapter every event is forwarded to.
            default_props: Properties merged into every tracked event. A copy is
                stored so later mutation of the caller's dict has no effect.
            sample_rate: Fraction of ``track`` calls to forward, in ``[0.0,
                1.0]``. ``1.0`` forwards all; ``0.0`` forwards none.

        Raises:
            ValueError: If ``sample_rate`` is outside ``[0.0, 1.0]``.
        """
        if not 0.0 <= sample_rate <= 1.0:
            raise ValueError("sample_rate must be within [0.0, 1.0]")
        self._adapter: TelemetryAdapter = adapter
        self._default_props: dict[str, Any] = dict(default_props or {})
        self._sample_rate: float = sample_rate
        self._counter: int = 0

    @property
    def adapter(self) -> TelemetryAdapter:
        """The adapter currently backing this provider.

        Returns:
            The active :class:`TelemetryAdapter`.
        """
        return self._adapter

    def _should_sample(self) -> bool:
        """Decide deterministically whether the next event passes sampling.

        A deterministic counter (rather than randomness) keeps tests reproducible
        and gives an even, predictable spread: with ``sample_rate`` ``0.5`` every
        other event is forwarded.

        Returns:
            ``True`` if the event should be forwarded to the adapter.
        """
        if self._sample_rate >= 1.0:
            return True
        if self._sample_rate <= 0.0:
            return False
        self._counter += 1
        # Forward when the running count crosses the next 1/sample_rate boundary.
        return (self._counter * self._sample_rate) % 1.0 < self._sample_rate

    def track(self, event: str, props: dict[str, Any] | None = None) -> None:
        """Record a named event, subject to sampling and global properties.

        Args:
            event: The event name.
            props: Optional per-event properties; merged on top of
                ``default_props``.

        Returns:
            None.
        """
        if not self._should_sample():
            return
        merged: dict[str, Any] = {**self._default_props, **(props or {})}
        self._adapter.track(event, merged)

    def identify(self, user_id: str, traits: dict[str, Any] | None = None) -> None:
        """Associate subsequent events with a user identity (never sampled).

        Args:
            user_id: A stable identifier for the current user.
            traits: Optional traits to attach to the identity.

        Returns:
            None.
        """
        self._adapter.identify(user_id, traits or {})


class ConsoleTelemetryAdapter:
    """A zero-dependency adapter that prints events through a sink callable.

    This is the default adapter and the Mode A (browser) fallback: in the browser
    the sink is ``console.log``; under CPython it defaults to :func:`print`.
    Injecting the sink keeps it trivially testable.
    """

    def __init__(self, sink: Any = print) -> None:  # noqa: ANN401 - injected console-like sink
        """Initialize the adapter.

        Args:
            sink: A callable invoked with a single string argument for each
                event. Defaults to the built-in :func:`print`.
        """
        self._sink: Any = sink

    def track(self, event: str, props: dict[str, Any]) -> None:
        """Print a tracked event.

        Args:
            event: The event name.
            props: The event properties.

        Returns:
            None.
        """
        self._sink(f"[telemetry] track {event} {props}")

    def identify(self, user_id: str, traits: dict[str, Any]) -> None:
        """Print an identify call.

        Args:
            user_id: The user identifier.
            traits: The identity traits.

        Returns:
            None.
        """
        self._sink(f"[telemetry] identify {user_id} {traits}")


class SentryTelemetryAdapter:
    """An adapter that maps telemetry onto an injected Sentry client.

    ``sentry_sdk`` is not a tempestweb dependency; the caller injects the module
    (or any object exposing ``capture_message`` and ``set_user``). Events become
    breadcrumb-style messages; identities become the Sentry user scope.
    """

    def __init__(self, client: Any) -> None:  # noqa: ANN401 - injected third-party Sentry client
        """Initialize the adapter.

        Args:
            client: An object compatible with ``sentry_sdk`` exposing
                ``capture_message(message, level=..., extras=...)`` and
                ``set_user(dict)``.
        """
        self._client: Any = client

    def track(self, event: str, props: dict[str, Any]) -> None:
        """Forward an event as a Sentry message with the props as extras.

        Args:
            event: The event name.
            props: The event properties, attached as Sentry ``extras``.

        Returns:
            None.
        """
        self._client.capture_message(event, level="info", extras=props)

    def identify(self, user_id: str, traits: dict[str, Any]) -> None:
        """Set the Sentry user scope.

        Args:
            user_id: The user identifier, mapped to ``id``.
            traits: Extra identity fields merged into the user dict.

        Returns:
            None.
        """
        self._client.set_user({"id": user_id, **traits})


class PostHogTelemetryAdapter:
    """An adapter that maps telemetry onto an injected PostHog client.

    ``posthog`` is not a tempestweb dependency; the caller injects a client
    exposing ``capture`` and ``identify``. A ``distinct_id`` is tracked across
    calls so events emitted before an explicit identify still attach to the right
    person once identity is known.
    """

    def __init__(self, client: Any, *, distinct_id: str = "anonymous") -> None:  # noqa: ANN401 - injected third-party PostHog client
        """Initialize the adapter.

        Args:
            client: An object compatible with the PostHog SDK exposing
                ``capture(distinct_id, event, properties)`` and
                ``identify(distinct_id, properties)``.
            distinct_id: The initial distinct id used until ``identify`` runs.
        """
        self._client: Any = client
        self._distinct_id: str = distinct_id

    def track(self, event: str, props: dict[str, Any]) -> None:
        """Forward an event to PostHog under the current distinct id.

        Args:
            event: The event name.
            props: The event properties.

        Returns:
            None.
        """
        self._client.capture(
            distinct_id=self._distinct_id, event=event, properties=props
        )

    def identify(self, user_id: str, traits: dict[str, Any]) -> None:
        """Bind the distinct id and forward an identify call to PostHog.

        Args:
            user_id: The user identifier, used as the new distinct id.
            traits: Person properties to attach.

        Returns:
            None.
        """
        self._distinct_id = user_id
        self._client.identify(distinct_id=user_id, properties=traits)
