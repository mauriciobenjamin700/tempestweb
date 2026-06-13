"""Error boundary + telemetry — demonstrating production-grade crash containment.

A real app has subtrees that can go wrong: a component reads from a data source
that can be null, a computed value raises on bad input, or a third-party widget
throws unexpectedly. Without an :class:`~tempestweb.observability.ErrorBoundary`
one broken subtree blanks the whole screen. This example shows how to:

1. Wrap a risky subtree in ``ErrorBoundary`` so the rest of the app keeps
   rendering when the child raises.
2. Wire ``on_error`` to both a structured :class:`~tempestweb.observability.Logger`
   (for human-readable crash records) and a
   :class:`~tempestweb.observability.TelemetryProvider` (for analytics / alerting)
   using :func:`~tempestweb.observability.telemetry_reporter`.
3. Toggle the failure from the UI so you can see the live transition:
   healthy subtree → fallback + log entry + telemetry event → healthy again.

Run it in either mode::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tempestweb._core.style import Edge

from tempestweb._core import App, Button, Column, Row, Style, Text, Widget
from tempestweb.observability import (
    ConsoleTelemetryAdapter,
    ErrorBoundary,
    ErrorInfo,
    LogRecord,
    TelemetryProvider,
    create_logger,
    telemetry_reporter,
)

# ---------------------------------------------------------------------------
# Shared observability sinks — in a real app these would live at the module
# level so that all components fan into the same telemetry pipeline.
# ---------------------------------------------------------------------------

#: Captures every :class:`~tempestweb.observability.LogRecord` emitted during the
#: session so the test (and a dev console panel) can inspect them.
_log_records: list[LogRecord] = []

#: Captures every telemetry event dict so the test can assert on them.
_telemetry_events: list[tuple[str, dict[str, Any]]] = []


def _make_telemetry_provider() -> TelemetryProvider:
    """Build a :class:`TelemetryProvider` that captures events into the module list.

    Returns:
        A configured provider backed by a :class:`ConsoleTelemetryAdapter` whose
        sink is also appending to :data:`_telemetry_events` for test inspection.
    """

    def _sink(message: str) -> None:
        # Parse the conventional "[telemetry] track <event> <props>" line emitted
        # by ConsoleTelemetryAdapter so the test list is structured.
        if message.startswith("[telemetry] track "):
            rest = message[len("[telemetry] track ") :]
            space_idx = rest.find(" ")
            if space_idx != -1:
                event_name = rest[:space_idx]
                try:
                    import ast

                    props: dict[str, Any] = ast.literal_eval(rest[space_idx + 1 :])
                except Exception:  # noqa: BLE001
                    props = {"raw": rest[space_idx + 1 :]}
                _telemetry_events.append((event_name, props))

    return TelemetryProvider(ConsoleTelemetryAdapter(sink=_sink))


def _record_sink(record: LogRecord) -> None:
    """Append a log record to the module-level capture list.

    Args:
        record: The structured log record to store.

    Returns:
        None.
    """
    _log_records.append(record)


# Module-level providers (created once; tests can inspect the captured lists).
_telemetry_provider = _make_telemetry_provider()
_logger = create_logger(sinks=[_record_sink], level="WARNING")


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class BoundaryState:
    """State for the error-boundary demo.

    Attributes:
        boom: When ``True`` the protected subtree raises a ``RuntimeError``,
            demonstrating the boundary's catch-and-fallback behaviour.
        render_count: Counts how many times the healthy subtree has rendered
            successfully.
        crash_count: Counts how many render errors have been caught by the
            boundary.
        last_error: The most recent captured error message, shown in the
            sidebar so the user can see what went wrong without losing the
            rest of the UI.
        log_entries: Human-readable log lines built from captured
            :class:`~tempestweb.observability.LogRecord` objects, shown in
            a live log panel.
    """

    boom: bool = False
    render_count: int = 0
    crash_count: int = 0
    last_error: str = ""
    log_entries: list[str] = field(default_factory=list)


def make_state() -> BoundaryState:
    """Build the initial state for the error-boundary demo.

    Returns:
        A fresh :class:`BoundaryState` with the protected subtree healthy.
    """
    return BoundaryState()


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


def view(app: App[BoundaryState]) -> Widget:
    """Render the error-boundary demo UI from the current state.

    The view nests an :class:`~tempestweb.observability.ErrorBoundary` inside a
    larger layout. When ``state.boom`` is ``True`` the child raises; the boundary
    renders the fallback, calls :data:`_logger` and :data:`_telemetry_provider` via
    the ``on_error`` hook, and updates ``crash_count`` / ``last_error`` on the app
    state. The outer layout — header, controls, log panel — keeps rendering
    regardless.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    # -----------------------------------------------------------------------
    # Handlers
    # -----------------------------------------------------------------------

    def toggle_boom() -> None:
        """Flip the ``boom`` flag to trigger / clear the simulated crash."""
        app.set_state(lambda s: setattr(s, "boom", not s.boom))

    def on_error(info: ErrorInfo) -> None:
        """Handle a captured render error: log it, track it, update state.

        Args:
            info: The captured render failure from the boundary.
        """
        # Structured log — WARNING level so it surfaces even in production.
        # NOTE: use ``error_msg`` as the field name to avoid shadowing the
        # positional ``message`` parameter of Logger.warning.
        _logger.warning(
            "render_error_caught",
            error_type=info.error_type,
            error_msg=info.message,
        )
        # Telemetry (forwards to the module-level provider).
        telemetry_reporter(_telemetry_provider)(info)

        # Mirror onto app state so the UI reflects the crash.
        def _update(s: BoundaryState) -> None:
            s.crash_count += 1
            s.last_error = f"{info.error_type}: {info.message}"
            # Append only the last 5 log lines so the panel stays readable.
            entry = f"[{info.error_type}] {info.message}"
            s.log_entries = (s.log_entries + [entry])[-5:]

        app.set_state(_update)

    # -----------------------------------------------------------------------
    # Protected child builder
    # -----------------------------------------------------------------------

    def child_builder() -> Widget:
        """Build the protected subtree; raises when ``state.boom`` is set.

        Returns:
            A healthy widget showing the render count, or raises
            ``RuntimeError`` when ``state.boom`` is ``True``.

        Raises:
            RuntimeError: When ``state.boom`` is ``True``, simulating a
                widget that fails to render due to bad data or a missing
                dependency.
        """
        if app.state.boom:
            raise RuntimeError("simulated render failure — bad data upstream")

        # Bump render_count so the test can confirm successful re-renders.
        app.set_state(lambda s: setattr(s, "render_count", s.render_count + 1))

        return Column(
            key="healthy-subtree",
            style=Style(gap=4.0, padding=Edge.all(8)),
            children=[
                Text(
                    content="Protected subtree is healthy.",
                    key="healthy-label",
                ),
                Text(
                    content=f"Successful renders: {app.state.render_count}",
                    key="render-count",
                ),
            ],
        )

    # -----------------------------------------------------------------------
    # Assemble the layout
    # -----------------------------------------------------------------------

    # Status badge next to the toggle button.
    status_text = "CRASH MODE ON" if app.state.boom else "healthy"
    toggle_label = "Disable crash" if app.state.boom else "Trigger crash"

    # Log panel entries.
    log_children: list[Widget] = [
        Text(content="Log panel (last 5 entries):", key="log-title")
    ]
    if app.state.log_entries:
        for i, entry in enumerate(app.state.log_entries):
            log_children.append(Text(content=entry, key=f"log-{i}"))
    else:
        log_children.append(Text(content="No errors captured yet.", key="log-empty"))

    return Column(
        key="root",
        style=Style(gap=12.0, padding=Edge.all(16)),
        children=[
            # Header
            Text(content="Error Boundary Demo", key="title"),
            # Controls row
            Row(
                key="controls",
                style=Style(gap=8.0),
                children=[
                    Button(
                        label=toggle_label,
                        on_click=toggle_boom,
                        key="toggle-boom",
                    ),
                    Text(content=f"Status: {status_text}", key="status"),
                    Text(
                        content=f"Crashes caught: {app.state.crash_count}",
                        key="crash-count",
                    ),
                ],
            ),
            # Protected subtree wrapped in ErrorBoundary
            ErrorBoundary(
                key="boundary",
                child_builder=child_builder,
                on_error=on_error,
            ),
            # Last error display (outside the boundary — never affected by it)
            Text(
                content=(
                    f"Last error: {app.state.last_error}"
                    if app.state.last_error
                    else "No error captured yet."
                ),
                key="last-error",
            ),
            # Live log panel (also outside the boundary)
            Column(
                key="log-panel",
                style=Style(gap=2.0, padding=Edge.all(8)),
                children=log_children,
            ),
        ],
    )
