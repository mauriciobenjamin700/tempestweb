# JWT Auth Gate

Build a **login-gate app with route protection** that uses `AuthStore`,
`route_guard`, offline JWT decoding, and an audit logger — all in pure Python,
no HTML or JavaScript. 🔐

By the end of this tutorial you'll have a working app that demonstrates the
**O4 (Observability › Auth)** rail of tempestweb: `AuthStore` holds the token
and drives which screen renders, `route_guard` redirects unauthenticated users,
JWT tokens are decoded without an external library, and every relevant event
(login, logout, failure) leaves an auditable trail in the `Logger`'s `LogRecord`s.

---

## The problem

Every authenticated app needs to solve four questions at the same time:

1. **Where to keep the token?** — in an observable place that triggers re-renders
   on change.
2. **How to protect routes?** — redirect to `/login` without scattering conditionals
   all over the `view`.
3. **What does the token say?** — `sub`, `role`, `exp` live in the JWT payload
   and the client needs to read them to decide when to refresh.
4. **How to audit events?** — log logins, logouts, and failures in a structured
   way without coupling business logic to `print`.

tempestweb solves this with the auth surface of `tempestweb.observability`:
`AuthStore` (observable store), `route_guard` (pure route guard),
`decode_jwt` + `is_jwt_expired` (offline JWT helpers), and `Logger` (structured
logging with pluggable sinks).

!!! note "What you'll practice"
    - `create_auth_store` / `AuthStore` — create, populate, and observe the token
      store.
    - `route_guard` — build a guard that redirects unauthenticated requests.
    - `decode_jwt` — decode a JWT payload without verifying the signature.
    - `is_jwt_expired` — check expiry with a fixed `now` (deterministic in tests).
    - `create_logger` / `Logger` / `LogRecord` / `LoggerSink` — record events
      with level, message, and structured fields.
    - Building unsigned JWTs for demos and offline tests.

---

## Prerequisites

Make sure you have completed the [Installation](../installation.en.md) and read
the [Counter Tutorial](../tutorial/index.en.md). This example assumes you
already know `App`, `set_state`, `make_state`, and `view`.

To understand how `route_guard` maps to the full tempestweb navigation system,
see [Navigation](../tutorial/index.en.md).

---

## The complete app

This is the exact code from
[`examples/auth-jwt/app.py`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/auth-jwt/app.py).
Copy it, run it, then read the section-by-section explanation below.

