"""Native storage capability over the browser's Web Storage API (localStorage).

The web sibling of :mod:`tempestroid.native.storage`. The names mirror
tempestroid (:func:`read_file` / :func:`write_file` / :func:`delete_file` /
:func:`list_files`) so application code is identical across platforms — on the
web a "file name" maps to a ``localStorage`` key and its content to the stored
string value. ``client/native.js`` drives ``window.localStorage``.

Conventions match the codebase rules:

* :func:`read_file` is a single-resource lookup — a missing key raises
  ``NativeError("not_found")``.
* :func:`list_files` is a collection — it returns ``[]`` when storage is empty,
  never raises.
"""

from __future__ import annotations

from tempestweb.native.dispatch import send_native_request

__all__ = ["delete_file", "list_files", "read_file", "write_file"]


async def write_file(name: str, content: str) -> None:
    """Write a string value under a storage key, creating or overwriting it.

    Args:
        name: The storage key (``localStorage`` key).
        content: The string value to store.

    Raises:
        NativeError: If the write fails, e.g. the quota is exceeded
            (``quota_exceeded``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    await send_native_request("storage", "write", {"name": name, "content": content})


async def read_file(name: str) -> str:
    """Read the string value stored under a key.

    Args:
        name: The storage key (``localStorage`` key).

    Returns:
        The stored string value.

    Raises:
        NativeError: If the key does not exist (``not_found``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    data = await send_native_request("storage", "read", {"name": name})
    return str(data.get("content", ""))


async def delete_file(name: str) -> None:
    """Delete the value stored under a key.

    Args:
        name: The storage key (``localStorage`` key).

    Raises:
        NativeError: If the key does not exist (``not_found``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    await send_native_request("storage", "delete", {"name": name})


async def list_files() -> list[str]:
    """List the keys currently present in storage.

    Returns:
        The storage keys, or ``[]`` when storage is empty.

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    data = await send_native_request("storage", "list", {})
    files = data.get("files", [])
    if not isinstance(files, list):
        return []
    return [str(name) for name in files]
