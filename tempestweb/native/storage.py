"""Native storage capability layered over the browser's IndexedDB (N3 + P2).

The web sibling of :mod:`tempestroid.native.storage`. On the web a "file name" maps
to an owner-scoped IndexedDB key and its content to the stored string value;
``client/native/storage.js`` drives the owner-scoped store from
``client/offline/store.js`` (T9 / P2), falling back to ``localStorage`` where
IndexedDB is unavailable. The same envelope reaches the browser in both modes.

Two surfaces are exposed over the one backend:

* Plan-facing key/value: :func:`put`, :func:`get`, :func:`list_keys`,
  :func:`remove`.
* tempestroid-style file aliases: :func:`write_file`, :func:`read_file`,
  :func:`delete_file`, :func:`list_files`.

Conventions match the codebase rules:

* :func:`get` / :func:`read_file` are single-resource lookups — a missing key
  raises ``NativeError("not_found")``.
* :func:`list_keys` / :func:`list_files` are collections — they return ``[]`` when
  storage is empty, never raise.
"""

from __future__ import annotations

from tempestweb.native.dispatch import send_native_call

__all__ = [
    "delete_file",
    "get",
    "list_files",
    "list_keys",
    "put",
    "read_file",
    "remove",
    "write_file",
]


async def put(name: str, content: str) -> None:
    """Write a string value under a storage key, creating or overwriting it.

    Args:
        name: The storage key (owner-scoped IndexedDB key).
        content: The string value to store.

    Raises:
        NativeError: If the write fails, e.g. the quota is exceeded
            (``quota_exceeded``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    await send_native_call("storage.put", {"name": name, "content": content})


async def get(name: str) -> str:
    """Read the string value stored under a key.

    Args:
        name: The storage key (owner-scoped IndexedDB key).

    Returns:
        The stored string value.

    Raises:
        NativeError: If the key does not exist (``not_found``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("storage.get", {"name": name})
    return str(value.get("content", ""))


async def remove(name: str) -> None:
    """Delete the value stored under a key.

    Args:
        name: The storage key (owner-scoped IndexedDB key).

    Raises:
        NativeError: If the key does not exist (``not_found``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    await send_native_call("storage.remove", {"name": name})


async def list_keys() -> list[str]:
    """List the keys currently present in storage.

    Returns:
        The storage keys, or ``[]`` when storage is empty.

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("storage.list", {})
    keys = value.get("keys", [])
    if not isinstance(keys, list):
        return []
    return [str(key) for key in keys]


#: tempestroid-style alias of :func:`put`.
write_file = put
#: tempestroid-style alias of :func:`get`.
read_file = get
#: tempestroid-style alias of :func:`remove`.
delete_file = remove
#: tempestroid-style alias of :func:`list_keys`.
list_files = list_keys
