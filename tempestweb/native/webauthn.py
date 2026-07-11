"""Native WebAuthn / passkey capability over the Credential Management Web API.

:func:`create` sends a ``webauthn.create`` ``native_call`` (registration) and
:func:`get` a ``webauthn.get`` (authentication); ``client/native/webauthn.js``
calls ``navigator.credentials.create`` / ``navigator.credentials.get`` with the
supplied options and returns the resulting credential. :func:`get_otp` uses the Web
OTP API (``navigator.credentials.get({otp: ...})``) to read a one-time code.

The WebAuthn option and credential shapes are large and browser-defined (nested
``ArrayBuffer`` fields the client base64-encodes), so they pass through as
``dict[str, Any]`` rather than being modeled as dataclasses.
"""

from __future__ import annotations

from typing import Any, cast

from tempestweb.native.dispatch import send_native_call

__all__ = ["create", "get", "get_otp"]


async def create(options: dict[str, Any]) -> dict[str, Any]:
    """Create (register) a public-key credential / passkey.

    Args:
        options: The ``PublicKeyCredentialCreationOptions`` dict, with binary
            fields base64-encoded for the wire.

    Returns:
        The created credential as a JSON-able dict.

    Raises:
        NativeError: If the API is unavailable (``unavailable``) or the ceremony is
            refused/aborted (``permission_denied``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("webauthn.create", {"options": options})
    return cast("dict[str, Any]", value.get("credential", {}))


async def get(options: dict[str, Any]) -> dict[str, Any]:
    """Get (authenticate with) a public-key credential / passkey.

    Args:
        options: The ``PublicKeyCredentialRequestOptions`` dict, with binary fields
            base64-encoded for the wire.

    Returns:
        The asserted credential as a JSON-able dict.

    Raises:
        NativeError: If the API is unavailable (``unavailable``) or the ceremony is
            refused/aborted (``permission_denied``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("webauthn.get", {"options": options})
    return cast("dict[str, Any]", value.get("credential", {}))


async def get_otp() -> str:
    """Read a one-time code delivered via the Web OTP API.

    Returns:
        The received one-time code, or ``""`` if none was delivered.

    Raises:
        NativeError: If the API is unavailable (``unavailable``) or the request is
            aborted (``permission_denied``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("webauthn.get_otp", {})
    return str(value.get("code", ""))
