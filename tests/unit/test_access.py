"""Access control for the view: the wildcard rule, and the unverified decode.

Two things are pinned here that are easy to get wrong in opposite directions.

The **wildcard** must cover what it should and nothing more: ``users:*`` grants
``users:delete`` and does not grant ``audit:read``. A matcher that is too
generous hands out permissions; one that is too strict makes an app write the
prefix loop by hand, which is the thing this module exists to stop.

The **decode** must NOT reject a bad signature. That looks like a security hole
and is the opposite: this layer cannot verify anything (in Mode A the key would
be in the browser), so pretending to would make the result look trustworthy.
``test_a_forged_signature_still_decodes_on_purpose`` fixes that, and the day
somebody "fixes" it by adding verification, it fails and says why.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import pytest

from tempestweb.access import (
    NO_ACCESS,
    Access,
    AccessControl,
    ClaimNames,
    TokenAccess,
    unverified_access_from_token,
)
from tempestweb.observability import JWTError

CONTROL = AccessControl(
    roles={
        "admin": ["users:*", "audit:read"],
        "viewer": ["users:read"],
        "root": ["*"],
    }
)


def _token(payload: dict[str, Any], *, signature: str = "c2ln") -> str:
    """Build a JWT carrying ``payload``, with a signature nobody will check."""
    encoded = (
        base64.urlsafe_b64encode(json.dumps(payload).encode())
        .rstrip(b"=")
        .decode("ascii")
    )
    return f"aGVhZGVy.{encoded}.{signature}"


# --------------------------------------------------------------------------
# The wildcard rule
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("granted", "requested", "expected"),
    [
        ("users:*", "users:delete", True),
        ("users:*", "users:read", True),
        ("users:*", "users:a:b", True),
        ("users:*", "audit:read", False),
        ("users:*", "users", False),
        ("users:*", "usersx:read", False),
        ("users:read", "users:read", True),
        ("users:read", "users:delete", False),
        ("users:read", "users:*", False),
        ("*", "anything:at:all", True),
        ("*", "users:*", True),
        ("admin:users:*", "admin:users:delete", True),
        ("admin:users:*", "admin:audit:read", False),
    ],
)
def test_wildcard_covers_its_prefix_and_nothing_else(
    granted: str, requested: str, expected: bool
) -> None:
    assert Access(frozenset({granted})).can(requested) is expected


def test_the_case_the_issue_names() -> None:
    """`users:*` cobre `users:delete`, **não** cobre `audit:read`."""
    access = CONTROL.for_permissions(["users:*"])
    assert access.can("users:delete")
    assert not access.can("audit:read")


def test_an_empty_permission_is_never_granted_even_by_the_star() -> None:
    assert not Access(frozenset({"*"})).can("")


def test_can_any_and_can_all() -> None:
    access = CONTROL.for_permissions(["users:read", "audit:read"])

    assert access.can_any("users:delete", "audit:read")
    assert not access.can_any("users:delete", "billing:read")
    assert access.can_all("users:read", "audit:read")
    assert not access.can_all("users:read", "users:delete")


def test_the_empty_requirement_is_satisfied_but_the_empty_choice_is_not() -> None:
    """`can_all()` of nothing is True; `can_any()` of nothing is False.

    A screen declaring ``requires = []`` must render; a screen asking "may the
    user do any of []" must not be granted anything.
    """
    access = CONTROL.for_permissions([])
    assert access.can_all()
    assert not access.can_any()


def test_no_access_grants_nothing_and_does_not_raise() -> None:
    assert not NO_ACCESS.can("users:read")
    assert not NO_ACCESS.can_any("users:read", "*")
    assert NO_ACCESS.permissions == frozenset()


# --------------------------------------------------------------------------
# Roles → permissions
# --------------------------------------------------------------------------


def test_roles_expand_through_the_map() -> None:
    assert CONTROL.for_roles(["viewer"]).can("users:read")
    assert not CONTROL.for_roles(["viewer"]).can("users:delete")
    assert CONTROL.for_roles(["admin"]).can("users:delete")


def test_several_roles_union_their_grants() -> None:
    access = CONTROL.for_roles(["viewer", "admin"])
    assert access.can("users:delete")
    assert access.can("audit:read")


def test_a_role_the_control_does_not_know_grants_nothing_instead_of_raising() -> None:
    """A server may add a role before the app models it; that must not crash."""
    access = CONTROL.for_roles(["ghost"])

    assert not access.can("users:read")
    assert access.permissions == frozenset()
    assert "ghost" not in CONTROL.known_roles


def test_known_roles_is_there_for_a_caller_that_wants_to_notice() -> None:
    assert CONTROL.known_roles == frozenset({"admin", "viewer", "root"})


def test_a_star_role_grants_everything() -> None:
    assert CONTROL.for_roles(["root"]).can("billing:refund")


def test_a_control_with_no_roles_still_resolves_direct_permissions() -> None:
    access = AccessControl().for_permissions(["users:read"])
    assert access.can("users:read")


# --------------------------------------------------------------------------
# Token claims — decoded, never verified
# --------------------------------------------------------------------------


def test_roles_permissions_and_expiry_are_read() -> None:
    token = _token(
        {"roles": ["admin"], "permissions": ["audit:read"], "exp": 4102444800}
    )
    access = unverified_access_from_token(token)

    assert access.roles == ("admin",)
    assert access.permissions == ("audit:read",)
    assert access.expires_at == 4102444800.0


def test_a_forged_signature_still_decodes_on_purpose() -> None:
    """Refusing a bad signature is NOT this function's job.

    It cannot verify — in Mode A the key would be in the browser. Rejecting some
    tokens would suggest the ones it accepts were checked. They were not.
    """
    forged = _token({"roles": ["admin"]}, signature="bm90LWEtc2lnbmF0dXJl")
    assert unverified_access_from_token(forged).roles == ("admin",)


def test_a_malformed_token_raises_because_there_is_nothing_to_read() -> None:
    with pytest.raises(JWTError):
        unverified_access_from_token("not-a-jwt")
    with pytest.raises(JWTError):
        unverified_access_from_token("aGVhZGVy.bm90LWpzb24.c2ln")


def test_a_token_with_no_permission_claim_is_a_user_with_no_permissions() -> None:
    access = unverified_access_from_token(_token({"sub": "u1"}))

    assert access.roles == ()
    assert access.permissions == ()
    assert access.expires_at is None
    assert not CONTROL.for_token(access).can("users:read")


def test_an_expired_token_reports_instead_of_raising() -> None:
    access = unverified_access_from_token(_token({"exp": 1000}))

    assert access.is_expired(now=1001)
    assert not access.is_expired(now=999)
    assert access.is_expired(now=995, leeway_seconds=10)


def test_a_token_with_no_expiry_does_not_expire() -> None:
    assert not unverified_access_from_token(_token({})).is_expired(now=1e12)


def test_the_oauth_scope_claim_is_space_separated() -> None:
    access = unverified_access_from_token(
        _token({"scope": "users:read audit:read users:read"})
    )
    assert access.permissions == ("users:read", "audit:read")


def test_scope_and_permissions_merge_without_duplicates() -> None:
    access = unverified_access_from_token(
        _token({"permissions": ["users:read"], "scope": "users:read audit:read"})
    )
    assert access.permissions == ("users:read", "audit:read")


def test_a_single_string_claim_is_one_value_not_a_split() -> None:
    access = unverified_access_from_token(_token({"roles": "admin"}))
    assert access.roles == ("admin",)


@pytest.mark.parametrize(
    "claim", [123, {"nested": True}, None, [1, 2], ["", "ok"], True]
)
def test_a_claim_shaped_unexpectedly_costs_a_button_not_a_crash(claim: Any) -> None:
    access = unverified_access_from_token(_token({"roles": claim}))
    assert all(isinstance(role, str) and role for role in access.roles)


@pytest.mark.parametrize("value", [True, False, "soon", None, {"at": 1}])
def test_a_non_numeric_exp_is_read_as_no_expiry(value: Any) -> None:
    assert unverified_access_from_token(_token({"exp": value})).expires_at is None


def test_claim_names_can_be_overridden_for_another_server() -> None:
    token = _token({"grupos": ["admin"], "escopos": ["audit:read"]})
    access = unverified_access_from_token(
        token, claims=ClaimNames(roles="grupos", permissions="escopos")
    )

    assert access.roles == ("admin",)
    assert access.permissions == ("audit:read",)


# --------------------------------------------------------------------------
# The call an app actually makes
# --------------------------------------------------------------------------


def test_for_token_unions_expanded_roles_with_direct_permissions() -> None:
    access = CONTROL.for_token(
        TokenAccess(roles=("viewer",), permissions=("audit:read",))
    )

    assert access.can("users:read")
    assert access.can("audit:read")
    assert not access.can("users:delete")


def test_for_token_end_to_end_from_a_real_looking_jwt() -> None:
    token = _token({"roles": ["admin"], "exp": 4102444800})
    access = CONTROL.for_token(unverified_access_from_token(token))

    assert access.can("users:delete")
    assert access.can("audit:read")
    assert not access.can("billing:refund")
