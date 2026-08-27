"""Reading roles and permissions out of a token, **without verifying it**.

The signature is not checked here, and that is the whole design. In Mode A the
app runs in the browser, so the signing key would be in the browser too — there
is nothing to verify *with*. The server already verified the token; this reads
the payload to decide what to **draw**.

The function is named ``unverified_``… so the word appears at every call site,
where a reviewer sees it:

Example:
    >>> import base64, json
    >>> payload = base64.urlsafe_b64encode(
    ...     json.dumps({"roles": ["admin"], "exp": 4102444800}).encode()
    ... ).rstrip(b"=").decode()
    >>> access = unverified_access_from_token(f"aGVhZGVy.{payload}.bm90LWEtc2ln")
    >>> access.roles
    ('admin',)
    >>> access.is_expired(now=0)
    False

!!! danger
    A token whose signature is garbage still decodes here, on purpose — refusing
    it is not this function's job, and pretending otherwise would suggest the
    result is trustworthy. It is not: anyone can hand the browser a token
    claiming ``roles: ["admin"]``. The only thing that decision changes is which
    buttons a screen paints.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from tempestweb.observability import decode_jwt

__all__ = [
    "TokenAccess",
    "ClaimNames",
    "DEFAULT_CLAIM_NAMES",
    "unverified_access_from_token",
    "ROLES_CLAIM",
    "PERMISSIONS_CLAIM",
    "SCOPE_CLAIM",
    "EXPIRY_CLAIM",
]

#: The claim carrying role names, by convention.
ROLES_CLAIM = "roles"

#: The claim carrying explicit permissions, by convention.
PERMISSIONS_CLAIM = "permissions"

#: The OAuth 2.0 claim carrying scopes, space-separated (RFC 8693 §4.2).
SCOPE_CLAIM = "scope"

#: The registered claim carrying the expiry, as UNIX seconds (RFC 7519 §4.1.4).
EXPIRY_CLAIM = "exp"


@dataclass(frozen=True)
class TokenAccess:
    """The access-related claims read off a token, unverified.

    Attributes:
        roles: The role names the token claims, in the order the claim listed
            them.
        permissions: The permissions the token claims directly, including any
            OAuth scopes.
        expires_at: The ``exp`` claim as UNIX seconds, or ``None`` when the
            token carries none.
    """

    roles: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    expires_at: float | None = None

    def is_expired(self, *, now: float, leeway_seconds: float = 0.0) -> bool:
        """Report whether the token's expiry has passed.

        Reports rather than raises: an expired token is an ordinary state an app
        handles by refreshing, not an exceptional one.

        Args:
            now: The current UNIX time in seconds. Passed in rather than read
                from the clock so the caller owns the time source, and so a test
                pins expiry without freezing a clock.
            leeway_seconds: Treat the token as expired this many seconds early,
                to absorb clock skew.

        Returns:
            ``False`` when the token carries no ``exp`` claim — a token without
            an expiry does not expire.
        """
        if self.expires_at is None:
            return False
        return now + leeway_seconds >= self.expires_at


@dataclass(frozen=True)
class ClaimNames:
    """Which claims to read, for a server that names them differently.

    Attributes:
        roles: The claim holding role names.
        permissions: The claim holding explicit permissions.
        scope: The claim holding space-separated OAuth scopes.
    """

    roles: str = ROLES_CLAIM
    permissions: str = PERMISSIONS_CLAIM
    scope: str = SCOPE_CLAIM


#: The claim names used when the caller does not say otherwise.
DEFAULT_CLAIM_NAMES = ClaimNames()


def unverified_access_from_token(
    token: str,
    *,
    claims: ClaimNames = DEFAULT_CLAIM_NAMES,
) -> TokenAccess:
    """Read roles, permissions and expiry off a JWT **without verifying it**.

    Args:
        token: A compact-serialization JWT (``header.payload.signature``).
        claims: Which claims to read, for a server naming them differently.

    Returns:
        The :class:`TokenAccess` the payload describes. Missing claims yield
        empty tuples and ``None`` — a token carrying no roles is a valid token
        for a user with no roles, not an error.

    Raises:
        JWTError: If the token is not three dot-separated segments, or its
            payload is not a JSON object. A **wrong signature is not an error**
            here: see the module's danger note.
    """
    payload = decode_jwt(token)
    permissions = list(_strings(payload.get(claims.permissions)))
    permissions.extend(_scopes(payload.get(claims.scope)))
    return TokenAccess(
        roles=tuple(_strings(payload.get(claims.roles))),
        permissions=tuple(dict.fromkeys(permissions)),
        expires_at=_seconds(payload.get(EXPIRY_CLAIM)),
    )


def _strings(value: Any) -> Iterable[str]:  # noqa: ANN401 — a JWT claim is any JSON value
    """Read a claim that should hold a list of strings.

    A single string is one value, not a list to split: only ``scope`` is
    space-separated, and that is handled by :func:`_scopes`. Anything else —
    a number, a nested object, ``None`` — contributes nothing rather than
    raising, because a claim shaped unexpectedly should cost the user a hidden
    button, not a crashed screen.

    Args:
        value: The raw claim value.

    Returns:
        The strings it holds.
    """
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]
    return []


def _scopes(value: Any) -> Iterable[str]:  # noqa: ANN401 — a JWT claim is any JSON value
    """Read the OAuth ``scope`` claim, which is space-separated by spec.

    Args:
        value: The raw claim value.

    Returns:
        The individual scopes.
    """
    if isinstance(value, str):
        return value.split()
    return _strings(value)


def _seconds(value: Any) -> float | None:  # noqa: ANN401 — a JWT claim is any JSON value
    """Read a numeric claim such as ``exp``.

    Args:
        value: The raw claim value.

    Returns:
        The value as seconds, or ``None`` when the claim is absent or is not a
        number. ``bool`` is rejected explicitly: it is an ``int`` in Python, and
        ``exp: true`` meaning "expires at second 1" would be absurd.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None
