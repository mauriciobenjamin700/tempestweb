"""Native storage capability layered over the browser's IndexedDB (N3).

The web sibling of :mod:`tempestroid.native.storage`. On the web a "file name" maps
to an IndexedDB key and its content to the stored string value;
``client/native/storage.js`` drives the key/value store built by
``client/native/idb-kv.js`` (database ``tempestweb``, object store ``kv``),
falling back to ``localStorage`` where IndexedDB is absent or refuses to open.
The same envelope reaches the browser in all three modes.

The keyspace is scoped by **owner**, which the app sets with
:func:`configure`. Two owners on the same origin — Mode B with two logins on one
device — get separate keyspaces: neither reads, overwrites nor lists the other's
keys. The owner is an app-supplied string because there is no identity the
framework could derive on its own: Mode A has no session, and Mode B's session id
identifies a *transport* and changes on every reconnect, so keying storage by it
would orphan the data on the first dropped socket.

The default owner is the empty string, and it stores keys **raw** — byte for byte
what a build without scoping wrote. Data already on disk therefore stays exactly
where it is, and an app that never calls :func:`configure` sees no change at
all.

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

from dataclasses import dataclass

from tempestweb.native.dispatch import send_native_call

__all__ = [
    "CODEC_DEFLATE",
    "CODEC_JSON",
    "StorageCodec",
    "configure",
    "delete_file",
    "get",
    "list_files",
    "list_keys",
    "put",
    "read_file",
    "remove",
    "write_file",
]


#: Values are stored as they are. The default, and the only codec every browser
#: has.
CODEC_JSON = "json"

#: Values are deflated before storage. Needs ``CompressionStream``, which shipped
#: in Safari 16.4 — below that, :func:`configure` reports ``supported=False`` and
#: the store stays on :data:`CODEC_JSON` rather than failing.
CODEC_DEFLATE = "deflate"


@dataclass(frozen=True)
class StorageCodec:
    """What :func:`configure` settled on.

    Attributes:
        requested: The codec the app asked for.
        active: The codec new writes will actually use. Differs from
            ``requested`` when the browser cannot run it.
        supported: Whether this browser can run the requested codec.
        owner: The owner every key is now scoped to; ``""`` means unscoped.
    """

    requested: str
    active: str
    supported: bool
    owner: str = ""


async def configure(*, codec: str = CODEC_JSON, owner: str = "") -> StorageCodec:
    """Choose the codec new writes use, and report what will actually run.

    **Measure before turning this on.** IndexedDB already compresses what it
    stores, so a codec here competes with the storage layer, not with raw text.
    Measured in Chrome 150: a 977 KB catalogue lands as **222 KB** on disk with
    no codec at all, and the codec takes it to **122 KB** — a real saving of 45%,
    not the 87% the compression ratio suggests. On a weak device (CPU throttled
    6x) that costs **+12 ms per read** and **+76 ms per write** at a megabyte,
    rising to **+34 ms / +295 ms** at four. The full table is in the recipe.

    So: worth it for an app holding tens of megabytes of repetitive collection,
    and not worth it for a queue of drafts. Hence off by default.

    Reads never consult this setting — a stored value carries the codec that
    wrote it, so turning the codec on does not orphan what is already stored, and
    turning it off does not orphan what was written while it was on.

    **Also scopes the keyspace**, via ``owner``. Every key written after this
    call belongs to that owner, and :func:`get`, :func:`remove` and
    :func:`list_keys` see only that owner's keys. The owner is a string the app
    supplies — typically the signed-in user's id — because nothing here could
    derive it: Mode A has no session at all, and Mode B's session id identifies a
    *transport* and changes on every reconnect, so keying storage by it would
    orphan the data on the first dropped socket.

    The default, ``""``, stores keys **raw**: byte for byte what a build without
    scoping wrote. So an app that never passes ``owner`` is unaffected, and data
    already on disk stays readable exactly where it is.

    Turning scoping on does **not** carry the existing data across — the new
    keyspace starts empty, and only the app knows whose the old data was. Adopt
    it deliberately, with the public API::

        await storage.configure()
        legacy = {k: await storage.get(k) for k in await storage.list_keys()}
        await storage.configure(owner=user_id)
        for name, content in legacy.items():
            await storage.put(name, content)

    On a device where two people already used the app, **do not** do that: the
    default keyspace holds both of their data mixed together, with no record of
    whose is whose, and adopting it would hand one user the other's. Start empty
    there.

    Both arguments are set on every call, like the codec has always been:
    ``configure()`` with no arguments resets the codec to :data:`CODEC_JSON`
    **and** the owner to ``""``. One rule for the whole function — but it means
    reconfiguring only the codec drops the owner, so pass both together.

    Args:
        codec: :data:`CODEC_JSON` (the default) or :data:`CODEC_DEFLATE`.
        owner: The keyspace owner for every later call. ``""`` (the default)
            stores keys unscoped.

    Returns:
        A :class:`StorageCodec` saying what was asked for and what will run. An
        unsupported codec is **not** an error: ``active`` falls back to
        :data:`CODEC_JSON`, because a store that cannot compress is still a
        working store while an exception here is a dead screen.

    Raises:
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call(
        "storage.configure", {"codec": codec, "owner": owner}
    )
    return StorageCodec(
        requested=str(value.get("requested", codec)),
        active=str(value.get("active", CODEC_JSON)),
        supported=bool(value.get("supported", False)),
        owner=str(value.get("owner", owner)),
    )


async def put(name: str, content: str) -> None:
    """Write a string value under a storage key, creating or overwriting it.

    Args:
        name: The storage key, within the owner configured by
            :func:`configure`.
        content: The string value to store.

    Raises:
        NativeError: If the write fails, e.g. the quota is exceeded
            (``quota_exceeded``), or another tab held an older database version
            open long enough to time the operation out (``blocked``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    await send_native_call("storage.put", {"name": name, "content": content})


async def get(name: str) -> str:
    """Read the string value stored under a key.

    Args:
        name: The storage key, within the owner configured by
            :func:`configure`.

    Returns:
        The stored string value.

    Raises:
        NativeError: If the key does not exist (``not_found``), or another tab
            held an older database version open long enough to time the operation
            out (``blocked``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call("storage.get", {"name": name})
    return str(value.get("content", ""))


async def remove(name: str) -> None:
    """Delete the value stored under a key.

    Args:
        name: The storage key, within the owner configured by
            :func:`configure`.

    Raises:
        NativeError: If the key does not exist (``not_found``), or another tab
            held an older database version open long enough to time the operation
            out (``blocked``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    await send_native_call("storage.remove", {"name": name})


async def list_keys() -> list[str]:
    """List the keys currently present in storage.

    The keys are the configured owner's, and they come back as the app wrote
    them — the owner prefix is not part of the answer, so a caller that filters
    the listing by its own prefix keeps working.

    Returns:
        The storage keys, or ``[]`` when storage is empty.

    Raises:
        NativeError: If another tab held an older database version open long
            enough to time the operation out (``blocked``).
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
