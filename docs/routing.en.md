# Routing & navigation

!!! abstract "What you'll learn"
    How a tempestweb app navigates between **screens**: the **navigation stack**
    (`NavStack`), how to define and render routes, how to navigate
    (`push`/`pop`/`replace`/`reset`), how the browser URL stays **in sync** with
    the stack (deep links + back button), and how to do **guards/redirects**. 🚀

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
  (back/forward), the client reports the document **path**. The runtime resolves
  the path into a stack (`routes_from_path`) and calls `app.reset` — so `view`
  re-renders the linked screen, with its back stack already built.
- **view → URL.** When your app navigates imperatively (`push`/`pop`/`reset`), the
  runtime emits the new path and the client `history.pushState`s it — so
  back/forward and bookmarks stay correct.

```text
  URL "/shop/item"  ──(load / popstate)──►  routes_from_path  ──►  app.reset
                                                                      │
                                                          view(app) re-renders
                                                                      │
  app.push(Route(name="/checkout"))  ──►  runtime emits "/checkout"  ──►  pushState
```

!!! info "`routes_from_path` builds the back stack"
    A path `"/a/b"` opens the stack `["/", "/a", "/a/b"]` — **cumulative** segments.
    So landing on `/shop/item` via a deep link still lets the user go back to
    `/shop` and then `/`. The root (`"/"`) yields the single root route.

!!! check "Done when"
    You open `http://127.0.0.1:8000/about` directly and see the "About" screen;
    you click "Details" and the URL becomes `/details`; the **browser back button**
    takes you back to `/about`. All with the same `view`, no history code in the
    app.

---

## 4. Path params: identity encoded in the name

tempestweb has **no** route patterns with placeholders (no `/users/:id` with
automatic extraction). Identity goes **in the route name itself** — that's how the
core models it, and it's what survives in the URL. You navigate with the full path
and parse the segment in `view`:

```python
from __future__ import annotations

from tempest_core import App, Route, Text, Widget


def open_user(app: App, user_id: int) -> None:
    """Navigate to a specific user's page."""
    app.push(Route(name=f"/users/{user_id}"))  # (1)!


def user_screen(route_name: str) -> Widget:
    """Extract the id from the route name and render."""
    user_id = route_name.removeprefix("/users/")  # (2)!
    return Text(content=f"User #{user_id}", key="user")


def view(app: App) -> Widget:
    """Dispatch by route prefix."""
    name = app.nav.top.name
    if name.startswith("/users/"):
        return user_screen(name)
    return Text(content="Home", key="home")
```

1.  The id becomes part of the path — and therefore of the URL (`/users/42`) and
    the deep link.
2.  No magic placeholder: you slice the name string. A `startswith`/`removeprefix`
    covers the common case.

!!! warning "`Route.params` does NOT go into the URL"
    You **can** pass data on the route via `Route(name="/users", params={"id": 42})`
    and read it in `app.nav.top.params["id"]`. But those `params` live **in memory
    only**: the runtime serializes only the route **`name`** into browser history
    (the URL). On reload or a deep link, `params` comes back **empty**. So for
    identity that must survive a reload, **encode it in the `name`** (as above) —
    not in `params`.

---

## 5. Query params

!!! danger "Gap: query params don't reach Python"
    tempestweb does **not** surface query params (`?q=...&page=2`) to the app
    today. The URL→navigation bridge reports only `location.pathname` — the query
    string (`location.search`) is dropped before it reaches Python. There is no
    typed query-param API; **don't invent one**.

The workaround is the same as for path params: if a value must be in the URL and
survive a reload, **put it in the path** (the route `name`) and parse it yourself.
For state that does **not** need to be in the URL (an ephemeral filter, a selected
tab), keep it in your normal `State` — not in the route.

```python
from tempest_core import App, Route


def search(app: App, term: str, page: int) -> None:
    """Put the search in the path so it survives a reload."""
    app.push(Route(name=f"/search/{term}/{page}"))
    # later, in view: name.removeprefix("/search/").split("/") → [term, page]
```

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
  back/forward resolve via `routes_from_path`; imperative navigation `pushState`s.
- **Path params** go in the route `name` (you parse it). `Route.params` is
  in-memory only — it does **not** survive a reload/URL.
- **Query params are not surfaced** today (known gap); encode them in the path or
  keep them in `State`.
- **Guards/redirects** come from `route_guard` (`tempestweb.observability`): a pure
  `requested_route -> effective_route` function you apply in `view`.

Want to see it all together? The [drawer navigation example](examples/router-drawer.md)
composes `NavStack`, `Navigator`, `RouteDrawer` and `Breadcrumb` into a complete
app. 🚀
