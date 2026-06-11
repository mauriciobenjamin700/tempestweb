"""O4 — Client auth: token store, route guard, JWT helpers and a refresh queue.

This is the *client-side* auth surface, identical in both execution modes:

* :func:`decode_jwt` / :func:`is_jwt_expired` read a JWT's claims **without
  verifying its signature** — enough for the client to decide when to refresh and
  what to show. Signature verification is a *server* concern: in Mode B the
  server reuses ``tempest_fastapi_sdk.JWTUtils`` (see :func:`server_decode_jwt`)
  to validate tokens it issues; the client never trusts claims for authorization.
* :func:`create_auth_store` is a tiny observable store holding the current token
  and user, with ``login`` / ``logout`` / ``token`` / ``user`` and change
  subscriptions that drive re-renders.
* :func:`route_guard` builds a guard that redirects an unauthenticated request
  away from a protected route.
* :func:`create_refresh_queue` **serializes concurrent refreshes**: when many
  callers hit an expired token at once, exactly one renewal runs and every caller
  awaits that single result.

Security note: in Mode A the token lives in the browser (storage), so treat XSS
as a real risk and prefer short-lived tokens + refresh. In Mode B the token lives
in the server session and never reaches the client.

Example:
    >>> store = create_auth_store()
    >>> store.login("jwt.token.here", {"id": "u1"})
    >>> store.is_authenticated
    True
    >>> store.logout()
    >>> store.is_authenticated
    False
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import time
from collections.abc import Awaitable, Callable
from typing import Any

__all__ = [
    "JWTError",
    "decode_jwt",
    "is_jwt_expired",
    "AuthState",
    "AuthStore",
    "AuthListener",
    "create_auth_store",
    "route_guard",
    "RefreshQueue",
    "RefreshFn",
    "create_refresh_queue",
    "server_decode_jwt",
]

#: A zero-argument callback fired when the auth store changes.
AuthListener = Callable[[], None]

#: An async function that performs the actual token renewal and returns the new
#: access token. Supplied by the application (it knows the refresh endpoint).
RefreshFn = Callable[[], Awaitable[str]]


class JWTError(ValueError):
    """Raised when a JWT cannot be parsed into a claims payload."""


def _b64url_decode(segment: str) -> bytes:
    """Decode a base64url segment, restoring padding the encoder stripped.

    Args:
        segment: A base64url-encoded string without padding.

    Returns:
        The decoded raw bytes.

    Raises:
        JWTError: If the segment is not valid base64url.
    """
    padding: str = "=" * (-len(segment) % 4)
    try:
        return base64.urlsafe_b64decode(segment + padding)
    except (binascii.Error, ValueError) as exc:
        raise JWTError("invalid base64url segment in token") from exc


def decode_jwt(token: str) -> dict[str, Any]:
    """Decode a JWT's payload claims **without verifying the signature**.

    This is a client-side convenience for inspecting expiry and display claims.
    It must never be used to make an authorization decision — only the server
    (with the signing key) may trust a token's claims.

    Args:
        token: A compact-serialization JWT (``header.payload.signature``).

    Returns:
        The decoded claims as a dictionary.

    Raises:
        JWTError: If the token is malformed or its payload is not a JSON object.
    """
    parts: list[str] = token.split(".")
    if len(parts) != 3:
        raise JWTError("token must have three dot-separated segments")
    raw: bytes = _b64url_decode(parts[1])
    try:
        claims: Any = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise JWTError("token payload is not valid JSON") from exc
    if not isinstance(claims, dict):
        raise JWTError("token payload is not a JSON object")
    return claims


def is_jwt_expired(
    token: str, *, leeway_seconds: int = 0, now: float | None = None
) -> bool:
    """Return whether a JWT is expired based on its ``exp`` claim.

    A token without an ``exp`` claim is treated as **not** expiring (returns
    ``False``). A malformed token is treated as expired (returns ``True``) so the
    caller refreshes rather than trusting garbage.

    Args:
        token: The JWT to inspect.
        leeway_seconds: Seconds of clock-skew tolerance; the token is considered
            expired this many seconds *before* its real ``exp`` so a refresh is
            triggered slightly early.
        now: The current UNIX time in seconds; defaults to :func:`time.time`.

    Returns:
        ``True`` if the token is expired (or unparseable), ``False`` otherwise.
    """
    try:
        claims: dict[str, Any] = decode_jwt(token)
    except JWTError:
        return True
    exp: Any = claims.get("exp")
    if exp is None:
        return False
    current: float = time.time() if now is None else now
    try:
        return current >= float(exp) - leeway_seconds
    except (TypeError, ValueError):
        return True


class AuthState:
    """A snapshot of the current authentication state.

    Attributes:
        token: The current access token, or ``None`` when logged out.
        user: The current user payload, or ``None`` when logged out.
    """

    def __init__(self, token: str | None, user: dict[str, Any] | None) -> None:
        """Initialize the snapshot.

        Args:
            token: The current access token, or ``None``.
            user: The current user payload, or ``None``.
        """
        self.token: str | None = token
        self.user: dict[str, Any] | None = user


class AuthStore:
    """An observable store of the current token and user.

    Mutations (``login`` / ``logout`` / ``set_token``) notify subscribers, which
    is how an auth change drives a re-render (e.g. swapping a login screen for the
    app). The store holds no refresh logic itself — pair it with a
    :class:`RefreshQueue` for that.
    """

    def __init__(self) -> None:
        """Initialize an empty (logged-out) store."""
        self._token: str | None = None
        self._user: dict[str, Any] | None = None
        self._listeners: list[AuthListener] = []

    @property
    def token(self) -> str | None:
        """The current access token, or ``None`` when logged out.

        Returns:
            The token, or ``None``.
        """
        return self._token

    @property
    def user(self) -> dict[str, Any] | None:
        """The current user payload, or ``None`` when logged out.

        Returns:
            The user payload, or ``None``.
        """
        return self._user

    @property
    def is_authenticated(self) -> bool:
        """Whether a token is currently present.

        Returns:
            ``True`` if a token is set, ``False`` otherwise.
        """
        return self._token is not None

    @property
    def state(self) -> AuthState:
        """An immutable snapshot of the current state.

        Returns:
            An :class:`AuthState` capturing token and user.
        """
        return AuthState(self._token, self._user)

    def login(self, token: str, user: dict[str, Any] | None = None) -> None:
        """Set the token (and optional user) and notify subscribers.

        Args:
            token: The access token to store.
            user: The user payload to store, if known.

        Returns:
            None.
        """
        self._token = token
        self._user = dict(user) if user is not None else None
        self._notify()

    def set_token(self, token: str) -> None:
        """Replace the access token (e.g. after a refresh) and notify.

        Args:
            token: The new access token.

        Returns:
            None.
        """
        self._token = token
        self._notify()

    def logout(self) -> None:
        """Clear the token and user and notify subscribers.

        Returns:
            None.
        """
        self._token = None
        self._user = None
        self._notify()

    def subscribe(self, listener: AuthListener) -> Callable[[], None]:
        """Register a listener fired on every auth change.

        Args:
            listener: A zero-argument callback invoked on change.

        Returns:
            An unsubscribe callable.
        """
        self._listeners.append(listener)

        def unsubscribe() -> None:
            """Remove the listener if still registered."""
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def _notify(self) -> None:
        """Notify every subscriber of a state change.

        Returns:
            None.
        """
        for listener in list(self._listeners):
            listener()


def create_auth_store() -> AuthStore:
    """Create a fresh, logged-out :class:`AuthStore`.

    Returns:
        A new :class:`AuthStore`.
    """
    return AuthStore()


def route_guard(
    store: AuthStore, *, redirect_to: str = "/login"
) -> Callable[[str], str]:
    """Build a route guard that redirects unauthenticated navigation.

    Args:
        store: The auth store consulted for the current session.
        redirect_to: The route an unauthenticated request is sent to.

    Returns:
        A function mapping a requested route name to the route that should
        actually render: the request unchanged when authenticated (or when it is
        already the redirect target), otherwise ``redirect_to``.
    """

    def guard(requested: str) -> str:
        """Resolve the effective route for a navigation request.

        Args:
            requested: The route the app is trying to navigate to.

        Returns:
            ``requested`` when allowed, otherwise ``redirect_to``.
        """
        if store.is_authenticated or requested == redirect_to:
            return requested
        return redirect_to

    return guard


class RefreshQueue:
    """Serializes concurrent token refreshes into a single in-flight renewal.

    When a token expires, many requests can discover it at once and each try to
    refresh. Without coordination that fires N parallel renewals, races the
    store, and can invalidate each other's refresh tokens. This queue ensures
    **exactly one** refresh runs: the first caller starts it, every concurrent
    caller awaits the same result, and the new token is pushed into the store
    once. After it settles the queue resets so a later expiry refreshes again.
    """

    def __init__(self, store: AuthStore, refresh_fn: RefreshFn) -> None:
        """Initialize the queue.

        Args:
            store: The auth store whose token is updated after a refresh.
            refresh_fn: An async function performing the renewal and returning
                the new access token.
        """
        self._store: AuthStore = store
        self._refresh_fn: RefreshFn = refresh_fn
        self._pending: asyncio.Future[str] | None = None
        self._calls: int = 0

    @property
    def refresh_calls(self) -> int:
        """The number of times the underlying ``refresh_fn`` was actually run.

        Useful in tests to assert that concurrent callers collapsed into a single
        renewal.

        Returns:
            The count of real refresh invocations.
        """
        return self._calls

    async def refresh(self) -> str:
        """Return a fresh token, coalescing concurrent callers into one renewal.

        The first caller schedules the real renewal as a single
        :class:`asyncio.Task` and stores it; every concurrent caller awaits that
        same task instead of starting its own. The task resolves once for all
        waiters, then the in-flight slot is cleared so a future expiry triggers a
        new renewal. If the renewal raises, the exception propagates to every
        waiter and the slot is cleared so a retry is possible.

        Returns:
            The new access token.

        Raises:
            Exception: Whatever ``refresh_fn`` raises, propagated to all waiters.
        """
        if self._pending is not None:
            return await self._pending

        task: asyncio.Task[str] = asyncio.ensure_future(self._run())
        self._pending = task
        try:
            return await task
        finally:
            self._pending = None

    async def _run(self) -> str:
        """Run the real refresh once and push the new token into the store.

        Returns:
            The new access token.
        """
        self._calls += 1
        token: str = await self._refresh_fn()
        self._store.set_token(token)
        return token


def create_refresh_queue(store: AuthStore, refresh_fn: RefreshFn) -> RefreshQueue:
    """Create a :class:`RefreshQueue` bound to a store and refresh function.

    Args:
        store: The auth store updated after a successful refresh.
        refresh_fn: The async renewal function returning a new access token.

    Returns:
        A configured :class:`RefreshQueue`.
    """
    return RefreshQueue(store, refresh_fn)


def server_decode_jwt(token: str, secret: str, **kwargs: Any) -> dict[str, Any]:  # noqa: ANN401 - forwarded verbatim to JWTUtils.decode
    """Verify and decode a JWT on the server via ``tempest_fastapi_sdk.JWTUtils``.

    Mode B issues and validates its own tokens. Rather than re-implement
    signature verification, the server reuses the SDK's ``JWTUtils`` so token
    handling stays consistent with the rest of the user's backend stack.

    Args:
        token: The JWT to verify and decode.
        secret: The signing secret used to verify the signature.
        **kwargs: Extra keyword arguments forwarded to ``JWTUtils.decode`` (e.g.
            ``algorithms``), depending on the installed SDK version.

    Returns:
        The verified claims dictionary.

    Raises:
        RuntimeError: If ``tempest_fastapi_sdk`` is not installed. It is an
            optional, server-only dependency — install the ``[auth]`` extra.
    """
    try:
        from tempest_fastapi_sdk import JWTUtils  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "server_decode_jwt requires tempest-fastapi-sdk; install the "
            "[auth] extra to verify tokens on the server."
        ) from exc
    result: Any = JWTUtils.decode(token, secret, **kwargs)
    return dict(result)