```python
"""JWT auth gate — client-side auth with AuthStore, route guard, and JWT helpers.

This example wires the full O4 auth surface into a realistic login-gate pattern:

- An **AuthStore** (created via ``create_auth_store``) is held inside State and
  drives which screen renders — a login prompt when logged out, a protected
  dashboard when logged in.
- A hand-built unsigned JWT (``header.payload.signature`` with a base64url-
  encoded JSON payload) is decoded offline by ``decode_jwt`` and inspected for
  expiry via ``is_jwt_expired(token, now=<fixed>)``.
- A **Logger** records every login and logout event for auditability.
- ``route_guard`` decides which screen to show based on auth status.

The ``view`` is transport-agnostic and runs unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb run --mode server   # Python on the server (FastAPI + WebSocket)

No bridge is needed: the initial mount calls no native capability, so
``build(view(app))`` is green with no bridge installed.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Any

from tempest_core import App, Widget
from tempest_core.style import AlignItems, Color, Edge, FontWeight, Style, TextAlign
from tempest_core.widgets import (
    Button,
    Column,
    Input,
    KeyboardType,
    Row,
    Text,
)
from tempest_core.widgets.events import TextChangeEvent
from tempestweb.observability import (
    AuthStore,
    Logger,
    LoggerSink,
    LogRecord,
    create_auth_store,
    create_logger,
    decode_jwt,
    is_jwt_expired,
    route_guard,
)

# ---------------------------------------------------------------------------
# JWT helpers — build offline-verifiable tokens for the demo
# ---------------------------------------------------------------------------

# A fixed "now" timestamp used throughout the demo so expiry display is
# deterministic in tests (and in the initial render).
_DEMO_NOW: float = 1_800_000_000.0  # arbitrary fixed epoch, well in the past


def _b64url(obj: dict[str, Any]) -> str:
    """Encode *obj* as a URL-safe base64 string without padding.

    Args:
        obj: A JSON-serialisable dict.

    Returns:
        The base64url-encoded JSON without trailing ``=`` characters.
    """
    raw: bytes = json.dumps(obj, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def make_jwt(claims: dict[str, Any]) -> str:
    """Build an unsigned compact JWT carrying *claims*.

    The signature segment is the literal string ``"sig"`` — it is
    intentionally not a real HMAC so the token can be decoded offline by
    ``decode_jwt`` without a secret. **Never use this pattern in production.**

    Args:
        claims: Arbitrary JSON-serialisable claims.

    Returns:
        A ``header.payload.sig`` JWT string.
    """
    header: str = _b64url({"alg": "none", "typ": "JWT"})
    payload: str = _b64url(claims)
    return f"{header}.{payload}.sig"


# Pre-built tokens used by the demo.
# ``exp`` is set relative to _DEMO_NOW so the expiry indicator is stable:
# the "alice" token expires 1 hour after the demo epoch (= not yet expired at
# _DEMO_NOW); the "bob" token expired 1 hour before (= already expired).
_ALICE_TOKEN: str = make_jwt(
    {
        "sub": "alice",
        "name": "Alice Souza",
        "role": "admin",
        "exp": int(_DEMO_NOW) + 3600,  # expires 1 h after the demo epoch
    }
)

_BOB_TOKEN: str = make_jwt(
    {
        "sub": "bob",
        "name": "Bob Lima",
        "role": "user",
        "exp": int(_DEMO_NOW) - 3600,  # expired 1 h before the demo epoch
    }
)

# Demo credential store (username → (password, JWT)).
_CREDENTIALS: dict[str, tuple[str, str]] = {
    "alice": ("secret", _ALICE_TOKEN),
    "bob": ("p4ssw0rd", _BOB_TOKEN),
}

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class AuthAppState:
    """All mutable state for the auth-gate app.

    Attributes:
        store: The observable auth store holding the current token and user.
        log: The logger; its records are read by the view.
        username: The draft username the user is typing.
        password: The draft password the user is typing.
        error: A top-level login error message (wrong credentials, etc.).
        log_records: Accumulated log records shown in the audit trail.
        current_route: The route the app is trying to render.
    """

    store: AuthStore = field(default_factory=create_auth_store)
    log: Logger = field(init=False)
    username: str = ""
    password: str = ""
    error: str = ""
    log_records: list[LogRecord] = field(default_factory=list)
    current_route: str = "/dashboard"

    def __post_init__(self) -> None:
        """Wire up the logger with an in-state sink so records drive re-renders.

        Returns:
            None.
        """

        def _append_sink(record: LogRecord) -> None:
            """Append a log record to the state list.

            Args:
                record: The structured record to store.
            """
            self.log_records.append(record)

        sink: LoggerSink = _append_sink
        self.log = create_logger(sinks=[sink], level="INFO")


def make_state() -> AuthAppState:
    """Build the initial, logged-out application state.

    Returns:
        A fresh :class:`AuthAppState`.
    """
    return AuthAppState()


# ---------------------------------------------------------------------------
# Screen helpers
# ---------------------------------------------------------------------------


def _token_badge(token: str) -> Widget:
    """Render a small info card showing decoded JWT claims and expiry.

    Args:
        token: The JWT to inspect.

    Returns:
        A widget tree summarising the token claims and whether it is expired.
    """
    claims: dict[str, Any] = decode_jwt(token)
    expired: bool = is_jwt_expired(token, now=_DEMO_NOW)

    sub: str = str(claims.get("sub", "—"))
    role: str = str(claims.get("role", "—"))
    exp_label: str = "expired" if expired else "valid"
    exp_color: Color = (
        Color.from_hex("#dc2626") if expired else Color.from_hex("#16a34a")
    )

    return Column(
        key="token-badge",
        style=Style(
            gap=4.0,
            padding=Edge.all(12.0),
            background=Color.from_hex("#f0fdf4"),
            radius=8.0,
        ),
        children=[
            Text(
                content="JWT Claims",
                style=Style(font_weight=FontWeight.BOLD, font_size=13.0),
                key="badge-title",
            ),
            Text(content=f"sub: {sub}", key="badge-sub"),
            Text(content=f"role: {role}", key="badge-role"),
            Text(
                content=f"token: {exp_label}",
                style=Style(color=exp_color, font_weight=FontWeight.BOLD),
                key="badge-exp",
            ),
        ],
    )


def _audit_trail(records: list[LogRecord]) -> Widget:
    """Render the last few log records as a compact audit trail.

    Args:
        records: The accumulated :class:`~tempestweb.observability.LogRecord` list.

    Returns:
        A widget tree listing the records (newest last), or an empty-state row.
    """
    if not records:
        return Row(
            key="audit-empty",
            children=[
                Text(
                    content="No log entries yet.",
                    style=Style(color=Color.from_hex("#6b7280"), font_size=12.0),
                    key="audit-empty-text",
                )
            ],
        )

    entries: list[Widget] = [
        Text(
            content=f"[{r.level}] {r.message}",
            style=Style(font_size=12.0, color=Color.from_hex("#374151")),
            key=f"audit-{i}",
        )
        for i, r in enumerate(records[-5:])  # show at most the last 5
    ]
    return Column(key="audit-records", style=Style(gap=2.0), children=entries)


# ---------------------------------------------------------------------------
# Sub-screens
# ---------------------------------------------------------------------------


def _login_screen(app: App[AuthAppState]) -> Widget:
    """Render the login prompt.

    Args:
        app: The application handle.

    Returns:
        A widget tree with username/password inputs and a login button.
    """

    def on_username(event: TextChangeEvent) -> None:
        """Update the draft username.

        Args:
            event: The text change event carrying the new value.
        """
        value: str = event.value

        def _set(s: AuthAppState) -> None:
            s.username = value
            s.error = ""

        app.set_state(_set)

    def on_password(event: TextChangeEvent) -> None:
        """Update the draft password.

        Args:
            event: The text change event carrying the new value.
        """
        value: str = event.value

        def _set(s: AuthAppState) -> None:
            s.password = value
            s.error = ""

        app.set_state(_set)

    def do_login() -> None:
        """Validate credentials and log in if correct.

        Looks the username up in the demo credential store, checks the
        password, then calls ``store.login`` with the matching JWT and a
        user-info dict.  Failures are surfaced via ``state.error``.

        Returns:
            None.
        """
        username: str = app.state.username.strip()
        password: str = app.state.password

        entry: tuple[str, str] | None = _CREDENTIALS.get(username)
        if entry is None or entry[0] != password:
            app.state.log.warning("login failed", username=username)

            def set_error(s: AuthAppState) -> None:
                s.error = "Invalid username or password."

            app.set_state(set_error)
            return

        _pw, token = entry
        claims: dict[str, Any] = decode_jwt(token)
        app.state.log.info(
            "login successful",
            username=username,
            role=str(claims.get("role", "?")),
        )
        user_info: dict[str, Any] = {
            "sub": username,
            "name": claims.get("name", username),
        }
        app.state.store.login(token, user_info)

        def on_logged_in(s: AuthAppState) -> None:
            s.error = ""
            s.username = ""
            s.password = ""
            s.current_route = "/dashboard"

        app.set_state(on_logged_in)

    error_widgets: list[Widget] = []
    if app.state.error:
        error_widgets.append(
            Text(
                content=app.state.error,
                style=Style(color=Color.from_hex("#dc2626"), font_size=13.0),
                key="login-error",
            )
        )

    return Column(
        key="login-screen",
        style=Style(
            gap=16.0,
            padding=Edge.all(24.0),
            align=AlignItems.CENTER,
        ),
        children=[
            Text(
                content="Sign in",
                style=Style(
                    font_size=26.0,
                    font_weight=FontWeight.BOLD,
                    text_align=TextAlign.CENTER,
                ),
                key="login-heading",
            ),
            Text(
                content="Demo users: alice / secret  ·  bob / p4ssw0rd",
                style=Style(font_size=12.0, color=Color.from_hex("#6b7280")),
                key="login-hint",
            ),
            Input(
                value=app.state.username,
                placeholder="Username",
                keyboard=KeyboardType.TEXT,
                on_change=on_username,
                key="username-input",
            ),
            Input(
                value=app.state.password,
                placeholder="Password",
                secure=True,
                keyboard=KeyboardType.PASSWORD,
                on_change=on_password,
                key="password-input",
            ),
            *error_widgets,
            Button(label="Sign in", on_click=do_login, key="login-btn"),
            _audit_trail(app.state.log_records),
        ],
    )


def _dashboard_screen(app: App[AuthAppState]) -> Widget:
    """Render the protected dashboard.

    Args:
        app: The application handle.

    Returns:
        A widget tree showing the user's token claims and a logout button.
    """
    token: str | None = app.state.store.token
    user: dict[str, Any] | None = app.state.store.user
    display_name: str = (
        str(user.get("name", user.get("sub", "User"))) if user else "User"
    )

    def do_logout() -> None:
        """Log out and return to the login screen.

        Returns:
            None.
        """
        uname: str = str(user.get("sub", "?")) if user else "?"
        app.state.log.info("logout", username=uname)
        app.state.store.logout()

        def on_logged_out(s: AuthAppState) -> None:
            s.current_route = "/login"

        app.set_state(on_logged_out)

    token_widget: Widget = (
        _token_badge(token)
        if token is not None
        else Text(content="No token.", key="no-token")
    )

    return Column(
        key="dashboard-screen",
        style=Style(gap=16.0, padding=Edge.all(24.0)),
        children=[
            Text(
                content=f"Welcome, {display_name}!",
                style=Style(
                    font_size=24.0,
                    font_weight=FontWeight.BOLD,
                    color=Color.from_hex("#1d4ed8"),
                ),
                key="dash-heading",
            ),
            Text(
                content=(
                    "This is a protected page. Only authenticated users can see it."
                ),
                style=Style(font_size=14.0, color=Color.from_hex("#374151")),
                key="dash-body",
            ),
            token_widget,
            Button(label="Log out", on_click=do_logout, key="logout-btn"),
            Column(
                key="audit-section",
                style=Style(gap=4.0),
                children=[
                    Text(
                        content="Audit trail",
                        style=Style(font_weight=FontWeight.BOLD, font_size=13.0),
                        key="audit-title",
                    ),
                    _audit_trail(app.state.log_records),
                ],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# view
# ---------------------------------------------------------------------------


def view(app: App[AuthAppState]) -> Widget:
    """Render the auth-gate app from the current application state.

    Uses ``route_guard`` to decide whether to show the login screen or the
    protected dashboard. The guard's decision is based on the ``AuthStore``
    held inside ``state``.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current auth + route state.
    """
    guard = route_guard(app.state.store, redirect_to="/login")
    effective_route: str = guard(app.state.current_route)

    if effective_route == "/dashboard":
        return _dashboard_screen(app)
    return _login_screen(app)
```

