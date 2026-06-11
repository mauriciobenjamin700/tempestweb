"""Dedicated tests for the auth-jwt example.

Covers:
- Initial mount: ``build(view(app))`` produces a valid Node tree (login screen,
  no bridge required).
- Login with valid credentials (alice): ``store.is_authenticated`` flips to
  ``True``, the protected dashboard renders, JWT claims are decoded, expiry is
  checked with a fixed ``now``, and a log record is written.
- Login failure (bad password): ``state.error`` is set, login screen still shows.
- Logout: ``store.is_authenticated`` clears, login screen re-renders, a logout
  log record is written.
- route_guard redirect: unauthenticated navigation to ``/dashboard`` is
  redirected to ``/login``.
- Bob's token (expired at the demo epoch): ``is_jwt_expired`` reports ``True``
  and the token badge reflects that.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from tempestweb._core import App, Node, build, diff
from tempestweb._core.widgets.events import TextChangeEvent

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load() -> ModuleType:
    """Import the auth-jwt example module.

    Returns:
        The module exposing ``make_state``, ``view``, and ``make_jwt``.
    """
    module_name = "_example_auth_jwt"
    path = EXAMPLES_DIR / "auth-jwt" / "app.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _make_app(module: ModuleType) -> App[Any]:
    """Wrap the example module in a no-op App.

    Args:
        module: The loaded example module.

    Returns:
        An :class:`App` whose ``apply_patches`` is a no-op.
    """
    return App(
        state=module.make_state(),
        view=module.view,
        apply_patches=lambda _patches: None,
    )


def _walk(node: Node) -> list[Node]:
    """Flatten an IR tree into a pre-order list.

    Args:
        node: The root node to traverse.

    Returns:
        All nodes in the subtree, root first.
    """
    out: list[Node] = [node]
    for child in node.children:
        out.extend(_walk(child))
    return out


def _types(node: Node) -> set[str]:
    """Collect every widget type tag in a tree.

    Args:
        node: The root node.

    Returns:
        The set of ``node.type`` values found across the subtree.
    """
    return {n.type for n in _walk(node)}


def _find_button(node: Node, key: str) -> Node:
    """Find a Button node by key, raising if absent.

    Args:
        node: The root node to search.
        key: The target ``node.key`` value.

    Returns:
        The matching :class:`Node`.

    Raises:
        AssertionError: If no Button with the given key exists in the tree.
    """
    hits = [n for n in _walk(node) if n.type == "Button" and n.key == key]
    assert hits, f"Button key={key!r} not found"
    return hits[0]


def _click(button_node: Node) -> None:
    """Invoke the ``on_click`` handler stored in a Button node.

    Args:
        button_node: A Button :class:`Node` whose ``props`` contain
            ``on_click``.

    Returns:
        None.
    """
    on_click = button_node.props.get("on_click")
    assert callable(on_click), "Button has no on_click"
    on_click()


def _change_input(node: Node, key: str, value: str) -> None:
    """Trigger the ``on_change`` handler of an Input widget.

    Args:
        node: The root node to search.
        key: The target Input's ``node.key``.
        value: The text value to deliver via :class:`TextChangeEvent`.

    Returns:
        None.
    """
    hits = [n for n in _walk(node) if n.type == "Input" and n.key == key]
    assert hits, f"Input key={key!r} not found"
    on_change = hits[0].props.get("on_change")
    assert callable(on_change)
    on_change(TextChangeEvent(value=value))


# ---------------------------------------------------------------------------
# Module fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def mod() -> ModuleType:
    """Load the auth-jwt example module once per test module.

    Returns:
        The loaded module.
    """
    return _load()


# ---------------------------------------------------------------------------
# Tests: initial mount (no bridge, deterministic)
# ---------------------------------------------------------------------------


def test_initial_build_is_valid_node_tree(mod: ModuleType) -> None:
    """Initial ``build(view(app))`` produces a non-empty Node tree."""
    app = _make_app(mod)
    node = build(mod.view(app))

    assert isinstance(node, Node)
    assert node.type
    assert node.children


def test_initial_screen_is_login(mod: ModuleType) -> None:
    """Before login, the login screen is rendered (contains the sign-in button)."""
    app = _make_app(mod)
    node = build(mod.view(app))
    types = _types(node)

    # Login screen must have text inputs and a Button.
    assert "Input" in types
    assert "Button" in types

    # The root Column key should be the login screen.
    assert node.key == "login-screen"


def test_initial_store_is_logged_out(mod: ModuleType) -> None:
    """The AuthStore starts logged out."""
    app = _make_app(mod)
    assert app.state.store.is_authenticated is False
    assert app.state.store.token is None


# ---------------------------------------------------------------------------
# Tests: successful login (alice)
# ---------------------------------------------------------------------------


def test_login_alice_flips_is_authenticated(mod: ModuleType) -> None:
    """Driving the login handler with alice's credentials sets is_authenticated."""
    app = _make_app(mod)
    node = build(mod.view(app))

    # Fill username and password.
    _change_input(node, "username-input", "alice")
    _change_input(node, "password-input", "secret")

    # Rebuild after typing (state has updated).
    node = build(mod.view(app))
    assert app.state.username == "alice"
    assert app.state.password == "secret"

    # Click Sign in.
    btn = _find_button(node, "login-btn")
    _click(btn)

    assert app.state.store.is_authenticated is True
    assert app.state.store.token is not None


