"""Native cookies capability over ``document.cookie`` (Track N).

A typed Python awaitable mirror of the browser cookie jar, served by
``client/native/cookies.js`` in every mode (A via FFI, B via the ``native_call``
round-trip, C via the in-process facade). Only cookies visible to
``document.cookie`` are covered — ``HttpOnly`` cookies are, by design, invisible
to the client and must be set by the server response.

Conventions match the codebase rules: :func:`get` is a single-resource lookup that
returns ``None`` when the cookie is absent (not an error); :func:`all` is a
collection that returns ``{}`` when there are no cookies.
"""

from __future__ import annotations

from typing import Any

from tempestweb.native.dispatch import send_native_call

__all__ = ["all_cookies", "get", "remove", "set"]


async def get(name: str) -> str | None:
    """Read a single cookie by name.

    Args:
        name: The cookie name.

    Returns:
        The cookie's value, or ``None`` when no such cookie is readable.

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    result = await send_native_call("cookies.get", {"name": name})
    value = result.get("value") if isinstance(result, dict) else result
    return None if value is None else str(value)


async def set(  # noqa: A001 — mirrors the browser's cookie "set" verb
    name: str,
    value: str,
    *,
    max_age: int | None = None,
    path: str = "/",
    same_site: str = "Lax",
    secure: bool = False,
) -> None:
    """Set a cookie.

    Args:
        name: The cookie name.
        value: The cookie value (percent-encoded on the wire).
        max_age: Lifetime in seconds; ``None`` makes it a session cookie.
        path: The cookie path scope (default ``"/"``).
        same_site: The ``SameSite`` policy (``"Lax"`` / ``"Strict"`` / ``"None"``).
        secure: Whether to mark the cookie ``Secure`` (HTTPS only).

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    await send_native_call(
        "cookies.set",
        {
            "name": name,
            "value": value,
            "max_age": max_age,
            "path": path,
            "same_site": same_site,
            "secure": secure,
        },
    )


async def remove(name: str, *, path: str = "/") -> None:
    """Remove a cookie by expiring it.

    Args:
        name: The cookie name.
        path: The path scope the cookie was set with (must match to clear it).

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    await send_native_call("cookies.remove", {"name": name, "path": path})


async def all_cookies() -> dict[str, str]:
    """Read every readable cookie.

    Returns:
        A name → value map (empty when there are no readable cookies).

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value: Any = await send_native_call("cookies.all", {})
    return {str(k): str(v) for k, v in dict(value or {}).items()}
