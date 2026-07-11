# Error Boundary + Telemetry — Containing Failures in Production 🛡️

Learn how to protect your UI with `ErrorBoundary`, wire the error hook to a structured `Logger` and a `TelemetryProvider`, and watch the log panel update in real time — all without a single broken subtree blanking the whole screen.

---

## The problem we are solving

In any real app, a subtree can fail to render: a component reads from a data source that can be `None`, a computed value raises on bad input, or a third-party widget throws unexpectedly.

Without protection, **a single exception in `view()` blanks the entire app**. The user sees a white screen and you have no evidence of what happened.

This example shows how to fix both sides of the problem:

| Problem | Solution |
|---|---|
| Broken subtree blanks the screen | `ErrorBoundary` contains the exception and renders a fallback |
| Silent failure with no trace | `Logger` + `TelemetryProvider` via `telemetry_reporter` |
| UI state stale after a crash | `on_error` calls `app.set_state` to reflect the crash |

!!! note "Note — complement to state rollback"
    `ErrorBoundary` handles **render errors**. The core's state rollback handles **errors in event handlers**. The two work together — one does not replace the other.

---

## What you'll build

An interactive demo featuring:

- 🟢 A protected subtree that shows a count of successful renders
- 💥 **Trigger crash** button that simulates a render failure
- 🔄 **Disable crash** button that restores the healthy subtree
- 📊 A sidebar showing `crash_count`, `last_error`, and `log_entries` (last 5 entries)
- 📡 Telemetry: each crash emits a `render_error` event to the `TelemetryProvider`
- 📋 Structured logging: each crash produces a `WARNING` `LogRecord`

---

## Prerequisites

```bash
pip install tempestweb
```

Recommended reading:

- [Basic tutorial](../tutorial/index.md) — `App`, `view`, `set_state`
- [Managing state](../tutorial/state.md) — mutators and closures
- [Execution modes](../tutorial/modes.md) — WASM vs. server

---

## Creating the project

```bash
mkdir -p examples/error-boundary
touch examples/error-boundary/app.py
```

---

## Step 1 — Understanding `ErrorBoundary`

`ErrorBoundary` is a core `Component`. You pass two key arguments:

- `child_builder` — a `() -> Widget` function that may raise
- `on_error` — a `(ErrorInfo) -> None` hook called when the exception is caught

When `child_builder()` raises, the boundary:

1. Captures the exception into an `ErrorInfo` (type, message, stack)
2. Calls `on_error(info)` — for logging, telemetry, or any other action
3. Renders `fallback_builder(info)` in place of the broken subtree
4. **Never re-raises** — the rest of the app keeps rendering normally

```python
from tempestweb.observability import ErrorBoundary, ErrorInfo

reported: list[ErrorInfo] = []

def broken() -> Text:
    raise ValueError("boom")

boundary = ErrorBoundary(child_builder=broken, on_error=reported.append)
rendered = boundary.render()  # does not raise — calls on_error and returns the fallback
assert reported[0].error_type == "ValueError"
```

!!! tip "Tip — `ErrorInfo` has everything you need"
    `ErrorInfo` is a `dataclass(frozen=True)` with four fields:

    | Field | Type | Content |
    |---|---|---|
    | `error` | `BaseException` | The original exception |
    | `error_type` | `str` | Class name (`"RuntimeError"`) |
    | `message` | `str` | `str(error)` |
    | `stack` | `str` | Formatted traceback |

    `error_type` and `message` are safe to show the user. `stack` goes to the log/telemetry — never directly on screen.

---

## Step 2 — Defining the state

The state needs to capture everything the UI must reflect after a crash:

```python
from __future__ import annotations

from dataclasses import dataclass, field


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
```

!!! info "Why `log_entries` in state?"
    The log panel needs to be reactive — it must update automatically when a new crash happens. Because tempestweb is state-driven, the only way for something to appear in the UI is for it to be in the state. That is why we capture entries in `log_entries` via `set_state` inside `on_error`.

