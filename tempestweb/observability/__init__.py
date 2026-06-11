"""Trilho O — production / observability providers (adapter pattern).

Every provider here follows the same shape: a tiny, stable interface application
code calls, plus one or more swappable adapters behind it. Changing the backend
never touches a call site.

Modules:
    * :mod:`telemetry` (O0) — ``track`` / ``identify`` with console/Sentry/PostHog
      adapters.
    * :mod:`logger` (O1) — structured logging with pluggable sinks and typed
      levels.

Import everything from this package level rather than from submodules.
"""

from tempestweb.observability.error_boundary import (
    ChildBuilder,
    ErrorBoundary,
    ErrorInfo,
    ErrorReporter,
    FallbackBuilder,
    default_fallback,
    telemetry_reporter,
    with_error_boundary,
)
from tempestweb.observability.logger import (
    Logger,
    LoggerSink,
    LogLevel,
    LogRecord,
    console_sink,
    create_logger,
)
from tempestweb.observability.telemetry import (
    ConsoleTelemetryAdapter,
    PostHogTelemetryAdapter,
    SentryTelemetryAdapter,
    TelemetryAdapter,
    TelemetryProvider,
)

__all__ = [
    "TelemetryAdapter",
    "TelemetryProvider",
    "ConsoleTelemetryAdapter",
    "SentryTelemetryAdapter",
    "PostHogTelemetryAdapter",
    "LogLevel",
    "LogRecord",
    "LoggerSink",
    "Logger",
    "console_sink",
    "create_logger",
    "ErrorInfo",
    "ErrorReporter",
    "FallbackBuilder",
    "ChildBuilder",
    "ErrorBoundary",
    "default_fallback",
    "with_error_boundary",
    "telemetry_reporter",
]
