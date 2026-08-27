"""Deciding what the **view** draws, from the permissions a user carries.

The `tempest-fastapi-sdk` validates the token and the server decides what a
request may do. On the **screen** side there was nothing: an app that shows
"Delete user" only to admins spread `if state.role == "admin"` across the view,
and read the permission list out of the JWT with `json.loads` in some corner.

Two pieces close that, and neither of them is authorization:

* :func:`unverified_access_from_token` reads roles, permissions and expiry off a
  JWT **without checking the signature** — there is nothing to check it with in
  the browser, and the server already did.
* :class:`AccessControl` holds the role → permission map once, and resolving it
  gives an :class:`Access` the view asks questions of.

Example:
    ```python
    from tempestweb.access import AccessControl

    ACCESS = AccessControl(
        roles={
            "admin": ["users:*", "audit:read"],
            "viewer": ["users:read"],
        }
    )

    access = ACCESS.for_roles(["viewer"])
    access.can("users:read")  # True
    access.can("users:delete")  # False — "users:read" is not "users:*"
    ```

The view then asks the question where it draws:
`if access.can("users:delete"): children.append(Button(...))`. A full screen is
in the recipe.

!!! danger "Hiding a button is not access control"
    Everything here runs where the user can change it. A screen that draws no
    Delete button still sits in front of an endpoint that deletes, and reaching
    that endpoint takes a terminal, not an exploit. The pair is:

    | Where | Decides | With |
    | --- | --- | --- |
    | Server (`tempest-fastapi-sdk`) | whether the request **may** happen | the key |
    | Here | whether the button **is drawn** | unverified claims |

    If the server does not enforce it, it is not enforced.

!!! warning "Modes A and B only"
    Mode C transpiles the app's own Python into JavaScript and serves a fixed set
    of modules — ``tempest_core``, ``tempestweb.components`` and
    ``tempestweb.native``. Importing this package from a Mode C app is refused at
    build time with a named error.

Import everything from this package level rather than from submodules.
"""

from __future__ import annotations

from tempestweb.access.claims import (
    DEFAULT_CLAIM_NAMES,
    EXPIRY_CLAIM,
    PERMISSIONS_CLAIM,
    ROLES_CLAIM,
    SCOPE_CLAIM,
    ClaimNames,
    TokenAccess,
    unverified_access_from_token,
)
from tempestweb.access.control import (
    NO_ACCESS,
    WILDCARD,
    WILDCARD_SUFFIX,
    Access,
    AccessControl,
)

__all__ = [
    "Access",
    "AccessControl",
    "NO_ACCESS",
    "WILDCARD",
    "WILDCARD_SUFFIX",
    "TokenAccess",
    "ClaimNames",
    "DEFAULT_CLAIM_NAMES",
    "unverified_access_from_token",
    "ROLES_CLAIM",
    "PERMISSIONS_CLAIM",
    "SCOPE_CLAIM",
    "EXPIRY_CLAIM",
]