---

## Step 3 — Setting up the observability sinks

Before `view`, we create both sinks **at module level**. This is important: in a real app all components should fan into the same telemetry pipeline.

### The Logger

```python
from tempestweb.observability import LogRecord, create_logger

#: Captures every LogRecord emitted during the session.
_log_records: list[LogRecord] = []


def _record_sink(record: LogRecord) -> None:
    """Append a log record to the module-level capture list.

    Args:
        record: The structured log record to store.

    Returns:
        None.
    """
    _log_records.append(record)


_logger = create_logger(sinks=[_record_sink], level="WARNING")
```

`create_logger` accepts a list of sinks — any callable `(LogRecord) -> None`. Here we pass `_record_sink` to capture records for inspection (and tests). In production you would also pass a `network_sink` that forwards to your backend.

!!! tip "Tip — `WARNING` level"
    We set `level="WARNING"` so that `DEBUG` and `INFO` are dropped before any sink runs. Render errors are always `WARNING` or higher, so nothing is lost.

### The TelemetryProvider

```python
from typing import Any

from tempestweb.observability import ConsoleTelemetryAdapter, TelemetryProvider

#: Captures every telemetry event for inspection.
_telemetry_events: list[tuple[str, dict[str, Any]]] = []


def _make_telemetry_provider() -> TelemetryProvider:
    """Build a TelemetryProvider that captures events into the module list.

    Returns:
        A configured provider backed by a ConsoleTelemetryAdapter whose
        sink is also appending to _telemetry_events for test inspection.
    """

    def _sink(message: str) -> None:
        # Parse the "[telemetry] track <event> <props>" line emitted by the adapter.
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


_telemetry_provider = _make_telemetry_provider()
```

`ConsoleTelemetryAdapter` formats each event as the string `[telemetry] track <event> <props>` and passes it to the `sink`. By injecting a custom `sink`, we get both visibility in the console (good for dev) and structured capture (good for tests).

!!! note "Note — swappable adapters"
    Switching from `ConsoleTelemetryAdapter` to `SentryTelemetryAdapter` or `PostHogTelemetryAdapter` is a single line of code — the rest of the app does not change. The adapter pattern is the heart of Track O.

---

## Step 4 — The `on_error` hook

The `on_error` hook is where everything connects. It receives an `ErrorInfo` and has three responsibilities:

```python
from tempestweb.observability import ErrorInfo, telemetry_reporter


def on_error(info: ErrorInfo) -> None:
    """Handle a captured render error: log it, track it, update state.

    Args:
        info: The captured render failure from the boundary.
    """
    # 1. Structured log — WARNING level
    _logger.warning(
        "render_error_caught",
        error_type=info.error_type,
        error_msg=info.message,
    )
    # 2. Telemetry — forward to the provider
    telemetry_reporter(_telemetry_provider)(info)

    # 3. State — mirror the crash onto the UI
    def _update(s: BoundaryState) -> None:
        s.crash_count += 1
        s.last_error = f"{info.error_type}: {info.message}"
        entry = f"[{info.error_type}] {info.message}"
        s.log_entries = (s.log_entries + [entry])[-5:]  # keep only the last 5

    app.set_state(_update)
```

Let's break down each part:

**`_logger.warning(...)`** — emits a `LogRecord` with `level="WARNING"`. The extra kwargs (`error_type`, `error_msg`) land in `record.fields` for any sink to consume. Note the use of `error_msg` rather than `message` to avoid shadowing the positional parameter of `Logger.warning`.

**`telemetry_reporter(_telemetry_provider)(info)`** — `telemetry_reporter` is a factory that takes a `TelemetryProvider` and returns an `ErrorReporter`. When called with `info`, it calls `provider.track("render_error", {...})` with the `error_type`, `message`, and `stack` fields.