---

## Explaining it piece by piece

### 1. Building JWTs for the demo

The app uses two pre-built tokens — one valid (alice) and one expired (bob) — to
demonstrate `decode_jwt` and `is_jwt_expired` deterministically in tests and in
the initial render.

```python
_DEMO_NOW: float = 1_800_000_000.0  # fixed epoch, well in the past


def _b64url(obj: dict[str, Any]) -> str:
    raw: bytes = json.dumps(obj, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def make_jwt(claims: dict[str, Any]) -> str:
    header: str = _b64url({"alg": "none", "typ": "JWT"})
    payload: str = _b64url(claims)
    return f"{header}.{payload}.sig"


_ALICE_TOKEN: str = make_jwt(
    {"sub": "alice", "name": "Alice Souza", "role": "admin",
     "exp": int(_DEMO_NOW) + 3600}  # valid: 1 h after demo epoch
)

_BOB_TOKEN: str = make_jwt(
    {"sub": "bob", "name": "Bob Lima", "role": "user",
     "exp": int(_DEMO_NOW) - 3600}  # expired: 1 h before demo epoch
)
```

A compact JWT has three dot-separated parts: `header.payload.signature`.
Here the signature is the literal string `"sig"` — that is enough for `decode_jwt`
to work offline, because it **does not verify** the signature (that is a server
concern).

