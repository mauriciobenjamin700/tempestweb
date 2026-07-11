"""Native payment capability over the Payment Request Web API.

:func:`request` sends a ``payment.request`` ``native_call``; ``client/native/
payment.js`` constructs a ``PaymentRequest`` with the supplied methods, details, and
options, shows it, and returns the resulting payment response. The payment method,
details, and response shapes are large and browser-defined, so they pass through as
``dict[str, Any]`` rather than being modeled as dataclasses.
"""

from __future__ import annotations

from typing import Any, cast

from tempestweb.native.dispatch import send_native_call

__all__ = ["is_supported", "request"]


async def is_supported() -> bool:
    """Report whether the Payment Request API is available.

    Returns:
        ``True`` if the browser exposes ``PaymentRequest``.

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("payment.is_supported", {})
    return bool(value.get("supported", False))


async def request(
    methods: list[dict[str, Any]],
    details: dict[str, Any],
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Show a payment request and return the user's response.

    Args:
        methods: The ``PaymentMethodData`` dicts describing accepted payment
            methods.
        details: The ``PaymentDetailsInit`` dict (total, display items, …).
        options: The optional ``PaymentOptions`` dict (request shipping, payer
            name/email/phone, …).

    Returns:
        The payment response as a JSON-able dict.

    Raises:
        NativeError: If the API is unavailable (``unavailable``) or the request is
            aborted/refused (``permission_denied``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    options = options or {}
    value = await send_native_call(
        "payment.request",
        {"methods": methods, "details": details, "options": options},
    )
    return cast("dict[str, Any]", value.get("response", {}))