**`app.set_state(_update)`** — updates state so the UI reflects the crash. The log panel and counter are reactive: they appear on the next render automatically.

!!! warning "Warning — `on_error` is called during render"
    `on_error` is called **synchronously** inside `ErrorBoundary.render()`. Do not do blocking I/O here. Network sinks should be fire-and-forget (enqueue and send in the background).

---

## Step 5 — The `child_builder` and `toggle_boom`

The "protected subtree" is a simple function that raises when `state.boom` is `True`:

```python
def child_builder() -> Widget:
    """Build the protected subtree; raises when state.boom is set.

    Returns:
        A healthy widget showing the render count, or raises
        RuntimeError when state.boom is True.

    Raises:
        RuntimeError: When state.boom is True, simulating a widget that
            fails to render due to bad data or a missing dependency.
    """
    if app.state.boom:
        raise RuntimeError("simulated render failure — bad data upstream")

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
```

And the button handler that toggles the crash:

```python
def toggle_boom() -> None:
    """Flip the boom flag to trigger / clear the simulated crash."""
    app.set_state(lambda s: setattr(s, "boom", not s.boom))
```

!!! tip "Tip — simulate real failures"
    In a real app, `child_builder` would be something like `lambda: UserProfileCard(user=fetch_user(id))` where `fetch_user` might return `None`. The `RuntimeError` here is just a shortcut for the demo. The pattern is identical.

---

## Step 6 — Assembling the layout

The layout has four sections outside the boundary (never affected by it) and the boundary itself:

```python
from tempest_core import App, Button, Column, Row, Style, Text, Widget
from tempest_core.style import Edge


def view(app: App[BoundaryState]) -> Widget:
    """Render the error-boundary demo UI from the current state."""

    # ... (handlers defined here — see steps 4 and 5)

    status_text = "CRASH MODE ON" if app.state.boom else "healthy"
    toggle_label = "Disable crash" if app.state.boom else "Trigger crash"

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
```

!!! check "Key point — the outer layout never breaks"
    The header, control buttons, last-error display, and log panel are **outside** the `ErrorBoundary`. They continue rendering normally even when `child_builder` raises. Only the boundary area (where `healthy-subtree` or the fallback appears) is affected by the crash.

---

## The complete app

Here is the full file, ready to copy:

```python
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

from tempest_core import App, Button, Column, Row, Style, Text, Widget
from tempest_core.style import Edge
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
```

---

## Running the example ▶

### Mode A — Python in the browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm --path examples/error-boundary
```

Python runs **inside the browser** via Pyodide. No server required. Ideal for demos and prototypes.

### Mode B — Python on the server (FastAPI + WebSocket)

```bash
tempestweb dev --mode server --path examples/error-boundary
```

Python runs on the server; the browser receives JSON patches over WebSocket and applies them to the DOM. Ideal for production with SEO and fast first-paint.

!!! check "Verification"
    In either mode, you should see:

    1. Title **"Error Boundary Demo"**
    2. Button **Trigger crash** + Status: **healthy** + **Crashes caught: 0**
    3. Healthy subtree: _"Protected subtree is healthy."_ + _"Successful renders: N"_
    4. _"No error captured yet."_ below
    5. Log panel: _"No errors captured yet."_

    After clicking **Trigger crash**:

    6. Button changes to **Disable crash** + Status: **CRASH MODE ON**
    7. The boundary area shows the fallback: _"Something went wrong."_ + `(RuntimeError)`
    8. **Crashes caught: 1** updates
    9. _"Last error: RuntimeError: simulated render failure — bad data upstream"_
    10. Log panel adds `[RuntimeError] simulated render failure — bad data upstream`
    11. The header, buttons, and log panel **remain visible and functional**

    After clicking **Disable crash**:

    12. Healthy subtree returns — _"Protected subtree is healthy."_
    13. `render_count` resumes counting

---

## Automated verification ✅

```bash
# Lint
ruff check .