!!! warning "Never in production"
    Tokens without a real signature (`alg: none`) are for demos and offline tests.
    In production, use `tempest_fastapi_sdk.JWTUtils` (server side) to issue and
    verify tokens signed with HMAC or RS256. The client uses `decode_jwt` only to
    *read* claims (for display and refresh decisions), never to *trust* them as
    authorization.

The table below summarizes the two demo users:

| User | Password | Role | Expiry at `_DEMO_NOW` |
|------|----------|------|------------------------|
| alice | secret | admin | valid (+ 1 h) |
| bob | p4ssw0rd | user | expired (− 1 h) |

---

### 2. State: `AuthStore` and `Logger` living together

```python
@dataclass
class AuthAppState:
    store: AuthStore = field(default_factory=create_auth_store)
    log: Logger = field(init=False)
    username: str = ""
    password: str = ""
    error: str = ""
    log_records: list[LogRecord] = field(default_factory=list)
    current_route: str = "/dashboard"

    def __post_init__(self) -> None:
        def _append_sink(record: LogRecord) -> None:
            self.log_records.append(record)

        sink: LoggerSink = _append_sink
        self.log = create_logger(sinks=[sink], level="INFO")
```

Two special objects live in the state:

- **`store: AuthStore`** — created by `create_auth_store()`. It holds the token and
  user payload. When you call `store.login(token, user_info)` or `store.logout()`,
  the store notifies subscribers — which in a real app would automatically trigger
  a re-render.

