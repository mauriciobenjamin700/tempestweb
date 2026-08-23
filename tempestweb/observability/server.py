"""S8 — server observability: patch latency, structured session logs, tracing.

``create_app(..., metrics=True)`` already answered *how many* sessions exist. It
could not answer whether they are slow, where the time goes, or what the server
did for the client that just complained (tempestweb#119) — and Mode B is the mode
that gets operated in production.

Three things, one seam:

* **Latency and throughput.** :class:`PatchMetrics` keeps a histogram of the time
  from "an event arrived" to "its patches are on the wire", plus counters. It
  renders as Prometheus text next to the connection counters already at
  ``GET /metrics``. The measurement spans the **coalesced rebuild**, because that
  is what the client waits for — timing the handler alone reported rounds with zero
  patches, which is the wrong number confidently displayed.
* **Structured session logs.** One JSON line per session lifecycle event, carrying
  the session id — the same id the trace uses, so a log line and a span can be put
  side by side.
* **Tracing.** A span per session and per patch round, through an adapter. The
  default is a no-op that does not import anything.

Nothing here is a forced dependency. The default :class:`ServerObservability` is
inert: no OpenTelemetry import, no histogram allocation per event, no log sink. An
app that wants tracing passes an adapter; an app that does not pays for a couple of
attribute lookups.

Example:
    >>> obs = ServerObservability(metrics=PatchMetrics())
    >>> with obs.session("s-1"):
    ...     obs.observe_patches(0.004, 2)
    >>> "tempestweb_patch_seconds_count 1" in obs.prometheus()
    True
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Protocol

from tempestweb.observability.logger import Logger, LogRecord

__all__ = [
    "PatchMetrics",
    "ServerObservability",
    "Span",
    "Tracer",
    "json_log_sink",
    "noop_tracer",
    "otel_tracer",
]

#: Histogram buckets in seconds. Chosen around what a Mode B round actually costs:
#: a small tree diffs in well under a millisecond, a heavy screen in a few, and
#: anything past 100 ms is a user-visible stall worth its own bucket.
DEFAULT_BUCKETS: tuple[float, ...] = (
    0.001,
    0.005,
    0.010,
    0.025,
    0.050,
    0.100,
    0.250,
    1.000,
)


class Span(Protocol):
    """One unit of traced work, ended by the context manager that opened it."""

    def set_attribute(self, key: str, value: Any) -> None:  # noqa: ANN401 — span attrs are scalars
        """Record one attribute on this span.

        Args:
            key: The attribute name.
            value: A scalar the exporter can carry.
        """
        ...


class Tracer(Protocol):
    """The tracing seam: open a span, get it back, end it on exit."""

    def span(self, name: str, **attributes: Any) -> Any:  # noqa: ANN401 — a context manager
        """Open a span.

        Args:
            name: The span name.
            **attributes: Initial attributes.

        Returns:
            A context manager yielding a :class:`Span`.
        """
        ...


class _NoopSpan:
    """A span that records nothing, so the default path allocates almost nothing."""

    def set_attribute(self, key: str, value: Any) -> None:  # noqa: ANN401 — ignored
        """Ignore the attribute.

        Args:
            key: Ignored.
            value: Ignored.
        """
        return None


class _NoopTracer:
    """The default tracer: no spans, no imports, no cost worth measuring."""

    @contextmanager
    def span(self, name: str, **attributes: Any) -> Iterator[_NoopSpan]:  # noqa: ANN401 — ignored
        """Yield an inert span.

        Args:
            name: Ignored.
            **attributes: Ignored.

        Yields:
            The shared no-op span.
        """
        yield _NOOP_SPAN


_NOOP_SPAN: _NoopSpan = _NoopSpan()
_NOOP_TRACER: _NoopTracer = _NoopTracer()


def noop_tracer() -> Tracer:
    """The tracer used when an app asks for no tracing.

    Returns:
        A tracer whose spans do nothing.
    """
    return _NOOP_TRACER


def otel_tracer(service_name: str = "tempestweb") -> Tracer:
    """Adapt OpenTelemetry as the tracer, importing it only when called.

    The import lives inside the function on purpose: the tracing default must not
    make ``opentelemetry`` a dependency of every app that serves a page. Exporter
    and sampler configuration stay with OpenTelemetry itself (env vars or an SDK
    setup the app owns) — wrapping those would be a second, worse configuration
    surface.

    Args:
        service_name: The tracer name reported to the exporter.

    Returns:
        A tracer backed by the OpenTelemetry API.

    Raises:
        RuntimeError: If ``opentelemetry-api`` is not installed, naming the extra
            that provides it.
    """
    try:
        # noqa: PLC0415 — the import is lazy on purpose (see the docstring).
        import opentelemetry.trace as trace  # type: ignore[import-not-found]  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover — depends on the environment
        raise RuntimeError(
            "otel_tracer() needs opentelemetry-api: "
            'uv add "tempestweb[otel]" (or opentelemetry-api directly). '
            "Tracing is opt-in precisely so this import is not everyone's problem."
        ) from exc

    otel = trace.get_tracer(service_name)

    class _OtelTracer:
        """Adapter over the OpenTelemetry tracer."""

        @contextmanager
        def span(self, name: str, **attributes: Any) -> Iterator[Any]:  # noqa: ANN401 — otel span
            """Open an OpenTelemetry span.

            Args:
                name: The span name.
                **attributes: Initial attributes.

            Yields:
                The OpenTelemetry span.
            """
            with otel.start_as_current_span(name) as span:
                for key, value in attributes.items():
                    span.set_attribute(key, value)
                yield span

    return _OtelTracer()


def json_log_sink(record: LogRecord) -> None:
    """Print one log record as a single JSON line.

    A session log is only useful if it can be queried, and the console sink prints
    prose. This prints one object per line — the shape every log pipeline ingests —
    with the structured fields at the top level, so ``session_id`` is a field and
    not a substring.

    Args:
        record: The record to print.
    """
    payload: dict[str, Any] = {
        "level": record.level,
        "message": record.message,
        **record.fields,
    }
    print(json.dumps(payload, sort_keys=True, default=str), flush=True)


@dataclass
class PatchMetrics:
    """Latency histogram and counters for the patch round trip.

    A round is one event's whole cost as the operator experiences it: the handler,
    the rebuild, the diff and handing the batch to the transport. Splitting it
    finer would measure the core, which its own benchmark already does; this
    measures the server.

    Attributes:
        buckets: Upper bounds in seconds, ascending.
        counts: Cumulative count per bucket (Prometheus semantics).
        total_seconds: Sum of observed durations, for the average.
        rounds: How many rounds were observed.
        patches: How many patches those rounds produced.
    """

    buckets: tuple[float, ...] = DEFAULT_BUCKETS
    counts: list[int] = field(default_factory=list)
    total_seconds: float = 0.0
    rounds: int = 0
    patches: int = 0

    def __post_init__(self) -> None:
        """Size the bucket counters to the configured bounds."""
        if not self.counts:
            self.counts = [0] * len(self.buckets)

    def observe(self, seconds: float, patches: int) -> None:
        """Record one patch round.

        Args:
            seconds: How long the round took.
            patches: How many patches it produced.
        """
        self.rounds += 1
        self.patches += patches
        self.total_seconds += seconds
        for index, bound in enumerate(self.buckets):
            if seconds <= bound:
                self.counts[index] += 1

    def prometheus(self) -> str:
        """Render the histogram and counters as Prometheus text.

        Returns:
            The metric lines, newline-terminated.
        """
        lines = [
            "# HELP tempestweb_patch_seconds Event-to-patch round duration.",
            "# TYPE tempestweb_patch_seconds histogram",
        ]
        cumulative = 0
        for bound, count in zip(self.buckets, self.counts, strict=True):
            cumulative = max(cumulative, count)
            lines.append(f'tempestweb_patch_seconds_bucket{{le="{bound}"}} {count}')
        lines += [
            f'tempestweb_patch_seconds_bucket{{le="+Inf"}} {self.rounds}',
            f"tempestweb_patch_seconds_sum {self.total_seconds:.6f}",
            f"tempestweb_patch_seconds_count {self.rounds}",
            "# HELP tempestweb_patches_total Patches sent to clients.",
            "# TYPE tempestweb_patches_total counter",
            f"tempestweb_patches_total {self.patches}",
        ]
        return "\n".join(lines) + "\n"


class ServerObservability:
    """The server's observability seam: metrics, structured logs, tracing.

    Every part is optional and independent. The default instance is inert, which is
    what makes it safe to call from the hot path unconditionally: no histogram, no
    logger, a no-op tracer.

    Attributes:
        metrics: The latency/throughput collector, or None.
        logger: The structured logger, or None.
        tracer: The tracer; :func:`noop_tracer` by default.
    """

    def __init__(
        self,
        metrics: PatchMetrics | None = None,
        logger: Logger | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        """Wire the parts an app asked for.

        Args:
            metrics: Collector for patch latency and throughput.
            logger: Structured logger for session lifecycle events.
            tracer: Tracing adapter; the no-op tracer when omitted.
        """
        self.metrics: PatchMetrics | None = metrics
        self.logger: Logger | None = logger
        self.tracer: Tracer = tracer or noop_tracer()

    @property
    def enabled(self) -> bool:
        """Whether anything is actually collected.

        Returns:
            True when metrics, a logger or a real tracer is wired.
        """
        return (
            self.metrics is not None
            or self.logger is not None
            or self.tracer is not _NOOP_TRACER
        )

    def observe_patches(self, seconds: float, patches: int) -> None:
        """Record one event-to-patch latency, when metrics are on.

        ``seconds`` is the wait the **client** experienced: from the event arriving
        to its patches being handed to the transport, rebuild included. That is the
        number an SLO is written against, and the reason the histogram is not taken
        around the handler alone.

        Args:
            seconds: How long the client waited.
            patches: How many patches the batch carries.
        """
        if self.metrics is not None:
            self.metrics.observe(seconds, patches)

    @contextmanager
    def session(self, session_id: str, **attributes: Any) -> Iterator[Any]:  # noqa: ANN401 — span
        """Trace and log one session's whole lifetime.

        The log carries the same ``session_id`` the span does, which is the point:
        a complaint about one client becomes a log query and a trace lookup with
        the same key.

        Args:
            session_id: The session's id.
            **attributes: Extra attributes for the span and the log records.

        Yields:
            The session's span.
        """
        started = time.perf_counter()
        if self.logger is not None:
            self.logger.info("session.open", session_id=session_id, **attributes)
        reason = "closed"
        try:
            with self.tracer.span(
                "tempestweb.session", session_id=session_id, **attributes
            ) as span:
                yield span
        except BaseException as exc:
            reason = type(exc).__name__
            raise
        finally:
            if self.logger is not None:
                self.logger.info(
                    "session.close",
                    session_id=session_id,
                    reason=reason,
                    duration_s=round(time.perf_counter() - started, 6),
                    **attributes,
                )

    @contextmanager
    def dispatch(self, session_id: str, event_type: str) -> Iterator[Any]:  # noqa: ANN401 — span
        """Trace one handler invocation.

        This is the *handler's* span, and deliberately not where the latency
        histogram is taken: the rebuild the handler triggers is **coalesced**, so it
        runs after the handler returns and may cover several events. Timing this
        block would report a number that stops before the work the client is waiting
        for — measured, and it read as ``0 patches`` per round. The histogram is
        taken where the batch actually leaves (:meth:`observe_patches`).

        Args:
            session_id: The session the event belongs to.
            event_type: The wire event type, as a span attribute.

        Yields:
            The handler's span.
        """
        with self.tracer.span(
            "tempestweb.dispatch", session_id=session_id, event_type=event_type
        ) as span:
            yield span

    @contextmanager
    def patch_batch(self, session_id: str, patches: int) -> Iterator[Any]:  # noqa: ANN401 — span
        """Trace one outgoing patch batch.

        Args:
            session_id: The session the batch belongs to.
            patches: How many patches the batch carries.

        Yields:
            The batch's span.
        """
        with self.tracer.span(
            "tempestweb.patch_batch", session_id=session_id, patches=patches
        ) as span:
            yield span

    def prometheus(self) -> str:
        """Render the metrics this instance collected.

        Returns:
            Prometheus text, empty when metrics are off.
        """
        return "" if self.metrics is None else self.metrics.prometheus()