# Formatting
ruff format --check .

# Types
mypy --strict tempestweb

# Tests (14 tests, all green)
pytest -q tests/unit/test_example_error_boundary.py
```

!!! note "Note — 14 tests covering the full cycle"
    The suite covers: initial mount, widget types in the tree, initial state, fallback with boom=True, crash_count/last_error updates, log_entries, ErrorInfo capture, telemetry event via telemetry_reporter, module-level capture, recovery, diff between states, crash_count accumulation after multiple cycles, and the 5-entry log cap.

---

## How it works under the hood

### The full crash flow

```
view(app) called
      │
      ▼
ErrorBoundary.render()
      │
      ├─ child_builder() → raises RuntimeError
      │
      ▼
ErrorInfo.from_exception(exc)
      │
      ├─ on_error(info)
      │       ├─ _logger.warning(...)     → LogRecord in _log_records
      │       ├─ telemetry_reporter(...)  → event in _telemetry_events
      │       └─ app.set_state(_update)   → crash_count++, last_error, log_entries
      │
      ▼
fallback_builder(info) → Column("Something went wrong.", "(RuntimeError)")
      │
      ▼
Rest of the layout keeps rendering normally
```

### Why is `telemetry_reporter` a factory?

`telemetry_reporter(provider)` takes a `TelemetryProvider` and returns an `ErrorReporter` (which is just `Callable[[ErrorInfo], None]`). This lets you compose the reporter with other reporters or pass it directly as `on_error`:

```python
# Direct form — without a custom logger
boundary = ErrorBoundary(
    child_builder=risky_component,
    on_error=telemetry_reporter(my_provider),
)

# Composed form — with logger + telemetry (as in this example)
def on_error(info: ErrorInfo) -> None:
    _logger.warning("render_error_caught", error_type=info.error_type)
    telemetry_reporter(my_provider)(info)
    app.set_state(lambda s: setattr(s, "crash_count", s.crash_count + 1))
```

### The `@with_error_boundary` decorator

For simple cases where you want to protect an existing builder without changing its call site, use the decorator:

```python
from tempestweb.observability import with_error_boundary

@with_error_boundary(on_error=telemetry_reporter(my_provider))
def profile_card() -> Widget:
    # may raise — now protected
    return Column(children=[Text(content=user.name)])
```

`profile_card()` now returns an `ErrorBoundary` instead of a `Widget` directly — transparent to callers.

### `log_entries` is capped at 5

The log panel uses a `[-5:]` slice to keep at most 5 entries:

```python
s.log_entries = (s.log_entries + [entry])[-5:]
```

This prevents the panel from growing unboundedly in production where crashes can accumulate.

---

## Recap

In this tutorial you learned:

- ✅ Use `ErrorBoundary` to contain render failures in specific subtrees
- ✅ Understand the fields of `ErrorInfo` (`error_type`, `message`, `stack`)
- ✅ Wire `on_error` to a structured `Logger` with `create_logger`
- ✅ Use `telemetry_reporter` to forward crashes to a `TelemetryProvider`
- ✅ Use `ConsoleTelemetryAdapter` with an injectable sink for dev and tests
- ✅ Update app state inside `on_error` via `app.set_state`
- ✅ Cap reactive lists to a maximum size with `[-N:]` slicing
- ✅ Create module-level observability sinks for component fan-in
- ✅ Use the `@with_error_boundary` decorator to protect existing builders

---

## Next steps

- 💡 Swap `ConsoleTelemetryAdapter` for `SentryTelemetryAdapter` to see the same pattern directing crashes to Sentry
- 💡 Add a second sink to `create_logger` that sends records to an HTTP endpoint in the background
- 💡 Explore [Feature Flags](./feature-flags.en.md) (Track O3) to disable unstable features without a deploy
- 💡 Explore [JWT auth gate](./auth-jwt.en.md) (Track O4) to protect routes with JWT + automatic refresh
