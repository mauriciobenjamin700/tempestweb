# When it goes wrong

!!! abstract "How to use this page"
    Every entry starts with the **literal message** you see in the terminal or
    the console, or with the **symptom** when there is no message at all. If you
    arrived here with an error on screen, paste part of it into the site search
    (the magnifier at the top) — the right entry comes up.

    The messages on this page are checked against the source by an automated
    test, so they do not go stale in silence.

---

## An extra is missing

By far the most common category, and the easiest to fix: tempestweb installs
**lean**. Every heavy capability lives in an extra, and the message always says
which one.

| Message contains | Install |
|---|---|
| `serving Mode B needs the 'server' extra (FastAPI + uvicorn)` | `pip install "tempestweb[server]"` |
| `the dev server needs the 'server' extra` | `pip install "tempestweb[server]"` |
| `the dev watcher needs watchfiles` | `pip install "tempestweb[cli]"` |
| `tomlkit is required for` `tempestweb sync` | `pip install "tempestweb[cli]"` |
| `PyJWT is required for verify_jwt` | `pip install "tempestweb[auth]"` |
| `redis is required for RedisSessionRouter` | `pip install "tempestweb[server]"` + redis |
| `pywebpush is required to send WebPush` | `pip install "tempestweb[webpush]"` |
| `cryptography is required to generate VAPID keys` | `pip install "tempestweb[webpush]"` |
| `FastAPI is required for webpush_router` | `pip install "tempestweb[server]"` |

!!! tip "When in doubt, read the message itself"
    Every message in this family ends with the exact command. They were written
    to be the documentation — you do not have to look anything up.

---

## Native capabilities

### `no native bridge installed (off-platform, or bootstrap incomplete)`

```text
no native bridge installed (off-platform, or bootstrap incomplete)
```

An `await native.<capability>()` ran where there is no browser on the far side
of the bridge. Three causes, most frequent first:

1. **You are in a test or a script**, outside a session. There is no browser —
   inject a double, or move the call inside a handler.
2. **Mode A's bootstrap did not complete.** The generated `bootstrap.js`
   installs the bridge before calling Python's `bootstrap()`; if the page broke
   before that, the error shows up on the first interaction.
3. **The Mode B session was closed** and a handler still in flight tried to use
   the bridge.

Reference: [Native capabilities](advanced/capabilities.md).

### `the installed native bridge does not support the event channel`

```text
the installed native bridge does not support the event channel
```

You called a `watch()` / `listen()` (continuous geolocation, network, sensors)
on a bridge that only resolves one-shot calls. In Mode A this happens when
`bootstrap()` was given `dispatch` but not `subscribe`/`unsubscribe`, which
produces the more specific variant:

```text
mode A native event channel is not wired (no subscribe callable)
```

The `bootstrap.js` that `tempestweb build` generates passes all three. If you
assemble the bootstrap by hand, pass the two streaming ones too.

Reference: [Native event channel](advanced/native-events.md).

---

## Session and handlers

### The interface froze — no button responds

No error at all, the screen just stops. A session dispatches **one event at a
time**: while a handler runs, nothing else is read. A slow `await` inside the
handler — model inference, a slow external API, a large file — freezes that
user's whole connection, and not even a "Cancel" helps (the click queues up
**behind** the work it was supposed to interrupt).

Move the work out of the handler with `spawn`:

```python
from tempestweb.runtime import spawn


async def analyse(app: App[State]) -> None:
    app.set_state(lambda s: setattr(s, "status", "processing…"))

    async def work() -> None:
        result = await something_slow()
        app.set_state(lambda s: setattr(s, "result", result))

    spawn(work())
```