- **`log: Logger`** — created in `__post_init__` with a sink that appends records
  to `log_records`. This closes the loop: each `log.info(...)` or
  `log.warning(...)` call updates `log_records` in state, which the `view` reads
  to render the audit trail.

!!! tip "Tip: sinks are any callable"
    `LoggerSink` is a `Protocol` with `__call__(record: LogRecord) -> None`.
    That means `list.append` is already a valid sink. In `__post_init__` we use
    a closure to access the dataclass attribute, but we could write
    `create_logger(sinks=[self.log_records.append])` after the dataclass is
    constructed if Python allowed it. The closure is the safe form.

!!! note "Why is `log` a `field(init=False)`?"
    The `Logger` needs access to `self.log_records`, which only exists after the
    dataclass is constructed. `field(init=False)` ensures `__post_init__` runs
    after all other fields are initialized.

---

### 3. `create_auth_store` and `AuthStore`

```python
store: AuthStore = field(default_factory=create_auth_store)
```

`create_auth_store()` is a convenience constructor that returns an empty
(logged-out) `AuthStore`. The `AuthStore` exposes:

| Property / Method | What it does |
|-------------------|--------------|
| `store.token` | Returns the current token or `None` |
| `store.user` | Returns the user payload or `None` |
| `store.is_authenticated` | `True` if a token is present |
| `store.login(token, user)` | Stores token + user, notifies subscribers |
| `store.logout()` | Clears token and user, notifies subscribers |
| `store.set_token(token)` | Replaces only the token (e.g. after a refresh) |
| `store.subscribe(fn)` | Registers a change listener; returns `unsubscribe` |

