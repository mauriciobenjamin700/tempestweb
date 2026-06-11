"""Unit tests for O0 telemetry: provider, sampling, and adapter swapping."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from tempestweb.observability import (
    ConsoleTelemetryAdapter,
    PostHogTelemetryAdapter,
    SentryTelemetryAdapter,
    TelemetryProvider,
)


class RecordingAdapter:
    """A test adapter that records every track/identify call."""

    def __init__(self) -> None:
        self.tracked: list[tuple[str, dict[str, Any]]] = []
        self.identified: list[tuple[str, dict[str, Any]]] = []

    def track(self, event: str, props: dict[str, Any]) -> None:
        self.tracked.append((event, props))

    def identify(self, user_id: str, traits: dict[str, Any]) -> None:
        self.identified.append((user_id, traits))


def test_track_and_identify_forward_to_adapter() -> None:
    adapter = RecordingAdapter()
    provider = TelemetryProvider(adapter)

    provider.identify("u1", {"plan": "pro"})
    provider.track("offline_replay", {"queued": 3})

    assert adapter.identified == [("u1", {"plan": "pro"})]
    assert adapter.tracked == [("offline_replay", {"queued": 3})]


def test_default_props_merged_into_every_event() -> None:
    adapter = RecordingAdapter()
    provider = TelemetryProvider(adapter, default_props={"mode": "wasm"})

    provider.track("push_subscribed", {"endpoint": "x"})
    provider.track("no_props")

    assert adapter.tracked[0] == ("push_subscribed", {"mode": "wasm", "endpoint": "x"})
    assert adapter.tracked[1] == ("no_props", {"mode": "wasm"})


def test_per_event_props_override_defaults() -> None:
    adapter = RecordingAdapter()
    provider = TelemetryProvider(adapter, default_props={"mode": "wasm"})

    provider.track("e", {"mode": "server"})

    assert adapter.tracked[0][1] == {"mode": "server"}


def test_sample_rate_zero_drops_all_track_but_not_identify() -> None:
    adapter = RecordingAdapter()
    provider = TelemetryProvider(adapter, sample_rate=0.0)

    for _ in range(10):
        provider.track("noise")
    provider.identify("u1")

    assert adapter.tracked == []
    assert adapter.identified == [("u1", {})]


def test_sample_rate_half_forwards_roughly_half() -> None:
    adapter = RecordingAdapter()
    provider = TelemetryProvider(adapter, sample_rate=0.5)

    for _ in range(100):
        provider.track("e")

    # Deterministic 1-in-2 spread; exactly half forwarded.
    assert len(adapter.tracked) == 50


def test_invalid_sample_rate_raises() -> None:
    with pytest.raises(ValueError, match="sample_rate"):
        TelemetryProvider(RecordingAdapter(), sample_rate=1.5)


def test_swapping_adapter_changes_no_call_sites() -> None:
    # The exact same provider-facing calls drive different backends.
    def emit(provider: TelemetryProvider) -> None:
        provider.identify("u1", {"plan": "pro"})
        provider.track("event_a", {"k": "v"})

    console_lines: list[str] = []
    console = TelemetryProvider(ConsoleTelemetryAdapter(console_lines.append))
    recording_adapter = RecordingAdapter()
    recording = TelemetryProvider(recording_adapter)

    emit(console)
    emit(recording)

    assert any("event_a" in line for line in console_lines)
    assert recording_adapter.tracked == [("event_a", {"k": "v"})]


def test_console_adapter_uses_injected_sink() -> None:
    lines: list[str] = []
    adapter = ConsoleTelemetryAdapter(lines.append)

    adapter.track("e", {"a": 1})
    adapter.identify("u1", {"x": "y"})

    assert lines[0].startswith("[telemetry] track e")
    assert lines[1].startswith("[telemetry] identify u1")


def test_sentry_adapter_wraps_injected_client() -> None:
    client = MagicMock()
    provider = TelemetryProvider(SentryTelemetryAdapter(client))

    provider.track("boom", {"detail": "x"})
    provider.identify("u1", {"email": "a@b.c"})

    client.capture_message.assert_called_once_with(
        "boom", level="info", extras={"detail": "x"}
    )
    client.set_user.assert_called_once_with({"id": "u1", "email": "a@b.c"})


def test_posthog_adapter_wraps_injected_client_and_binds_distinct_id() -> None:
    client = MagicMock()
    adapter = PostHogTelemetryAdapter(client)
    provider = TelemetryProvider(adapter)

    provider.track("before_identify", {"k": 1})
    provider.identify("u1", {"plan": "pro"})
    provider.track("after_identify", {"k": 2})

    client.capture.assert_any_call(
        distinct_id="anonymous", event="before_identify", properties={"k": 1}
    )
    client.identify.assert_called_once_with(
        distinct_id="u1", properties={"plan": "pro"}
    )
    client.capture.assert_any_call(
        distinct_id="u1", event="after_identify", properties={"k": 2}
    )
