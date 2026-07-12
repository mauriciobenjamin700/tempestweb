"""Tests for URL<->route mapping (tempestweb.runtime.routing) + navigate wiring."""

from __future__ import annotations

from tempest_core import App, Route
from tempestweb.runtime.events import apply_navigate
from tempestweb.runtime.routing import match_path, path_to_routes, route_to_path


def test_path_to_routes_builds_cumulative_stack() -> None:
    stack = path_to_routes("/shop/item")
    assert [r.name for r in stack] == ["/", "/shop", "/shop/item"]
    assert stack[-1].params == {}


def test_path_to_routes_attaches_query_to_top_route() -> None:
    stack = path_to_routes("/shop/item?ref=home&page=2")
    assert [r.name for r in stack] == ["/", "/shop", "/shop/item"]
    assert stack[-1].params == {"ref": "home", "page": "2"}


def test_path_to_routes_root_and_query_only() -> None:
    assert [r.name for r in path_to_routes("/")] == ["/"]
    top = path_to_routes("/?q=x")[-1]
    assert top.name == "/" and top.params == {"q": "x"}


def test_route_to_path_no_params_is_bare_name() -> None:
    assert route_to_path(Route(name="/settings")) == "/settings"


def test_route_to_path_encodes_params_as_query() -> None:
    path = route_to_path(Route(name="/shop", params={"ref": "home", "page": 2}))
    # dict insertion order is preserved; values coerced to str.
    assert path == "/shop?ref=home&page=2"


def test_route_to_path_url_encodes_values() -> None:
    path = route_to_path(Route(name="/search", params={"q": "a b&c"}))
    assert path == "/search?q=a+b%26c"


def test_round_trip_route_params_survive_url() -> None:
    """A route with params serializes to a URL that parses back to the same params."""
    original = Route(name="/shop/item", params={"ref": "home"})
    url = route_to_path(original)
    top = path_to_routes(url)[-1]
    assert top.name == original.name
    assert top.params == original.params


def test_match_path_extracts_params() -> None:
    assert match_path("/users/:id", "/users/42") == {"id": "42"}
    assert match_path("/users/:id/posts/:pid", "/users/7/posts/9") == {
        "id": "7",
        "pid": "9",
    }


def test_match_path_ignores_query() -> None:
    assert match_path("/users/:id", "/users/42?tab=info") == {"id": "42"}


def test_match_path_mismatch_returns_none() -> None:
    assert match_path("/users/:id", "/posts/42") is None  # literal differs
    assert match_path("/users/:id", "/users/42/extra") is None  # length differs


def test_apply_navigate_resets_stack_with_query_params() -> None:
    """The navigate event carries path+query into the nav stack's top route."""
    app: App[dict[str, object]] = App(
        state={},
        view=lambda a: None,  # type: ignore[arg-type,return-value]
        apply_patches=lambda patches: None,
    )
    apply_navigate(app, {"path": "/shop/item?ref=home"})
    assert app.nav.top.name == "/shop/item"
    assert app.nav.top.params == {"ref": "home"}