In the demo app, the store is consulted by `route_guard` and by `_dashboard_screen`
to display the name and the token.

---

### 4. `route_guard`: protecting routes in one line

```python
def view(app: App[AuthAppState]) -> Widget:
    guard = route_guard(app.state.store, redirect_to="/login")
    effective_route: str = guard(app.state.current_route)

    if effective_route == "/dashboard":
        return _dashboard_screen(app)
    return _login_screen(app)
```

`route_guard(store, redirect_to="/login")` returns a `guard` function. When you
call `guard("/dashboard")`:

- If `store.is_authenticated` is `True` → returns `"/dashboard"` unchanged.
- If `store.is_authenticated` is `False` → returns `"/login"` (the `redirect_to`).
- If the requested route is already `"/login"` → returns `"/login"` with no
  infinite loop.

The result (`effective_route`) is what the `view` uses to decide which sub-tree to
render. All guard logic is captured in a single call — no scattered conditionals.

!!! check "No router dependency"
    `route_guard` is a pure function — it does not depend on any navigation system.
    You can use it in isolation (as the unit tests do) or alongside the full
    tempestweb router when you need history and deep links.

---

### 5. `decode_jwt` and `is_jwt_expired`

`_token_badge` uses both helpers to inspect the token without any network call:

```python
def _token_badge(token: str) -> Widget:
    claims: dict[str, Any] = decode_jwt(token)
    expired: bool = is_jwt_expired(token, now=_DEMO_NOW)

    sub: str = str(claims.get("sub", "—"))
    role: str = str(claims.get("role", "—"))
    exp_label: str = "expired" if expired else "valid"
    exp_color: Color = (
        Color.from_hex("#dc2626") if expired else Color.from_hex("#16a34a")
    )
    ...
```

**`decode_jwt(token)`** splits the JWT at `.`, takes the middle segment (payload),
base64url-decodes it, and deserializes the JSON. It returns a `dict[str, Any]`
with the claims — `sub`, `role`, `exp`, etc. If the token is malformed, it raises
`JWTError`.

**`is_jwt_expired(token, now=_DEMO_NOW)`** calls `decode_jwt` internally, reads
the `exp` claim, and compares it with `now`. The `now` parameter is optional
(defaults to `time.time()`); this app uses `_DEMO_NOW` to make tests deterministic.

!!! info "Result with the demo tokens"
    - `is_jwt_expired(_ALICE_TOKEN, now=_DEMO_NOW)` → `False` (valid)
    - `is_jwt_expired(_BOB_TOKEN, now=_DEMO_NOW)` → `True` (expired)

    Logging in as alice shows the green badge ("valid"). This is because
    `_ALICE_TOKEN.exp = _DEMO_NOW + 3600` and `_DEMO_NOW < _DEMO_NOW + 3600`.

!!! warning "No signature verification"
    `decode_jwt` is intentionally client-side: it reads claims so the client can
    decide *when* to refresh and *what to show* in the UI. The cryptographic
    validity of the token is the server's responsibility — use
    `server_decode_jwt(token, secret)` on the FastAPI side (Mode B).

---

### 6. The Logger and the audit trail

```python
app.state.log.info(
    "login successful",
    username=username,
    role=str(claims.get("role", "?")),
)
```

The `Logger` has conventional level methods: `debug`, `info`, `warning`, `error`,
`critical`. Each accepts a message and arbitrary structured fields as `**kwargs`.
What reaches the sink is a `LogRecord`:

