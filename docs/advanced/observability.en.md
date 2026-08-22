# Observability

The **observability / production** layer (Track O) gives your app telemetry,
structured logs, an error boundary, feature flags and client auth — all in
**typed Python**, identical whether Python runs in the browser (Mode A) or on the
server (Mode B). 📊

!!! check "Shipped surface (Track O · O0–O4)"
    All five phases are **in the package** and importable from
    `tempestweb.observability`. Each one has a complete app under
    [Examples](../examples/index.md): [feature flags](../examples/feature-flags.md),
    [error boundary + telemetry](../examples/error-boundary.md) and
    [JWT auth](../examples/auth-jwt.md).

## The adapter pattern

Every provider follows the same principle: a **minimal interface** that you swap
without touching the app. You program against the **provider**; the adapter
decides where it goes (console, Sentry, GrowthBook, …).

```text
   your app  ──calls──▶  Provider (stable API)  ──delegates──▶  Adapter (backend)
                                                                console / sentry / posthog / ...
```

!!! check "Swapping backend does not change calls"
    Migrating from `console` to `sentry` changes **no** `track()` call. It is the
    same promise as `tempest-react-sdk`, now in typed Python.

!!! info "A provider is an object, not a singleton"
    There is no global `init()`: you **build** the provider with the adapter you
    want and keep the instance (in a module, in your `State`, wherever fits). In
    Mode A every tab has its own; in Mode B every session has its own. No hidden
    global state to leak between users.

## O0 — Telemetry

Instruments framework and app events (service worker, push, offline replay,
errors) with a pluggable provider.

```python hl_lines="3 5"
from tempestweb.observability import ConsoleTelemetryAdapter, TelemetryProvider

telemetry = TelemetryProvider(ConsoleTelemetryAdapter())

telemetry.track("order_submitted", {"items": 3, "total": 99.9})
telemetry.identify("user-42", {"plan": "pro"})
```

The constructor takes two knobs that matter in production:

```python
from tempestweb.observability import ConsoleTelemetryAdapter, TelemetryProvider

telemetry = TelemetryProvider(
    ConsoleTelemetryAdapter(),
    default_props={"app": "checkout", "release": "1.4.0"},
    sample_rate=0.1,
)
```

- `default_props` rides along on **every** event, so you stop repeating the same
  dict.
- `sample_rate=0.1` sends 10% of events — the cut happens in the provider, before
  the adapter, so the backend never sees the rest.

Swapping backend means swapping the adapter: `PostHogTelemetryAdapter`,
`SentryTelemetryAdapter`, or your own (the interface is `TelemetryAdapter`). To
capture events in a test, the console adapter takes a `sink`:

```python
from typing import Any

from tempestweb.observability import ConsoleTelemetryAdapter, TelemetryProvider

captured: list[Any] = []
telemetry = TelemetryProvider(ConsoleTelemetryAdapter(sink=captured.append))
telemetry.track("checkout_opened")
```

!!! warning "Do not leak PII"
    Keep personal data out of `props` and use `sample_rate` so you do not flood
    the backend. Telemetry is diagnostics, not a user database.

## O1 — Logger

Structured logging with **pluggable sinks** and typed levels (`LogLevel` is
`Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]`).

```python hl_lines="3"
from tempestweb.observability import console_sink, create_logger

log = create_logger(sinks=[console_sink], level="INFO")

log.info("order created", order_id="o-1", total=99.9)
log.error("payment failed", order_id="o-1", reason="card_declined")
```

Every extra `**fields` rides in the `LogRecord` (`level`, `message`, `fields`), so
a network sink serializes the whole record instead of parsing a string.

!!! note "In Mode A the default sink is the browser console"
    Network sinks (shipping logs to a server) must be **async/non-blocking** — in
    Mode A a blocking sink freezes the tab.

## O2 — Error boundary

Catches a **render** error → shows a visual fallback and fires a report, without
taking the app down. The rest of the tree stays alive.

`ErrorBoundary` is a widget, and it takes its child as a **builder**
(`child_builder`), not as an already-built widget — that is what lets it run the
build inside the `try`.

```python hl_lines="13 14 15"
from tempest_core import Text, Widget

from tempestweb.observability import (
    ErrorBoundary,
    ErrorInfo,
    TelemetryProvider,
    telemetry_reporter,
)


def panel(telemetry: TelemetryProvider) -> Widget:
    """Build the dashboard panel, guarded by a boundary."""
    return ErrorBoundary(
        key="dashboard",
        child_builder=lambda: build_dashboard(),
        fallback_builder=lambda info: Text(content=f"Something broke: {info.message}"),
        on_error=telemetry_reporter(telemetry),
    )
```

The `ErrorInfo` handed to the fallback and to `on_error` carries `error`,
`error_type`, `message` and `stack` — enough to show the type on screen and ship
the stack to the backend.

When the pattern is always the same, `with_error_boundary` builds the decorator:

