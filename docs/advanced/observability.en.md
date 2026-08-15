# Observability

The **observability / production** layer (Track O) gives your app telemetry,
structured logs, an error boundary, feature flags and client auth — all in
**typed Python**, identical whether Python runs in the browser (Mode A) or on the
server (Mode B). 📊

!!! info "Under construction (Track O)"
    This layer is the roadmap's **Track O**. Phases O0–O4 are detailed in the
    [design plan](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/plan.md).
    This page describes the **planned surface** and the adapter pattern.

## The adapter pattern

Every provider follows the same principle: a **minimal interface** that you swap
without touching the app. You program against the API; the adapter decides where
it goes (console, Sentry, GrowthBook, …).

```text
   your app  ──calls──▶  Provider (stable API)  ──delegates──▶  Adapter (backend)
                                                                console / sentry / posthog / ...
```

!!! check "Swapping backend does not change calls"
    Migrating from `console` to `sentry` changes **no** `track()` call. It is the
    same promise as `tempest-react-sdk`, now in typed Python.

## O0 — Telemetry

Instruments framework and app events (service worker, push, offline replay,
errors) with a pluggable provider.

```python
from tempestweb.observability import telemetry
from tempestweb.observability.telemetry import ConsoleAdapter


telemetry.init(adapter=ConsoleAdapter())

telemetry.track("order_submitted", {"items": 3, "total": 99.9})
telemetry.identify("user-42")
```

!!! warning "Do not leak PII"
    Do not put personal data in `props`, and use sampling so you do not flood the
    backend. Telemetry is diagnostics, not a user database.

## O1 — Logger

Structured logging with **pluggable sinks** and typed levels (`LogLevel`).

```python
from tempestweb.observability import create_logger, console_sink

log = create_logger(sinks=[console_sink])

log.info("order created", order_id="o-1", total=99.9)
log.error("payment failed", order_id="o-1", reason="card_declined")
```

!!! note "In Mode A the default sink is the browser console"
    Network sinks (sending logs to a server) must be **async/non-blocking** — in
    Mode A a blocking sink freezes the tab.

## O2 — Error boundary

Captures **render** errors → shows a visual fallback + fires a report, without
bringing the app down. The rest of the tree stays alive.

```python
from tempestweb.observability import error_boundary
from tempest_core import Text, Widget


@error_boundary(fallback=lambda err: Text(content=f"Something broke: {err}"))
def risky_panel(app: object) -> Widget:
    """Render a panel that may raise during build.

    Args:
        app: The running app handle.

    Returns:
        The rendered panel widget.
    """
    return build_dashboard(app.state)   # if it raises, the fallback appears
```

!!! tip "Render error ≠ async handler error"
    The boundary catches **render** errors (during `view()`). Async handler errors
    go to the event loop's handling. In both cases, **report** — never swallow the
    stack.

## O3 — Feature flags

Toggles features at runtime with gradual rollout. The adapter interface is tiny
(~20 lines to implement a new one).

```python
from tempestweb.observability import feature_flags
from tempestweb.observability.feature_flags import InMemoryAdapter


feature_flags.init(adapter=InMemoryAdapter({"new_checkout": True}))


def view(app: object) -> object:
    """Render checkout, gated by a feature flag."""
    if feature_flags.is_enabled("new_checkout"):
        return new_checkout(app)
    return legacy_checkout(app)
```

!!! warning "Flags are not secrets; have a safe default"
    When the flags backend is down, `is_enabled` must fall back to a **safe
    default** — never break the app. And never use flags to hide secrets: they are
    visible on the client.

## O4 — Client auth

Auth store + route guard + JWT helpers + a **refresh queue** that serializes
concurrent renewals (one refresh, many waiters).

```python
from tempestweb.observability import create_auth_store, create_refresh_queue

auth = create_auth_store()
refresh = create_refresh_queue(auth)


async def call_api(app: object) -> dict[str, object]:
    """Call a protected endpoint, refreshing the token once if needed.

    Args:
        app: The running app handle.

    Returns:
        The decoded JSON response.
    """
    if auth.is_token_expired():
        await refresh.run()   # many concurrent calls => ONE refresh
    response = await app.native.http.request(
        "GET", "/api/me", headers={"Authorization": f"Bearer {auth.token}"}
    )
    return response.json()
```

!!! danger "The token lives in different places per mode"
    In **Mode A** the token lives in the browser (storage) — treat **XSS** as a
    real risk. In **Mode B** it lives in the server session, more protected. The
    server reuses `JWTUtils` from `tempest-fastapi-sdk`.

## Recap

- Observability uses the **adapter pattern**: swap the backend without changing
  the app.
- **Telemetry** (O0), **Logger** (O1), **Error boundary** (O2), **Feature flags**
  (O3) and **Auth** (O4) are all typed Python, identical in Modes A and B.
- Safe defaults and care with PII/tokens are part of the contract.

This layer mirrors the `tempest-react-sdk` providers. For phase-by-phase detail,
read the
[design plan](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/plan.md).
🚀
