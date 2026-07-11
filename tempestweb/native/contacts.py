"""Native contact-picker capability over the Contact Picker Web API.

:func:`select` sends a ``contacts.select`` ``native_call``; ``client/native/
contacts.js`` calls ``navigator.contacts.select`` with the requested properties and
returns the user-selected contacts. The contact shape is browser-defined (arrays of
names, emails, phone numbers), so contacts pass through as ``dict[str, Any]`` rather
than being modeled as dataclasses.
"""

from __future__ import annotations

from typing import Any, cast

from tempestweb.native.dispatch import send_native_call

__all__ = ["is_supported", "select"]


async def is_supported() -> bool:
    """Report whether the Contact Picker API is available.

    Returns:
        ``True`` if the browser exposes ``navigator.contacts``.

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("contacts.is_supported", {})
    return bool(value.get("supported", False))


async def select(
    properties: list[str] | None = None,
    multiple: bool = False,
) -> list[dict[str, Any]]:
    """Let the user pick one or more contacts through the system picker.

    Args:
        properties: The contact properties to request (defaults to
            ``["name", "email", "tel"]``).
        multiple: Whether to allow selecting more than one contact.

    Returns:
        The selected contacts as JSON-able dicts (an empty list when the user
        cancels the picker).

    Raises:
        NativeError: If the API is unavailable (``unavailable``) or the picker is
            refused (``permission_denied``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    properties = properties or ["name", "email", "tel"]
    value = await send_native_call(
        "contacts.select",
        {"properties": properties, "multiple": multiple},
    )
    return cast("list[dict[str, Any]]", value.get("contacts", []))
