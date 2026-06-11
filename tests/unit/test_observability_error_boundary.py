"""Unit tests for O2 error boundary: fallback, reporting, decorator, telemetry."""

from __future__ import annotations

from typing import Any

from tempestweb._core import Column, Text, Widget
from tempestweb.observability import (
    ErrorBoundary,
    ErrorInfo,
    TelemetryProvider,
    default_fallback,
    telemetry_reporter,
    with_error_boundary,
)


def _ok() -> Text:
    return Text(content="hello")


def _broken() -> Widget:
    raise ValueError("render boom")


def test_successful_render_passes_child_through() -> None:
    boundary = ErrorBoundary(child_builder=_ok)
    rendered = boundary.render()

    assert isinstance(rendered, Text)
    assert rendered.content == "hello"


def test_render_error_yields_fallback_instead_of_raising() -> None:
    boundary = ErrorBoundary(child_builder=_broken)
    rendered = boundary.render()

    assert isinstance(rendered, Column)


def test_render_error_invokes_report_hook_with_error_info() -> None:
    reported: list[ErrorInfo] = []
    boundary = ErrorBoundary(child_builder=_broken, on_error=reported.append)

    boundary.render()

    assert len(reported) == 1
    assert reported[0].error_type == "ValueError"
    assert reported[0].message == "render boom"
    assert "ValueError" in reported[0].stack


def test_custom_fallback_receives_error_info() -> None:
    def fallback(info: ErrorInfo) -> Text:
        return Text(content=f"failed: {info.error_type}")

    boundary = ErrorBoundary(child_builder=_broken, fallback_builder=fallback)
    rendered = boundary.render()

    assert isinstance(rendered, Text)
    assert rendered.content == "failed: ValueError"


def test_default_fallback_is_renderer_agnostic_column() -> None:
    info = ErrorInfo.from_exception(ValueError("x"))
    widget = default_fallback(info)

    assert isinstance(widget, Column)
    assert isinstance(widget.children[0], Text)


def test_decorator_wraps_builder_into_boundary() -> None:
    reported: list[ErrorInfo] = []

    @with_error_boundary(on_error=reported.append)
    def card() -> Widget:
        raise RuntimeError("nope")

    boundary = card()
    assert isinstance(boundary, ErrorBoundary)

    rendered = boundary.render()
    assert isinstance(rendered, Column)
    assert reported[0].error_type == "RuntimeError"


def test_telemetry_reporter_forwards_render_error_to_provider() -> None:
    tracked: list[tuple[str, dict[str, Any]]] = []

    class Adapter:
        def track(self, event: str, props: dict[str, Any]) -> None:
            tracked.append((event, props))

        def identify(self, user_id: str, traits: dict[str, Any]) -> None:
            pass

    provider = TelemetryProvider(Adapter())
    boundary = ErrorBoundary(
        child_builder=_broken, on_error=telemetry_reporter(provider)
    )

    boundary.render()

    assert tracked[0][0] == "render_error"
    assert tracked[0][1]["error_type"] == "ValueError"
    assert tracked[0][1]["message"] == "render boom"
