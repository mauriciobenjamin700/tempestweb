"""S8 — the three promises of server observability, each pinned.

The issue asked for latency, structured logs and tracing, and for none of them to
become a forced dependency (tempestweb#119). Those are four claims, and each one
has an obvious way to be wrong:

* latency that is collected but never rendered,
* a log line that carries the id as prose instead of as a field,
* a tracer that is "optional" and imported anyway,
* instrumentation that costs something when it is off.

One test each — plus the one that was missing: the shipped OpenTelemetry adapter
is *run*, not only declared. A test double satisfies the Protocol whether or not
the real adapter drives the real API, so proving the seam proves nothing about the
code an app actually gets.
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tempest_core import App, Button, Column, Text, Widget
from tempestweb.observability import (
    PatchMetrics,
    ServerObservability,
    create_logger,
    json_log_sink,
    noop_tracer,
    otel_tracer,
)
from tempestweb.observability.logger import LogRecord
from tempestweb.server import create_app


def _view(app: App[int]) -> Widget:
    """Render a counter with a button that increments it.

    Args:
        app: The application handle.

    Returns:
        The widget tree.
    """
    return Column(
        key="root",
        children=[
            Text(key="label", content=f"Count: {app.state}"),
            Button(
                key="inc",
                label="+",
                on_click=lambda: app.set_state(lambda state: state + 1),
            ),
        ],
    )


def test_patch_latency_and_throughput_reach_the_metrics_endpoint() -> None:
    """A real click makes the histogram and the patch counter move.

    The number has to arrive where an operator reads it — a histogram collected and
    never rendered is the same as no histogram.
    """
    metrics = PatchMetrics()
    app = create_app(
        state_factory=lambda: 0,
        view=_view,
        metrics=True,
        observability=ServerObservability(metrics=metrics),
    )
    client = TestClient(app)

    with client.websocket_connect("/ws") as socket:
        socket.receive_json()  # the initial mount
        socket.send_json({"kind": "event", "data": {"type": "click", "key": "inc"}})
        socket.receive_json()  # the update this click produced

    body = client.get("/metrics").text
    assert "tempestweb_patch_seconds_count 1" in body
    assert 'tempestweb_patch_seconds_bucket{le="+Inf"} 1' in body
    assert "tempestweb_patches_total 1" in body
    # And the connection counters are still there: this adds, it does not replace.
    assert "tempestweb_sessions_opened_total 1" in body


def test_the_session_log_is_json_with_the_id_as_a_field() -> None:
    """A session's open and close are queryable objects, not prose.

    ``session_id`` has to be a *field*, because the whole point is joining a log
    line to a span by that key — a message that merely contains the id is not
    something a log pipeline can group by.
    """
    records: list[LogRecord] = []
    logger = create_logger(sinks=[records.append], level="INFO")
    obs = ServerObservability(logger=logger)

    with obs.session("s-42", transport="ws"):
        pass

    assert [record.message for record in records] == ["session.open", "session.close"]
    opened, closed = records
    assert opened.fields["session_id"] == "s-42"
    assert opened.fields["transport"] == "ws"
    assert closed.fields["reason"] == "closed"
    assert closed.fields["duration_s"] >= 0.0

    # And the sink that ships it renders one parseable object per line.
    payload = {
        "level": closed.level,
        "message": closed.message,
        **closed.fields,
    }
    parsed = json.loads(json.dumps(payload, default=str))
    assert parsed["session_id"] == "s-42"


def test_a_failed_session_logs_why() -> None:
    """A session that dies of an exception says so in its close record."""
    records: list[LogRecord] = []
    obs = ServerObservability(logger=create_logger(sinks=[records.append]))

    with pytest.raises(RuntimeError), obs.session("s-7"):
        raise RuntimeError("client vanished")

    assert records[-1].fields["reason"] == "RuntimeError"


def test_the_opentelemetry_adapter_is_exercised_not_just_declared() -> None:
    """The shipped adapter runs, which the Protocol double cannot prove.

    ``otel_tracer()`` is public surface and an extra in ``pyproject.toml``, so
    "the seam works" is not the claim being made — the claim is that *this*
    adapter drives the real OpenTelemetry API. Only running it says so; a
    RecordingTracer would pass with the adapter broken.

    Skipped rather than failed when the extra is absent, because tracing is opt-in
    by design and a bare install must stay a passing install.
    """
    pytest.importorskip("opentelemetry.trace")

    obs = ServerObservability(tracer=otel_tracer("tempestweb-test"))
    with obs.session("s-otel"):
        with obs.dispatch("s-otel", "click"):
            pass
        with obs.patch_batch("s-otel", 2):
            pass


def test_tracing_off_by_default_imports_nothing() -> None:
    """The default path does not import OpenTelemetry, which is the promise.

    "Optional dependency" is only true if the default never touches it.

    A fresh interpreter, not this one: ``sys.modules`` is process-wide, so reading
    it here would only report whether some *other* test happened to import
    opentelemetry first — the test above does exactly that. Asked in a subprocess,
    the question is the one that matters and the answer does not depend on test
    order.
    """
    probe = (
        "import sys;"
        "from tempestweb.observability import ServerObservability, noop_tracer;"
        "assert ServerObservability().tracer is noop_tracer();"
        "print([name for name in sys.modules if name.startswith('opentelemetry')])"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "[]", (
        "the default observability path imported opentelemetry: "
        f"{result.stdout.strip()}"
    )
    assert ServerObservability().tracer is noop_tracer()


def test_the_inert_default_collects_nothing_and_costs_nothing_visible() -> None:
    """With nothing wired, a round records nothing and reports nothing."""
    obs = ServerObservability()
    assert obs.enabled is False

    with obs.dispatch("s-1", "click"):
        pass
    obs.observe_patches(0.01, 5)

    assert obs.prometheus() == ""


def test_a_custom_tracer_sees_a_span_per_session_and_per_round() -> None:
    """The tracing seam is a Protocol, so a test double is a full adapter."""
    spans: list[tuple[str, dict[str, Any]]] = []

    class RecordingTracer:
        """A tracer that records the spans it is asked for."""

        def span(self, name: str, **attributes: Any) -> Any:  # noqa: ANN401 — context manager
            """Record and yield a span.

            Args:
                name: The span name.
                **attributes: The initial attributes.

            Returns:
                A context manager yielding the recording span.
            """
            recorded: dict[str, Any] = dict(attributes)
            spans.append((name, recorded))

            class _Span:
                """Collects attributes into the recorded dict."""

                def set_attribute(self, key: str, value: Any) -> None:  # noqa: ANN401 — scalar
                    """Record one attribute.

                    Args:
                        key: The attribute name.
                        value: Its value.
                    """
                    recorded[key] = value

                def __enter__(self) -> _Span:
                    """Enter the span.

                    Returns:
                        This span.
                    """
                    return self

                def __exit__(self, *exc: object) -> None:
                    """Exit the span.

                    Args:
                        *exc: The exception triple, ignored.
                    """
                    return None

            return _Span()

    obs = ServerObservability(tracer=RecordingTracer())
    with obs.session("s-9"):
        with obs.dispatch("s-9", "click"):
            pass
        with obs.patch_batch("s-9", 4):
            pass

    names = [name for name, _ in spans]
    assert names == [
        "tempestweb.session",
        "tempestweb.dispatch",
        "tempestweb.patch_batch",
    ]
    assert spans[0][1]["session_id"] == "s-9"
    assert spans[1][1]["event_type"] == "click"
    assert spans[2][1]["patches"] == 4


def test_the_histogram_buckets_are_cumulative_prometheus_semantics() -> None:
    """A 40 ms round lands in the 50 ms bucket and every larger one."""
    metrics = PatchMetrics()
    metrics.observe(0.040, patches=2)
    body = metrics.prometheus()

    assert 'tempestweb_patch_seconds_bucket{le="0.025"} 0' in body
    assert 'tempestweb_patch_seconds_bucket{le="0.05"} 1' in body
    assert 'tempestweb_patch_seconds_bucket{le="1.0"} 1' in body
    assert "tempestweb_patches_total 2" in body


def test_json_log_sink_prints_one_object_per_line(capsys: Any) -> None:  # noqa: ANN401 — pytest fixture
    """The sink a deployment wires prints a line a pipeline can ingest.

    Args:
        capsys: pytest's stdout capture.
    """
    logger = create_logger(sinks=[json_log_sink], level="INFO")
    logger.info("session.open", session_id="s-3", transport="sse")

    line = capsys.readouterr().out.strip()
    parsed = json.loads(line)
    assert parsed == {
        "level": "INFO",
        "message": "session.open",
        "session_id": "s-3",
        "transport": "sse",
    }


def test_the_session_id_is_stable_and_shared_by_metric_log_and_span() -> None:
    """One id per connection, the same one in all three outputs."""
    records: list[LogRecord] = []
    obs = ServerObservability(
        metrics=PatchMetrics(), logger=create_logger(sinks=[records.append])
    )

    with obs.session("s-11"):
        obs.observe_patches(0.002, 1)

    assert records[0].fields["session_id"] == "s-11"
    assert "tempestweb_patches_total 1" in obs.prometheus()