```python
@dataclass(frozen=True)
class LogRecord:
    level: LogLevel          # "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL"
    message: str
    fields: dict[str, Any]   # the kwargs passed at the call site
```

In the app, the sink created in `__post_init__` appends each record to
`state.log_records`. `_audit_trail` renders the last five:

```python
def _audit_trail(records: list[LogRecord]) -> Widget:
    if not records:
        return Row(
            key="audit-empty",
            children=[
                Text(
                    content="No log entries yet.",
                    style=Style(color=Color.from_hex("#6b7280"), font_size=12.0),
                    key="audit-empty-text",
                )
            ],
        )

    entries: list[Widget] = [
        Text(
            content=f"[{r.level}] {r.message}",
            style=Style(font_size=12.0, color=Color.from_hex("#374151")),
            key=f"audit-{i}",
        )
        for i, r in enumerate(records[-5:])
    ]
    return Column(key="audit-records", style=Style(gap=2.0), children=entries)
```

!!! tip "Tip: multiple sinks in parallel"
    `create_logger(sinks=[sink_a, sink_b], level="INFO")` delivers each record to
    both `sink_a` and `sink_b`. If one sink raises an exception, the rest still
    receive the record — a broken destination does not take down logging. This is
    useful for logging simultaneously to the UI (state sink) and a remote server
    (HTTP sink).

---

### 7. The login handler step by step

```python
def do_login() -> None:
    username: str = app.state.username.strip()
    password: str = app.state.password

    entry: tuple[str, str] | None = _CREDENTIALS.get(username)
    if entry is None or entry[0] != password:
        app.state.log.warning("login failed", username=username)

        def set_error(s: AuthAppState) -> None:
            s.error = "Invalid username or password."

        app.set_state(set_error)
        return

    _pw, token = entry
    claims: dict[str, Any] = decode_jwt(token)
    app.state.log.info(
        "login successful",
        username=username,
        role=str(claims.get("role", "?")),
    )
    user_info: dict[str, Any] = {
        "sub": username,
        "name": claims.get("name", username),
    }
    app.state.store.login(token, user_info)

    def on_logged_in(s: AuthAppState) -> None:
        s.error = ""
        s.username = ""
        s.password = ""
        s.current_route = "/dashboard"

    app.set_state(on_logged_in)
```

The flow in order:

1. Look up the credentials in `_CREDENTIALS`.
2. If not found or password does not match → `log.warning(...)` + `state.error`.
3. If found → `decode_jwt(token)` to read the `role`.
4. `log.info(...)` records the success with structured fields.
5. `store.login(token, user_info)` — stores the token and notifies subscribers.
6. `app.set_state(on_logged_in)` — clears the input fields and sets
   `current_route = "/dashboard"`.

On the next `view` call, `route_guard` receives `"/dashboard"` with
`store.is_authenticated == True`, so it passes through and `_dashboard_screen` is
rendered.

---

### 8. The logout handler

```python
def do_logout() -> None:
    uname: str = str(user.get("sub", "?")) if user else "?"
    app.state.log.info("logout", username=uname)
    app.state.store.logout()

    def on_logged_out(s: AuthAppState) -> None:
        s.current_route = "/login"

    app.set_state(on_logged_out)
```

`store.logout()` clears `_token` and `_user` and notifies subscribers.
Then `current_route` is set to `"/login"`. On the next `view`, `route_guard`
receives `"/login"` with `store.is_authenticated == False` — but since `"/login"`
is the `redirect_to` itself, the guard returns `"/login"` without looping — and
the login screen is rendered.

!!! info "Why not just call `store.logout()`?"
    `store.logout()` clears the internal store state. `current_route` is a
    separate field in `AuthAppState`. Updating both together in a single
    `set_state` ensures the next render is consistent: route + auth change
    atomically from the reconciler's point of view.

---

## Running the app 🚀

Save the file as `examples/auth-jwt/app.py` and pick a mode:

