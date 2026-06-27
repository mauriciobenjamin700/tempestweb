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
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

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
