"""Deciding what the view draws, from the permissions the user carries.

An app that shows "Delete user" only to admins does it with ``if`` — that part is
fine. What goes wrong is the *condition*: ``state.role == "admin"`` scattered
across the view, so adding a second privileged role means finding every one of
them, and the wildcard everybody eventually wants (``users:*`` covering
``users:delete``) gets reimplemented slightly differently in each place.

:class:`AccessControl` holds the role → permission map once. Resolving it against
what a user carries gives an :class:`Access`, and the view asks it questions.

Example:
    >>> control = AccessControl(
    ...     roles={"admin": ["users:*", "audit:read"], "viewer": ["users:read"]}
    ... )
    >>> access = control.for_roles(["viewer"])
    >>> access.can("users:read"), access.can("users:delete")
    (True, False)
    >>> control.for_roles(["admin"]).can("users:delete")
    True

!!! danger
    None of this is authorization. Hiding a button stops nobody from calling the
    endpoint behind it — the browser is the attacker's computer. The server
    decides what a request may do; this decides what a screen shows.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from tempestweb.access.claims import TokenAccess

__all__ = [
    "Access",
    "AccessControl",
    "NO_ACCESS",
    "WILDCARD",
    "WILDCARD_SUFFIX",
]

#: Grants everything. Held by a superuser role, and by nothing else.
WILDCARD = "*"

#: A grant ending in this covers every permission under the same prefix:
#: ``users:*`` covers ``users:delete`` and ``users:read``, but not ``users``
#: itself and not ``audit:read``.
WILDCARD_SUFFIX = ":*"


@dataclass(frozen=True)
class Access:
    """What one user may do, already resolved.

    Attributes:
        permissions: The permissions the user carries, wildcards included. This
            is the raw grant set, not an expansion of it — ``users:*`` stays
            ``users:*`` and is matched at question time.
    """

    permissions: frozenset[str]

    def can(self, permission: str) -> bool:
        """Report whether the user carries a permission.

        Args:
            permission: The permission to test, such as ``"users:delete"``.

        Returns:
            ``True`` when a grant covers it exactly or by wildcard. An empty
            string is never granted.
        """
        if not permission:
            return False
        return any(_grants(grant, permission) for grant in self.permissions)

    def can_any(self, *permissions: str) -> bool:
        """Report whether the user carries at least one of the permissions.

        Args:
            *permissions: The permissions to test.

        Returns:
            ``True`` when any one is granted. With no arguments, ``False`` —
            asking for nothing grants nothing.
        """
        return any(self.can(permission) for permission in permissions)

    def can_all(self, *permissions: str) -> bool:
        """Report whether the user carries every one of the permissions.

        Args:
            *permissions: The permissions to test.

        Returns:
            ``True`` when all are granted. With no arguments, ``True`` — the
            empty requirement is satisfied, which keeps
            ``can_all(*screen.requires)`` correct for a screen requiring nothing.
        """
        return all(self.can(permission) for permission in permissions)


#: Grants nothing. The right value for a logged-out view, and a safer default
#: than ``None`` — every ``can`` on it answers ``False`` instead of raising.
NO_ACCESS = Access(frozenset())


class AccessControl:
    """The role → permission map, in one place.

    Example:
        >>> control = AccessControl(roles={"editor": ["posts:*"]})
        >>> control.for_roles(["editor"]).can("posts:publish")
        True
        >>> control.for_roles(["ghost"]).can("posts:publish")
        False
    """

    def __init__(self, roles: Mapping[str, Iterable[str]] | None = None) -> None:
        """Build a control from a role map.

        Args:
            roles: Each role name mapped to the permissions it grants. Omitted
                for an app that reads permissions straight off the token and
                has no roles of its own.
        """
        self._roles: dict[str, frozenset[str]] = {
            name: frozenset(grants) for name, grants in (roles or {}).items()
        }

    @property
    def known_roles(self) -> frozenset[str]:
        """The role names this control knows about.

        Returns:
            Every key of the role map.
        """
        return frozenset(self._roles)

    def for_permissions(self, permissions: Iterable[str]) -> Access:
        """Resolve access from permissions the user carries directly.

        Args:
            permissions: The permission strings, wildcards allowed.

        Returns:
            The resolved :class:`Access`.
        """
        return Access(frozenset(permissions))

    def for_roles(self, roles: Iterable[str]) -> Access:
        """Resolve access from role names, expanding each through the map.

        A role this control does not know grants nothing, rather than raising:
        the roles come from a server that may add one before the app models it,
        and an app that crashes on a new role is worse than one that hides a
        button. :attr:`known_roles` is there for a caller that wants to notice.

        Args:
            roles: The role names the user holds.

        Returns:
            The resolved :class:`Access`, holding the union of every known
            role's grants.
        """
        granted: set[str] = set()
        for role in roles:
            granted |= self._roles.get(role, frozenset())
        return Access(frozenset(granted))

    def for_token(self, access: TokenAccess) -> Access:
        """Resolve access from a token's claims: roles expanded, plus direct.

        This is the call an app makes. A token may carry roles, explicit
        permissions, or both — the result is the union, so a user whose role
        grants ``users:read`` and who additionally carries ``audit:read`` gets
        both.

        Args:
            access: The claims read by
                :func:`~tempestweb.access.unverified_access_from_token`.

        Returns:
            The resolved :class:`Access`.
        """
        expanded = self.for_roles(access.roles).permissions
        return Access(expanded | frozenset(access.permissions))


def _grants(granted: str, requested: str) -> bool:
    """Report whether one grant covers one requested permission.

    The rule is deliberately small — one separator and one trailing wildcard,
    not a glob. ``users:*`` covers ``users:delete``; it does not cover bare
    ``users`` (which is a different permission, not a shallower one) and it does
    not cover ``audit:read``.

    Args:
        granted: The permission the user holds, possibly a wildcard.
        requested: The permission being tested.

    Returns:
        Whether the grant covers the request.
    """
    if granted == WILDCARD:
        return True
    if granted == requested:
        return True
    if granted.endswith(WILDCARD_SUFFIX):
        return requested.startswith(granted[: -len(WILDCARD)])
    return False
