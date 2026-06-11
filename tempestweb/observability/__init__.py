"""Trilho O — production / observability providers (adapter pattern).

Every provider here follows the same shape: a tiny, stable interface application
code calls, plus one or more swappable adapters behind it. Changing the backend
(console -> Sentry, in-memory flags -> LaunchDarkly, ...) never touches a call
site.

Modules:
    * :mod:`telemetry` (O0) — ``track`` / ``identify`` with console/Sentry/PostHog
      adapters.
    * :mod:`logger` (O1) — structured logging with pluggable sinks and typed
      levels.
    * :mod:`error_boundary` (O2) — render-error fallback widget/decorator plus a
      report hook into telemetry.
    * :mod:`feature_flags` (O3) — runtime toggles with in-memory / GrowthBook /
      LaunchDarkly adapters.
    * :mod:`auth` (O4) — token store, route guard, JWT helpers and a refresh queue
      that serializes concurrent renewals.

Import everything from this package level rather than from submodules.
"""

from tempestweb.observability.auth import (
    AuthListener,
    AuthState,
    AuthStore,
    JWTError,
    RefreshFn,
    RefreshQueue,
    create_auth_store,
    create_refresh_queue,
    decode_jwt,
    is_jwt_expired,
    route_guard,
    server_decode_jwt,
)
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
from tempestweb.observability.feature_flags import (
    ChangeListener,
    FeatureFlagsAdapter,
    FeatureFlagsProvider,
    FlagValue,
    GrowthBookFeatureFlagsAdapter,
    InMemoryFeatureFlagsAdapter,
    LaunchDarklyFeatureFlagsAdapter,
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
    "FlagValue",
    "ChangeListener",
    "FeatureFlagsAdapter",
    "FeatureFlagsProvider",
    "InMemoryFeatureFlagsAdapter",
    "GrowthBookFeatureFlagsAdapter",
    "LaunchDarklyFeatureFlagsAdapter",
    "JWTError",
    "decode_jwt",
    "is_jwt_expired",
    "AuthState",
    "AuthStore",
    "AuthListener",
    "create_auth_store",
    "route_guard",
    "RefreshQueue",
    "RefreshFn",
    "create_refresh_queue",
    "server_decode_jwt",
]