=== "WASM mode (Python in the browser)"

    ```bash
    tempestweb dev --mode wasm --path examples/auth-jwt
    ```

    Pyodide loads the full Python runtime in the browser. `decode_jwt`,
    `is_jwt_expired`, `AuthStore`, and `Logger` all run entirely in the tab —
    no WebSocket, no server.

=== "Server mode (FastAPI + WebSocket)"

    ```bash
    tempestweb run --mode server --path examples/auth-jwt
    ```

    A FastAPI server starts locally. The JS client sends input and click events
    and receives reconciler patches via WebSocket. The `app.py` is unchanged.

!!! check "Same code, two modes"
    The `app.py` does not reference `wasm` or `server` anywhere. No bridge is
    needed: no native capability is called on the initial mount, so
    `build(view(app))` is green with no bridge installed.

Open the browser at `http://localhost:8000`. Try these scenarios:

1. **Login with alice / secret** → dashboard with green badge ("valid").
2. **Login with bob / p4ssw0rd** → dashboard with red badge ("expired").
3. **Wrong password** → red error message, `state.error` set.
4. **Logout** → login screen, audit trail with a logout record.
5. **Direct navigation to `/dashboard` without login** → `route_guard` redirects
   to `/login`.

---

## Running the tests ✅

```bash
pytest tests/unit/test_example_auth_jwt.py -v
```

The 20 tests cover:

| Group | What it verifies |
|-------|-----------------|
| **Initial mount** | `build(view(app))` produces a valid tree; screen is login; store starts logged out |
| **Login with alice** | `is_authenticated` flips to `True`; dashboard renders; INFO log record is written; `diff` detects tree change |
| **JWT / expiry** | `_ALICE_TOKEN` not expired at `_DEMO_NOW`; `_BOB_TOKEN` expired; `decode_jwt` returns correct claims; badge appears on dashboard |
| **Login failure** | Wrong password keeps `is_authenticated = False`; `state.error` is set; screen stays login; WARNING log written |
| **Logout** | `is_authenticated` flips to `False`; token cleared; screen returns to login; INFO log written |
| **`route_guard` standalone** | Unauthenticated → `/login`; authenticated → `/dashboard`; `"/login"` is never redirected |

---

## Recap

In this example you learned:

- ✅ **`create_auth_store` / `AuthStore`** — observable store holding token and
  user; `login` / `logout` / `is_authenticated` / `subscribe`.
- ✅ **`route_guard`** — pure route guard that redirects unauthenticated requests;
  no loop on `redirect_to`.
- ✅ **`decode_jwt`** — offline payload decoding (no signature verification);
  returns `dict[str, Any]`.
- ✅ **`is_jwt_expired`** — checks the `exp` claim against a configurable `now`;
  tokens without `exp` never expire; malformed tokens are treated as expired.
- ✅ **`create_logger` / `Logger` / `LogRecord` / `LoggerSink`** — structured
  logging with a severity threshold; multiple sinks in parallel; a broken sink
  does not affect the rest.
- ✅ **State sink** — closing the loop between `Logger` and `view` using a closure
  that appends records to `state.log_records`, making the audit trail re-render
  automatically.
- ✅ **Unsigned JWTs for demos/tests** — `header.payload.sig` is enough to
  exercise `decode_jwt` and `is_jwt_expired` offline in a deterministic way.

---

## Next steps

- Read the [Login Form](./login-form.en.md) example to see three-layer validation
  with `Form` + `FormField` + `Banner`.
- Explore the [Dashboard Shell](./dashboard-shell.en.md) example to see how
  `AuthStore` integrates into a layout with a sidebar and header.
- See [Notification Center](./notification-center.en.md) to use `Logger` with a
  sink that feeds a live notification panel.
- Check the [`tempestweb.observability` reference](../observability.md) for
  the full list of `AuthStore` and `RefreshQueue` methods.
