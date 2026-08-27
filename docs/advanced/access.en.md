# Permissions in the view (`tempestweb.access`)

!!! tip "What you'll learn"
    How to decide **what the screen draws** from the permissions a user carries —
    without spreading `if state.role == "admin"` across the view and without
    reading the JWT with `json.loads` in some corner. 🚀

!!! danger "First of all: hiding a button is **not** access control"
    Everything on this page runs where the user can change it. A screen that does
    not draw the "Delete" button still sits in front of an endpoint that deletes,
    and reaching that endpoint takes a terminal, not an exploit.

    | Where | Decides | With |
    | --- | --- | --- |
    | **Server** (`tempest-fastapi-sdk`) | whether the request **may** happen | the signing key |
    | **Here** | whether the button **is drawn** | claims nobody verified |

    If the server does not stop it, **it is not stopped**. This is user
    experience: not showing someone an action that would answer 403.

## The problem

```python
# ❌ The condition spread across the view
if app.state.role == "admin":
    children.append(Button(label="Delete", key="del", on_click=delete))
...
if app.state.role == "admin":
    children.append(audit_panel(app))
```

The day a second privileged role exists, you have to find every `if`. And the
first time somebody wants "admin can do everything under users", a
`startswith("users:")` is born — written one way in one file and another way in
the next.

## The map, in one place

```python
from tempestweb.access import AccessControl

ACCESS = AccessControl(
    roles={
        "admin": ["users:*", "audit:read"],
        "viewer": ["users:read"],
    }
)
```

And the view asks:

```python
from tempest_core import App, Button, Column, Widget

from tempestweb.access import AccessControl

ACCESS = AccessControl(
    roles={"admin": ["users:*", "audit:read"], "viewer": ["users:read"]}
)


def view(app: App[State]) -> Widget:
    """Draw the list, with Delete only for whoever may delete."""
    access = ACCESS.for_roles(app.state.roles)
    children: list[Widget] = [user_list(app)]
    if access.can("users:delete"):
        children.append(Button(label="Delete", key="del", on_click=delete))
    return Column(key="body", children=children)
```

## The wildcard

One separator (`:`) and one wildcard **at the end**. Not a glob.

| Granted | Requested | Result |
| --- | --- | --- |
| `users:*` | `users:delete` | ✅ |
| `users:*` | `users:a:b` | ✅ |
| `users:*` | `audit:read` | ❌ different prefix |
| `users:*` | `users` | ❌ a different permission, not a shallower one |
| `users:read` | `users:*` | ❌ reading is not doing everything |
| `*` | anything | ✅ the superuser role |

Three questions, beyond `can`:

```python
access.can("users:delete")                      # one
access.can_any("users:delete", "audit:read")    # at least one
access.can_all("users:read", "audit:read")      # all of them
```

!!! note "`can_all()` with no arguments is `True`; `can_any()` is `False`"
    A screen declaring `requires = []` must render. A screen asking "may the user
    do any of []" must be granted nothing. The two answers are opposites, and
    both are right.

## Reading the token

```python
from tempestweb.access import unverified_access_from_token

claims = unverified_access_from_token(token)
claims.roles         # ('admin',)
claims.permissions   # ('audit:read',)  — OAuth scopes included
claims.is_expired(now=time.time())
```

And the step that joins the two — roles expanded **plus** direct permissions:

```python
access = ACCESS.for_token(unverified_access_from_token(token))
```

### The name says `unverified` on purpose

!!! danger "The signature is **not** verified, and that is the design"
    In Mode A the app runs in the browser: the signing key would be in the
    browser with it. There is nothing to verify *with*. The server verifies, with
    the `tempest-fastapi-sdk`, before the request reaches anything.

    A token with a forged signature **decodes normally** here — deliberately.
    Refusing some tokens would suggest the accepted ones had been checked. They
    were not: anyone can hand their own browser a token claiming
    `roles: ["admin"]`. The only thing that decision changes is which button the
    screen paints.

    The `unverified_` in the name exists so the word appears at every call site,
    where a reviewer sees it.

This is pinned by a test (`test_a_forged_signature_still_decodes_on_purpose`):
the day somebody "fixes" it by adding verification, that test fails and says why.

### An expired token reports; it does not raise

```python
if claims.is_expired(now=time.time()):
    await refresh()
```

Expiry is an ordinary state, handled by refreshing — not an exception. And a
token with **no** `exp` does not expire: `is_expired` returns `False`.

!!! info "`now` is a parameter, not a hidden clock"
    `is_expired(now=...)` takes the time rather than reading `time.time()`
    internally: the caller owns the time source, and a test pins expiry without
    freezing any clock.

### A server that names its claims differently

```python
from tempestweb.access import ClaimNames, unverified_access_from_token

claims = unverified_access_from_token(
    token, claims=ClaimNames(roles="groups", permissions="scopes")
)
```

The OAuth 2.0 `scope` claim is always read alongside, space-separated, as the
spec requires.

## When a claim arrives malformed

A claim with an unexpected shape — a number where a list belongs, a nested
object, `null` — **does not take the screen down**: it contributes nothing. The
worst case is one missing button, which a reload fixes; an exception in the view
is a blank page.

The same holds for an unknown role:

```python
ACCESS.for_roles(["role-the-server-invented-yesterday"]).can("users:read")
# False, no exception
```

The server may gain a role before the app models it, and an app that breaks on a
new role is worse than one that hides a button. Whoever wants to notice has
`ACCESS.known_roles`.

## Logged out

```python
from tempestweb.access import NO_ACCESS

access = ACCESS.for_token(claims) if app.state.token else NO_ACCESS
```

`NO_ACCESS` answers `False` to everything. A better default than `None`, which
would raise `AttributeError` in the first view that forgot to check.

## Modes A and B

!!! warning "Mode C refuses this import"
    Mode C transcribes your app's Python into JavaScript and serves a closed set
    of modules — `tempest_core`, `tempestweb.components` and
    `tempestweb.native`. A Mode C app importing `tempestweb.access` is
    **refused at build time**, with a named error:

    ```text
    app.py:5: import from 'tempestweb.access' is not supported
    (only tempest_core, `tempestweb.components` and `tempestweb.native`)
    ```

    In a Mode C app the server sends along what the screen may draw — which is
    the more honest arrangement anyway: the decision comes from whoever holds the
    key.

## Out of scope

- **Verifying a JWT signature on the client.** In Mode A the secret would be in
  the browser. The server validates.
- **Dynamic roles from an external service.** That is a feature flag, and it
  already exists in [`tempestweb.observability`](observability.md).

## Recap

- `AccessControl(roles={...})` holds the role → permission map **once**.
- `for_roles` / `for_permissions` / `for_token` resolve it; `for_token` is the
  one apps use, because it unions expanded roles with direct permissions.
- `access.can(...)`, `can_any(...)`, `can_all(...)` are what the view asks.
- `users:*` covers `users:delete`; it covers neither `audit:read` nor `users`.
- `unverified_access_from_token` does **not** verify the signature, and the name
  says so at every call site.
- None of this is authorization. The server decides; this draws.
- Mode A and Mode B. Mode C refuses the import at build time.