def test_login_alice_renders_dashboard(mod: ModuleType) -> None:
    """After a successful login the dashboard screen is rendered."""
    app = _make_app(mod)
    node = build(mod.view(app))

    _change_input(node, "username-input", "alice")
    _change_input(node, "password-input", "secret")
    node = build(mod.view(app))
    _click(_find_button(node, "login-btn"))

    node_after = build(mod.view(app))
    assert node_after.key == "dashboard-screen"
    assert "logout-btn" in {n.key for n in _walk(node_after) if n.type == "Button"}


def test_login_alice_writes_log_record(mod: ModuleType) -> None:
    """A successful login writes a log record with level INFO."""
    app = _make_app(mod)
    node = build(mod.view(app))

    _change_input(node, "username-input", "alice")
    _change_input(node, "password-input", "secret")
    node = build(mod.view(app))
    _click(_find_button(node, "login-btn"))

    assert any(
        r.level == "INFO" and "login" in r.message for r in app.state.log_records
    )


def test_login_alice_tree_diff_is_non_empty(mod: ModuleType) -> None:
    """The widget tree changes between the login and dashboard renders."""
    app = _make_app(mod)
    node_before = build(mod.view(app))

    node_login = build(mod.view(app))
    _change_input(node_login, "username-input", "alice")
    _change_input(node_login, "password-input", "secret")
    node_login2 = build(mod.view(app))
    _click(_find_button(node_login2, "login-btn"))

    node_after = build(mod.view(app))

    patches = diff(node_before, node_after)
    assert patches  # the tree changed — login → dashboard


# ---------------------------------------------------------------------------
# Tests: JWT claims and expiry
# ---------------------------------------------------------------------------


def test_alice_token_is_not_expired_at_demo_now(mod: ModuleType) -> None:
    """Alice's token has exp = demo_epoch + 3600, so it is valid at the demo epoch."""
    from tempestweb.observability import is_jwt_expired

    token: str = mod._ALICE_TOKEN
    # At _DEMO_NOW the token has 3600 s left.
    assert is_jwt_expired(token, now=mod._DEMO_NOW) is False


def test_bob_token_is_expired_at_demo_now(mod: ModuleType) -> None:
    """Bob's token has exp = demo_epoch - 3600, so it is expired at the demo epoch."""
    from tempestweb.observability import is_jwt_expired

    token: str = mod._BOB_TOKEN
    # At _DEMO_NOW the token expired 3600 s ago.
    assert is_jwt_expired(token, now=mod._DEMO_NOW) is True


def test_decode_jwt_returns_alice_claims(mod: ModuleType) -> None:
    """decode_jwt returns the correct claims from alice's hand-built token."""
    from tempestweb.observability import decode_jwt

    claims = decode_jwt(mod._ALICE_TOKEN)
    assert claims["sub"] == "alice"
    assert claims["role"] == "admin"
    assert "exp" in claims


def test_dashboard_shows_token_badge_after_login(mod: ModuleType) -> None:
    """The token badge (Column key=token-badge) is present on the dashboard."""
    app = _make_app(mod)
    node = build(mod.view(app))

    _change_input(node, "username-input", "alice")
    _change_input(node, "password-input", "secret")
    node = build(mod.view(app))
    _click(_find_button(node, "login-btn"))

    node_dash = build(mod.view(app))
    keys = {n.key for n in _walk(node_dash)}
    assert "token-badge" in keys