Reference: [Long work: dispatch is serial](tutorial/best-practices.md#long-work-dispatch-is-serial).

### `spawn() needs a running tempestweb session`

```text
spawn() needs a running tempestweb session; call it from an event handler, or await the coroutine directly
```

`spawn` hangs the task off the session in the current context, and there is no
session in the context you called from — typically a test, a script, or module
code running at import. Inside a handler there always is one. Outside, just
`await` the coroutine directly.

### The handler runs, but the screen does not change

No error. Almost always a state mutation **outside** a `set_state`:

```python
# ❌ the state changes, but nothing rebuilds the tree
async def mark(app: App[State]) -> None:
    app.state.done = True

# ✅
async def mark(app: App[State]) -> None:
    app.set_state(lambda s: setattr(s, "done", True))
```

The repaint is scheduled by `set_state`, not by the object changing.

---

## Build and Mode C

### `TranspileError` with a `file:line`

The Mode C compiler accepts a subset of typed Python, and refuses early with the
exact line. The most frequent ones:

```text
is not available in Mode C
```

`import x` works for the modules Mode C serves (`re`, `json`, `math`, `base64`,
`asyncio`) and nothing else — and a refused module's message **says what to do
instead** (`datetime` → format it in your state and pass the string).

```text
variadic parameters (*args / **kwargs) are not supported
```

```text
function decorators are not supported
```

And the one you meet most when porting an existing app:

```text
is not supported (only tempest_core, `tempestweb.components` and `tempestweb.native`)
```

Mode C sees `tempest_core`, `tempestweb.components` and `tempestweb.native`
— the last one in all three forms: `from tempestweb import native`,
`from tempestweb.native import storage` and
`from tempestweb.native.geolocation import get_position`. Plain `import
tempestweb.native` is not one of them: the message says which form to write.
Annotation-only stdlib imports (`collections.abc`, `typing`) pass too: the name
exists for the type checker and costs no JS import — but using one as a **value**
is an error (`'Any' is a type-only name`), because nothing would import it.

Outside that list, `tempestweb.presets` and `tempestweb.observability` are out of
reach: screens built from presets run in Modes A and B, not in C.

A native capability Mode C does not have in-process (`camera`) is refused
saying **which mode has it**:

```text
`camera` is not served in Mode C: the facade in `native.js` has no `camera`,
so the capability needs Mode A (Pyodide) or Mode B (server)
```

A legal name in a legal module can still be missing from the client — then the
error names the **name**, not the module:

```text
is not available in Mode C (the transpile client exports no such name)
```

Reference: [Mode C — transpile](advanced/transpile.md).

### The field with an error message is not red (Mode C)

The `Input` shows the message underneath, but its border and text stay the
normal color — in Mode A or B the same code paints both red.

A field with `error` set is **invalid**, and the core repaints its border and
text in the `error` role **while building it**. That rule lives in the built
style, not in the stylesheet, so the Mode C builder — a passthrough — dropped it
silently: the field compiled, mounted and lied.

Fixed in 0.88.0 — `Input` resolves through `resolveFieldStyle`, which applies the
core's rule (a 1px border in the `error` role, a bottom-only `SideBorder` when
`field_variant` is `flushed`, and the caller's `style` still winning last).

If you see this, update the package:

```bash
uv add "tempestweb>=0.88.0"
```

---

### The app loads with the **old** version of the code

No error, no warning: you rebuilt, you reloaded, and the fix is not there. It is
the **service worker**.

By design the worker does not call `skipWaiting` — the page owns the update, via
a prompt to the user. The consequence in development is that after a `build` the
new worker installs but sits **waiting**, and the old one keeps serving the
app-shell from its own cache. A plain F5 does not swap it: the tab stays
controlled by the old worker.

Diagnosis and fix, in Chrome DevTools → **Application** → **Service Workers**:

1. If a worker shows up labelled **waiting to activate**, that is it.
2. Tick **Update on reload** while you are developing — each reload then
   activates the new worker.
3. To clear it for good: **Unregister**, then **Application → Storage → Clear
   site data**, and reload.

In production the path is the other one: the page detects the waiting worker and
offers the update prompt, which posts `{type:"SKIP_WAITING"}`.

Reference: [PWA & offline](advanced/pwa.md).

---

## Connection (Mode B)

### `websocket disconnected` / `sse transport is closed`

```text
websocket disconnected
```

```text
sse transport is closed
```

The client went away (tab closed, network dropped, proxy cut it) and something
tried to write to the transport afterwards. As a server-side error it is
expected and needs no action. If it happens constantly in production with active
users, look at the **reverse proxy**: a short idle timeout or a missing
WebSocket upgrade tears down healthy connections.

If your infrastructure simply does not let WebSocket through, swap the shell for
SSE — see [Deploy](advanced/deploy.md#infrastructure-blocking-websocket-swap-the-shell-for-sse).

### The editor does not complete anything from `tempestweb`

mypy treats everything as `Any` and autocomplete suggests nothing. That is the
symptom of a version **before 0.64.0**, which did not ship the `py.typed`
marker — without it, PEP 561 tells the checker to ignore the types, however
thoroughly annotated the package is.

```bash
pip install --upgrade tempestweb
```

---

## Developing tempestweb itself

### `MODULE_NOT_FOUND` when running the client tests

The directory form breaks on Node 24+:

```bash
node --test tests/client/        # ❌ MODULE_NOT_FOUND
node --test "tests/client/*.test.js"   # ✅
```

Always use the glob, quoted so the shell does not expand it first.

---

## Recap

- **A missing-extra message** already contains the command — read it before
  searching here.
- **A missing native bridge** means "there is no browser on this side": a test,
  a script, or an incomplete bootstrap.
- **A frozen interface with no error** is the serial dispatch; the answer is
  `spawn`.
- **A screen that does not change** is a mutation without `set_state`.
- **Old code after a build** is the service worker waiting; turn on *Update on
  reload* while developing.
- **Not here?** Try the [FAQ](faq.md) or
  [open an issue](https://github.com/mauriciobenjamin700/tempestweb/issues).
