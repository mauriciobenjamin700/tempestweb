# Scoping storage by owner

Two people can use your app **in the same browser**. A family device, a front-desk
computer, a shared tablet at the counter — or just you, with two accounts.

When that happens, `native.storage` needs to know whose each key is. This page
shows how to tell it, what happens to data already on disk, and why the answer
cannot be automatic.

## The problem, in three lines

```python
# Alice signs in and saves a draft
await native.storage.put("draft", "my notes")

# she signs out, Bob signs in on the same browser
await native.storage.put("draft", "Bob's notes")

# Alice comes back
await native.storage.get("draft")   # "Bob's notes"
```

Without scoping, the key is just the name. Bob's `put` wrote over Alice's value,
each one's `list_keys()` returns both sets, and either one's `remove` reaches the
other's data.

!!! danger "And it is not only the keys you choose"
    The persisted [`query`](../tutorial/query.md) cache stores API responses
    through the same path. Without scoping, Bob's boot filled the `QueryCache`
    with **responses Alice had persisted** — server data, showing up on a screen
    that never asked for it. Scoping storage closes that with no code change in
    `query` at all.

## The fix: say who the owner is

```python
from tempestweb import native


async def on_sign_in(user_id: str) -> None:
    """Point storage at this user's keyspace."""
    await native.storage.configure(owner=user_id)
    await native.storage.put("draft", "my notes")
```

After that call, every `put`, `get`, `remove` and `list_keys` stays inside that
owner's keyspace. Bob cannot read, overwrite or list anything of Alice's.

`list_keys()` returns the name **as you wrote it**, with no prefix attached:

```python
await native.storage.configure(owner="alice")
await native.storage.put("draft", "a")
await native.storage.put("sent", "b")

await native.storage.list_keys()   # ["draft", "sent"]
```

!!! tip "Configure at boot, before the first call"
    The owner is state in the tab's JS module. It survives a socket reconnect in
    Mode B, but **not** a page reload — your app has to reconfigure during boot.
    A `put` issued before `configure` lands in the default keyspace with no
    warning, because the framework has no way to know you "should have"
    configured by then.

## Why you have to pass the `owner`

It would be more comfortable if the framework worked it out. It cannot:

- **Mode A** runs entirely in the browser. There is no session, no server-side
  login, nothing to derive an identity from;
- **Mode B** has a `session_id`, but that identifies a **transport**, not a
  person: it changes on every reconnect. Keying storage by it would orphan the
  data on the first dropped socket.

Your app is what knows who is signed in, after the login. That is why `owner` is
a parameter rather than magic.

## Data that is already stored

The default owner is the empty string, and it stores keys **raw** — byte for byte
what a build without scoping wrote. That is deliberate, and it has one good
consequence and one that needs care.

!!! check "The good one: nothing breaks"
    Nothing is rewritten, nothing is migrated, no database version moves. An app
    that never calls `configure(owner=...)` sees no difference at all, and data
    already on disk stays exactly where it is.

!!! warning "The one that needs care: turning scoping on starts empty"
    The old data does **not** come along. It stays readable under the default
    owner, but `owner="alice"` starts from nothing — because only your app knows
    whose that data was.

    If you want to carry the legacy data over to an owner, do it explicitly:

    ```python
    from tempestweb import native


    async def adopt_legacy(user_id: str) -> None:
        """Move data from the default keyspace into the user's."""
        await native.storage.configure()
        legacy = {
            name: await native.storage.get(name)
            for name in await native.storage.list_keys()
        }
        await native.storage.configure(owner=user_id)
        for name, content in legacy.items():
            await native.storage.put(name, content)
    ```

!!! danger "Do not adopt on a device two people already used"
    There the default keyspace holds both people's data **mixed together**, with
    no record of whose is whose — the store keeps `key → value`, and nothing
    else. Adopting would hand one person the other's data.

    Worse: wherever both wrote the same key, there is **one** value, the last
    writer's. The first one's vanished the day it was overwritten, and nothing
    here recovers it — not before this change, and not after.

    In that case, start empty.

## `configure` sets both knobs

`configure` is the same function that picks the [compression
codec](storage-codec.md), and it **always** sets both:

```python
await native.storage.configure(codec="deflate", owner="alice")

await native.storage.configure(codec="deflate")   # ⚠️ owner goes back to ""
```

One rule for the whole function, the same way the codec already behaved. The cost
is the footgun above — reconfiguring one drops the other — so **pass them
together**.

## Another tab may be updating the app

If another tab is mid-way through a database version change, a storage call can
fail with the `blocked` code:

```python
from tempestweb.native import NativeError


async def save(content: str) -> None:
    """Save, telling the user when another tab is updating the app."""
    try:
        await native.storage.put("draft", content)
    except NativeError as error:
        if error.code == "blocked":
            print("Another tab is updating the app. Try again.")
        else:
            raise
```

This is not a write failure: the database is there and healthy, and the operation
works again once the other tab closes. Before this version the call simply
**never answered**.

## Recap

- `configure(owner=...)` gives each person their own keyspace: no cross reads, no
  overwrites, no listing someone else's data.
- The owner comes from your app because neither Mode A nor Mode B has a person's
  identity to offer.
- The default (`""`) stores keys raw, so **nothing changes** for apps that do not
  use it.
- Turning scoping on starts empty on purpose; adopting the legacy data is the
  app's decision, and **not** something to do on a shared device.
- `configure()` sets codec **and** owner — pass them together.
- `blocked` means "another tab is updating", not "the write failed".