```python hl_lines="6 7 8 9"
from tempest_core import Text, Widget

from tempestweb.observability import ErrorInfo, with_error_boundary


@with_error_boundary(
    fallback_builder=lambda info: Text(content=f"Something broke: {info.message}"),
)
def risky_panel() -> Widget:
    """Build a panel that may raise during build."""
    return build_dashboard()
```

The decorator wraps a **zero-argument** builder and returns another callable:
calling `risky_panel()` hands you the ready `ErrorBoundary` to put in the tree.
Without `fallback_builder`, `default_fallback` takes over.

!!! tip "Render error ≠ async handler error"
    The boundary catches **render** errors (during the child's build). Async
    handler errors go to the event loop's handling. In both cases, **report** —
    never swallow the stack.

## O3 — Feature flags

Toggles features at runtime with gradual rollout. The adapter interface is tiny
(`get` + `subscribe`), so writing a new one takes ~20 lines.

```python hl_lines="3"
from tempestweb.observability import FeatureFlagsProvider, InMemoryFeatureFlagsAdapter

flags = FeatureFlagsProvider(InMemoryFeatureFlagsAdapter({"new_checkout": True}))


def view() -> object:
    """Render checkout, gated by a feature flag."""
    if flags.is_enabled("new_checkout"):
        return new_checkout()
    return legacy_checkout()
```

- `is_enabled(key, default=False)` coerces the value to `bool` — a missing flag
  falls back to `default`.
- `get(key, default)` returns the raw value (`bool`, `str`, number) for variant
  flags: `flags.get("checkout_variant", "control")`.
- `on_change(listener)` registers a **zero-argument** callback (it says something
  changed; you re-read the flag) and returns the unsubscribe function.

```python
unsubscribe = flags.on_change(lambda: app.request_rebuild())
```

In production, swap the adapter for `GrowthBookFeatureFlagsAdapter` or
`LaunchDarklyFeatureFlagsAdapter` — no `is_enabled` call changes.

!!! warning "Flags are not secrets; keep a safe default"
    When the flag backend is down, `is_enabled` falls back to the **safe
    default** — it never breaks the app. And never use flags to hide secrets:
    they are visible on the client.

## O4 — Client auth

Auth store + route guard + JWT helpers + a **refresh queue** that serializes
concurrent renewals (one renewal, many waiters).

```python hl_lines="10 12"
from tempestweb.observability import (
    create_auth_store,
    create_refresh_queue,
    is_jwt_expired,
    route_guard,
)

auth = create_auth_store()


async def renew() -> str:
    """Fetch a fresh token from the backend.

    Returns:
        The new access token.
    """
    response = await app.native.http.request("POST", "/api/refresh")
    return str(response.json_body["token"])


refresh = create_refresh_queue(auth, renew)
guard = route_guard(auth, redirect_to="/login")


async def call_api() -> dict[str, object]:
    """Call a protected endpoint, refreshing the token once if needed.

    Returns:
        The decoded JSON response.
    """
    token = auth.token
    if token is None or is_jwt_expired(token):
        token = await refresh.refresh()
    response = await app.native.http.request(
        "GET", "/api/me", headers={"Authorization": f"Bearer {token}"}
    )
    return dict(response.json_body)
```

The queue is the subtle part: `refresh.refresh()` is **single-flight**. Ten
concurrent callers that find the token expired trigger **one** renewal and all
await the same result — `refresh.refresh_calls` counts the real renewals, and
that is what you assert in a test.

The store holds the session and notifies subscribers:

```python
from tempestweb.observability import create_auth_store

auth = create_auth_store()
auth.login(token, {"name": "Ana"})   # or set_token(token) to swap only the token
unsubscribe = auth.subscribe(lambda: app.request_rebuild())

print(auth.is_authenticated, auth.user, auth.token)
auth.logout()
```

`decode_jwt(token)` reads the claims **without** verifying the signature (this is
the client: verification is the server's job) and
`is_jwt_expired(token, leeway_seconds=30)` decides expiry with slack.

!!! danger "The token lives in different places per mode"
    In **Mode A** the token lives in the browser (storage) — treat **XSS** as a
    real risk. In **Mode B** it lives in the server session, better protected. The
    server reuses `JWTUtils` from `tempest-fastapi-sdk`, and `server_decode_jwt`
    verifies it with a secret.

## Recap

- Observability uses the **adapter pattern**: swap the backend without changing
  the app.
- **A provider is an object you build** — `TelemetryProvider(adapter)`,
  `FeatureFlagsProvider(adapter)` — there is no global `init()`.
- **Telemetry** (O0), **Logger** (O1), **Error boundary** (O2), **Feature flags**
  (O3) and **Auth** (O4) are all typed Python, identical in Modes A and B.
- `ErrorBoundary` takes **builders**, not built widgets; the refresh queue is
  **single-flight**.
- Safe defaults and care with PII/tokens are part of the contract.

This layer mirrors the `tempest-react-sdk` providers. To see it all together in a
running app, start with
[error boundary + telemetry](../examples/error-boundary.md). 🚀