# ---------------------------------------------------------------------------
# Tests: login failure
# ---------------------------------------------------------------------------


def test_login_bad_password_sets_error(mod: ModuleType) -> None:
    """Wrong password keeps the user logged out and sets state.error."""
    app = _make_app(mod)
    node = build(mod.view(app))

    _change_input(node, "username-input", "alice")
    _change_input(node, "password-input", "WRONG")
    node = build(mod.view(app))
    _click(_find_button(node, "login-btn"))

    assert app.state.store.is_authenticated is False
    assert app.state.error != ""


def test_login_bad_password_still_shows_login_screen(mod: ModuleType) -> None:
    """After a failed login the login screen is still rendered."""
    app = _make_app(mod)
    node = build(mod.view(app))

    _change_input(node, "username-input", "alice")
    _change_input(node, "password-input", "WRONG")
    node = build(mod.view(app))
    _click(_find_button(node, "login-btn"))

    node_after = build(mod.view(app))
    assert node_after.key == "login-screen"


def test_login_bad_password_writes_warning_log(mod: ModuleType) -> None:
    """A failed login attempt writes a WARNING log record."""
    app = _make_app(mod)
    node = build(mod.view(app))

    _change_input(node, "username-input", "alice")
    _change_input(node, "password-input", "WRONG")
    node = build(mod.view(app))
    _click(_find_button(node, "login-btn"))

    assert any(
        r.level == "WARNING" and "login" in r.message for r in app.state.log_records
    )


# ---------------------------------------------------------------------------
# Tests: logout
# ---------------------------------------------------------------------------


def test_logout_clears_is_authenticated(mod: ModuleType) -> None:
    """Clicking Log out clears store.is_authenticated."""
    app = _make_app(mod)

    # Log in first.
    node = build(mod.view(app))
    _change_input(node, "username-input", "alice")
    _change_input(node, "password-input", "secret")
    node = build(mod.view(app))
    _click(_find_button(node, "login-btn"))
    assert app.state.store.is_authenticated is True

    # Now log out.
    node_dash = build(mod.view(app))
    _click(_find_button(node_dash, "logout-btn"))

    assert app.state.store.is_authenticated is False
    assert app.state.store.token is None


def test_logout_returns_to_login_screen(mod: ModuleType) -> None:
    """After logout, route_guard redirects to the login screen."""
    app = _make_app(mod)

    node = build(mod.view(app))
    _change_input(node, "username-input", "alice")
    _change_input(node, "password-input", "secret")
    node = build(mod.view(app))
    _click(_find_button(node, "login-btn"))

    node_dash = build(mod.view(app))
    _click(_find_button(node_dash, "logout-btn"))

    node_after = build(mod.view(app))
    assert node_after.key == "login-screen"


def test_logout_writes_log_record(mod: ModuleType) -> None:
    """Logout writes an INFO log record."""
    app = _make_app(mod)

    node = build(mod.view(app))
    _change_input(node, "username-input", "alice")
    _change_input(node, "password-input", "secret")
    node = build(mod.view(app))
    _click(_find_button(node, "login-btn"))

    node_dash = build(mod.view(app))
    _click(_find_button(node_dash, "logout-btn"))

    assert any(
        r.level == "INFO" and "logout" in r.message for r in app.state.log_records
    )


# ---------------------------------------------------------------------------
# Tests: route_guard standalone
# ---------------------------------------------------------------------------


def test_route_guard_redirects_unauthenticated(mod: ModuleType) -> None:
    """An unauthenticated request to /dashboard is redirected to /login."""
    from tempestweb.observability import create_auth_store, route_guard

    store = create_auth_store()
    guard = route_guard(store, redirect_to="/login")
    assert guard("/dashboard") == "/login"


def test_route_guard_allows_authenticated(mod: ModuleType) -> None:
    """An authenticated request to /dashboard is allowed through."""
    from tempestweb.observability import create_auth_store, route_guard

    store = create_auth_store()
    store.login("tok")
    guard = route_guard(store, redirect_to="/login")
    assert guard("/dashboard") == "/dashboard"


def test_route_guard_no_loop_on_login_route(mod: ModuleType) -> None:
    """An unauthenticated request to /login is not redirected (no loop)."""
    from tempestweb.observability import create_auth_store, route_guard

    store = create_auth_store()
    guard = route_guard(store, redirect_to="/login")
    assert guard("/login") == "/login"
