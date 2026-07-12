# Routing & navigation

!!! abstract "What you'll learn"
    How a tempestweb app navigates between **screens**: the **navigation stack**
    (`NavStack`), how to define and render routes, how to navigate
    (`push`/`pop`/`replace`/`reset`), how the browser URL stays **in sync** with
    the stack (deep links + back button), how **query and path params** round-trip
    through the URL, and how to do **guards/redirects**. 🚀

Navigation in tempestweb isn't a separate router with its own tree: it's the
**same** `view(app)` producing a different tree depending on the route on top of
the stack. The reconciler diffs the result into patches — no new patch kind, no
magic. It's the `go_router` (Flutter) and React Navigation model. ✅

---

## Why a stack

A single-screen app is rare. The moment you have "Home → Details → Back", you have
a **stack**: an ordered list of routes from the root to the visible screen.
tempestweb models this with two simple values, imported from
[`tempest-core`](https://pypi.org/project/tempest-core/):

- **`Route`** — a destination: a `name` (a path-like string, e.g. `"/"`,
  `"/details"`) and an optional `params` dict.
- **`NavStack`** — the ordered stack of routes. The top (`stack.top`) is the
  visible screen; the bottom is the root.

The `App` **owns** a `NavStack` (in `app.nav`) and mutates it for you through
`push`/`pop`/`replace`/`reset`, each scheduling a rebuild. Your `view()` reads
`app.nav.top` and decides which screen to build.

---

## 1. Define routes: `view` reads `app.nav.top`

There's no declarative "route table". You **dispatch** in `view` on the name of
the route on top of the stack. This is
[`examples/router_demo/app.py`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/router_demo/app.py):

```python
from __future__ import annotations

from dataclasses import dataclass

from tempest_core import App, Button, Column, Row, Style, Text, Widget
from tempest_core.navigation import Route
from tempest_core.style import Edge


@dataclass
class RouterState:
    """The screen comes from app.nav, not from state."""


def make_state() -> RouterState:
    """Initial state."""
    return RouterState()


def view(app: App[RouterState]) -> Widget:
    """Render the screen for the route on top of the stack."""
    route = app.nav.top.name  # (1)!
    if route == "/details":
        screen = Text(content="Details screen", key="screen")
    elif route == "/about":
        screen = Text(content="About screen", key="screen")
    else:
        screen = Text(content="Home screen", key="screen")

    def go(path: str) -> None:
        app.push(Route(name=path))  # (2)!

    return Column(
        style=Style(gap=8.0, padding=Edge.all(16)),
        children=[
            Text(content=f"Route: {route}", key="route"),
            screen,
            Row(
                style=Style(gap=4.0),
                children=[
                    Button(label="Details", on_click=lambda: go("/details"), key="d"),
                    Button(label="About", on_click=lambda: go("/about"), key="a"),
                ],
            ),
        ],
    )
```

1.  `app.nav.top` is the visible `Route`; `.name` is the identifier you use to
    pick the screen.
2.  Navigating is just pushing a route onto the stack. The rebuild is scheduled
    for you.

!!! tip "`name` is a path, not an enum"
    Use path-like names (`"/"`, `"/settings"`, `"/shop/item"`). That's not just a
    convention: it's **exactly** what shows up in the browser URL (next section),
    and what a deep link resolves back into the stack.

---

## 2. Navigate: `push` · `pop` · `replace` · `reset`

The `App` exposes four operations on the stack. All schedule a rebuild:

| Method | Does | Returns |
|---|---|---|
| `app.push(route)` | Push a route on top (advance one screen). | `None` |
| `app.pop()` | Remove the top (go back one screen). No-op at root. | `bool` |
| `app.replace(route)` | Swap the top route **without** changing depth. | `None` |
| `app.reset(stack)` | Replace the whole stack (e.g. deep link, logout). | `None` |

You also read the stack:

- `app.nav.top` → the visible `Route`.
- `app.nav.stack` → the full list of routes (root → top).
- `app.nav.can_pop` → `True` when a back navigation is possible (more than one
  route on the stack).

```python
from tempest_core import App, Route, Widget


def go_to_details(app: App) -> None:
    """Advance to details."""
    app.push(Route(name="/details"))


def go_back(app: App) -> None:
    """Go back one screen — if there's somewhere to go."""
    if app.nav.can_pop:
        app.pop()


def open_login_fresh(app: App) -> None:
    """Reset the stack to the login screen (e.g. after logout)."""
    app.reset([Route(name="/login")])
```

!!! note "`pop` at the root is a safe no-op"
    With a single route on the stack, `app.pop()` returns `False` and does **not**
    empty the stack — an app always has a screen to render. Check `app.nav.can_pop`
    before showing a "back" button.

!!! tip "A ready-made back button"
    Render the back button only when `app.nav.can_pop` is true:

    ```python
    from tempest_core import Button


    def back_button(app: App) -> Button | None:
        """A back button, or None at the root."""
        if not app.nav.can_pop:
            return None
        return Button(label="← Back", on_click=app.pop, key="back")
    ```

---

## 3. The browser URL: deep links and back/forward

Here's the part that makes the app "truly web": **the URL stays in sync with the
stack**, across all three modes (WASM, server and transpile). The browser owns the
URL; the Python app owns the stack; tempestweb wires the two:

- **URL → view.** On load (a deep link / bookmark) and on every `popstate`
  (back/forward), the client reports the document **URL** (path + query). The
  runtime resolves it into a stack (`path_to_routes`) and calls `app.reset` — so
  `view` re-renders the linked screen, with its back stack already built and the
  query params on the top route's `params`.
- **view → URL.** When your app navigates imperatively (`push`/`pop`/`reset`), the
  runtime serializes the top route (`route_to_path`, including its `params` as the
  query string) and the client `history.pushState`s it — so back/forward and
  bookmarks stay correct.

```text
  URL "/shop/item?ref=home"  ──(load / popstate)──►  path_to_routes  ──►  app.reset
                                                                            │
                                                                view(app) re-renders
                                                                            │
  app.push(Route("/checkout", params={"cart":"42"}))  ──►  route_to_path
                                                            "/checkout?cart=42"  ──►  pushState
```

!!! info "The back stack is cumulative"
    A path `"/a/b"` opens the stack `["/", "/a", "/a/b"]` — **cumulative** segments.
    So landing on `/shop/item` via a deep link still lets the user go back to
    `/shop` and then `/`. The root (`"/"`) yields the single root route. The
    URL↔stack mapping lives in `tempestweb.runtime.routing` (`path_to_routes` /
    `route_to_path`) and is mirrored in the Mode C client — the behavior is
    **identical across all three modes**.

!!! check "Done when"
    You open `http://127.0.0.1:8000/about` directly and see the "About" screen;
    you click "Details" and the URL becomes `/details`; the **browser back button**
    takes you back to `/about`. All with the same `view`, no history code in the
    app.

---

## 4. Query params: `Route.params` round-trips through the URL

Pass data on the route via `params` and it **shows up in the URL as a query
string** and **survives reload/deep-link** — in all three modes.
`app.push(Route("/shop", params={"ref": "home"}))` shows `/shop?ref=home` in the
bar; on the way back (deep link or back/forward), `app.nav.top.params` brings back
`{"ref": "home"}`.

```python
from __future__ import annotations

from tempest_core import App, Column, Text, Widget


def open_shop(app: App) -> None:
    """Navigate to the shop with an origin parameter."""
    app.push(Route(name="/shop", params={"ref": "home"}))  # (1)!


def view(app: App) -> Widget:
    """Read the params off the route on top of the stack."""
    top = app.nav.top
    if top.name == "/shop":
        ref = top.params.get("ref", "direct")               # (2)!
        return Text(content=f"Shop (via: {ref})", key="shop")
    return Text(content="Home", key="home")
```

1.  This becomes the URL `/shop?ref=home` (`route_to_path` serializes `params` as
    the query string). Reloading or sharing the link reconstructs the same route.
2.  When arriving via URL, `path_to_routes` attaches the parsed query to the top
    route's `params`. You read it straight off `app.nav.top.params`.

!!! info "Query/path values are **strings**"
    A URL only carries text, so everything in `app.nav.top.params` (and what
    `match_path` extracts) arrives as a **`str`**. Richer typing is the app's job:
    convert in `view` (`int(params["page"])`, etc.).

---

## 5. Path params: `:name` with `match_path`

For identity in the **path** (e.g. `/users/42`), navigate with the value in the
`name` and extract it with `match_path` — the built-in `:name` pattern matcher:

```python
from __future__ import annotations

from tempest_core import App, Route, Text, Widget
from tempestweb.runtime.routing import match_path  # (1)!


def open_user(app: App, user_id: int) -> None:
    """Navigate to a specific user's page."""
    app.push(Route(name=f"/users/{user_id}"))       # /users/42


def view(app: App) -> Widget:
    """Dispatch by route pattern, extracting the :id."""
    params = match_path("/users/:id", app.nav.top.name)  # (2)!
    if params is not None:
        return Text(content=f"User #{params['id']}", key="user")
    return Text(content="Home", key="home")
```

1.  `match_path` lives in `tempestweb.runtime.routing`.
2.  `match_path("/users/:id", "/users/42")` → `{"id": "42"}`; a path that doesn't
    match (different segment count or a differing literal) → `None`. The query
    string, if any, is **ignored** here — combine with `app.nav.top.params` to read
    it.

!!! tip "Path params + query params together"
    They complement each other: `match_path` extracts the **path** segments
    (`:id`), and `app.nav.top.params` carries the **query string**. E.g. on
    `/users/42?tab=posts`, `match_path("/users/:id", app.nav.top.name)` gives
    `{"id": "42"}` and `app.nav.top.params` gives `{"tab": "posts"}`.

---

## 6. Guards and redirects

Need to protect a screen (e.g. require login before `/dashboard`)? tempestweb
ships a ready-made **route guard** in `tempestweb.observability`: given the auth
state, it maps the **requested** route to the route that should **actually**
render. This is the heart of
[`examples/auth-jwt/app.py`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/auth-jwt/app.py):

```python
from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Text, Widget
from tempestweb.observability import AuthStore, create_auth_store, route_guard


@dataclass
class GateState:
    """State that carries the AuthStore."""

    store: AuthStore = field(default_factory=create_auth_store)


def make_state() -> GateState:
    """Initial state."""
    return GateState()


def view(app: App[GateState]) -> Widget:
    """Render the protected screen or redirect to login."""
    guard = route_guard(app.state.store, redirect_to="/login")  # (1)!
    effective_route = guard(app.nav.top.name)                    # (2)!

    if effective_route == "/dashboard":
        return Text(content="Protected dashboard", key="dash")
    return Text(content="Please log in", key="login")
```

1.  `route_guard(store, redirect_to=...)` returns a pure
    `Callable[[str], str]`.
2.  It returns the requested route when authenticated (or when it's already the
    redirect target), otherwise `redirect_to`. You render the **effective** screen,
    not the requested one.

!!! info "A guard is a pure function in `view`, not middleware"
    `route_guard` doesn't intercept navigation or `pushState` — it only decides
    **what to render**. That keeps everything inside `view` (one tree for the
    current state) and works the same across all three modes. For custom guards
    (roles, feature flags), write your own `str -> str` function in the same shape.

!!! tip "Imperative redirect"
    If you'd rather **change the stack** than just render a different screen (so
    the URL reflects the redirect), call `app.reset` in the handler:

    ```python
    from tempest_core import App, Route


    def require_auth(app, authenticated: bool) -> None:
        """Send to login when not authenticated."""
        if not authenticated and app.nav.top.name != "/login":
            app.reset([Route(name="/login")])
    ```

---

## Recap

- Navigation is a **stack** (`app.nav`, a `NavStack` of `Route`). `view` reads
  `app.nav.top.name` and builds the screen — there's no separate route table.
- Navigate with `app.push` / `app.pop` / `app.replace` / `app.reset`; read
  `app.nav.top`, `app.nav.stack` and `app.nav.can_pop`.
- The **URL stays in sync** with the stack across all three modes: deep links and
  back/forward resolve via `path_to_routes`; imperative navigation serializes with
  `route_to_path` and `pushState`s.
- **Query params round-trip:** `Route.params` becomes the URL query string and
  **survives** reload/deep-link; read it off `app.nav.top.params`.
- **Path params** come out of the `:name` pattern with
  `match_path("/users/:id", app.nav.top.name)` → `{"id": "42"}` (or `None`).
- **Query/path values are always `str`** — richer typing is the app's job.
- **Guards/redirects** come from `route_guard` (`tempestweb.observability`): a pure
  `requested_route -> effective_route` function you apply in `view`.

Want to see it all together? The [drawer navigation example](examples/router-drawer.md)
composes `NavStack`, `Navigator`, `RouteDrawer` and `Breadcrumb` into a complete
app. 🚀
