# PWA & offline

!!! abstract "What you'll learn"
    How to turn your app into an **installable, offline PWA** — service worker, a
    durable mutation queue, and **end-to-end WebPush** — with minimal code.

The **PWA / offline-first / WebPush** layer (Track P) makes your app
**installable** and able to run **without a network**. It is most turnkey in
**[Mode C (transpile)](transpile.md)**: because the bundle is 100% static,
`build --mode transpile` emits the whole PWA on its own. 📱

!!! success "PWA out of the box in Mode C"
    Start a PWA in one command:

    ```bash
    tempestweb new myapp --template pwa
    ```

    This scaffolds a Mode C project already configured (`mode = "transpile"` + a
    `[pwa]` block) with a counter and an **Install** button. A `tempestweb build
    --mode transpile` emits the manifest, the icons, the `sw.js` (cache-first
    service worker) and `register.js` — without you writing a line of plumbing. 🚀

## The four pieces

<div class="grid cards" markdown>

-   :material-cellphone-arrow-down: __Installable (P0)__

    ---

    Manifest + icons + install prompt. The app lands on the home screen like a
    native one.

-   :material-sync: __Service worker (P1)__

    ---

    App-shell precache → **offline after the 1st load** + update lifecycle ("new
    version, reload").

-   :material-database: __Offline-first (P2)__

    ---

    Durable IndexedDB mutation queue + replay on reconnect (Background Sync).

-   :material-bell-ring: __WebPush (P3)__

    ---

    Subscribe in the browser (`native.notifications`); send via `webpush_router`
    (VAPID) on the server.

</div>

## P0 — Installable app

The install prompt is exposed to Python through the
[`native.install`](capabilities.md) capability. The controller already suppresses
the browser's cold mini-infobar and stores the `beforeinstallprompt` event, so you
show an "Install" button at the right time:

```python
from tempestweb import native


async def maybe_show_install_button() -> bool:
    """Return whether an Install button should be shown."""
    state = await native.install.state()   # InstallState(can_install, installed)
    return state.can_install and not state.installed


async def on_install_tap() -> None:
    """Fire the native install prompt from a button handler."""
    outcome = await native.install.prompt()   # "accepted" | "dismissed" | "unavailable"
```

!!! tip "Call the prompt after a user gesture"
    Browsers only allow `install.prompt()` from a real gesture (a click). Render
    the button when `can_install` is true and fire the prompt in `on_click`.

## P1 — Service worker: offline after the 1st load

In Mode C, the generated `sw.js` **precaches the entire static bundle** —
`index.html`, the shared client, your `app.gen.js`, the icons and the manifest.
After the first load, the app opens and runs **without a network**.

!!! check "Truly offline ✅"
    With the HTTP server **turned off**, reloading the page still **renders the
    app** and navigation keeps working — verified live in Playwright. Because
    Mode C is a static, Python-free bundle, nothing depends on the server after the
    first fetch.

!!! tip "Update prompt (automatic)"
    When you ship a new version, the old service worker stays live until the tab
    closes. The shell detects the waiting worker and shows a discreet banner
    **"new version available → Update"**; on confirm, the new worker takes over and
    the page reloads once. Nothing to write in the app.

## P2 — Offline-first: durable mutation queue

Writes made offline **survive**. The [`native.offline`](transpile.md) capability
records each mutation in a durable IndexedDB queue (with an idempotency key) and
replays them in FIFO order when the connection returns — via the `online` event,
via Background Sync (tab closed) or explicitly:

```python
from tempestweb import native


async def save_note(text: str) -> None:
    """Persist a note, queueing the write if we are offline."""
    await native.offline.enqueue("POST", "/api/notes", {"text": text})


async def flush_when_online() -> None:
    """Replay any pending mutations in FIFO order."""
    await native.offline.replay()
```

Inspect the queue with `native.offline.size()` and `native.offline.pending()`.

!!! warning "Replay needs idempotency"
    When the network returns, the queue re-sends the mutations. The server
    **dedups on the idempotency key**, so a replay never applies the effect twice.
    It is the same key from the [`native.http`](capabilities.md) capability.

## P3 — End-to-end WebPush

The browser creates the subscription; the server sends. Both sides use the
**VAPID key** that proves to the browser's push service that the send is
legitimate.

### On the client — `native.notifications`

```python
from tempestweb import native


async def enable_push(vapid_public_key: str) -> None:
    """Ask for permission and subscribe the browser to WebPush."""
    state = await native.notifications.push_state()   # {supported, permission}
    if not state.supported:
        return
    await native.notifications.request_permission()
    sub = await native.notifications.subscribe(vapid_public_key)
    # Send `sub` (subscription JSON) to your backend — via native.http
    # or queued with native.offline. The framework does not decide your schema.
    await native.http.request("POST", "/webpush/subscribe", json=sub)
```

### On the server — `tempestweb vapid` + `webpush_router`

Generate the VAPID keypair once with the CLI and mount the ready-made router:

```bash
tempestweb vapid --env   # prints VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY
```

```python
from fastapi import FastAPI

from tempestweb.server import WebPushService, webpush_router

app = FastAPI()
service = WebPushService()                       # reads the VAPID_* keys from the env
app.include_router(webpush_router(service))       # /webpush/subscribe, /send, …
```

`webpush_router` already exposes the subscribe and send endpoints; `WebPushService`
stores the subscriptions and fires the signed sends via
`tempest-fastapi-sdk[webpush]` (pywebpush).

!!! danger "iOS/Safari requires an installed PWA"
    On iOS (16.4+), WebPush **only works with the PWA installed** on the home
    screen. On desktop browsers and Android it works without installing. Test on a
    real device — see [Manual verification](#manual-verification).

!!! info "The full flow has a page of its own"
    The [WebPush end-to-end (server)](examples/webpush-server.md) example walks
    through key generation, the router, the subscription and the send, step by
    step, with a sequence diagram.

## Configuring the manifest with `[pwa]`

Install metadata comes from an optional `[pwa]` section in your `tempestweb.toml`.
Every field is optional — without the section, the build uses sensible defaults
derived from the project name:

```toml
[pwa]
name = "Weather Pro"
short_name = "WPro"
theme_color = "#0a84ff"
display = "standalone"
```

The full field list is documented on the
[Mode C — transpile](transpile.md#configuring-the-manifest-with-pwa) page.

## Manual verification

!!! note "What requires a real device/browser"
    Some PWA guarantees **cannot** be fully automated; confirm by hand:

    - Install the app from the prompt and open it from the home screen.
    - Turn off the network and confirm the **2nd load** opens the app (offline).
    - Receive a WebPush notification — **on iOS, with the PWA installed**.

## Recap

- The PWA is most turnkey in **[Mode C](transpile.md)**: `build --mode transpile`
  emits the manifest, icons and service worker on its own.
- **Installable** (P0) via `native.install`; **offline after the 1st load** (P1)
  via the service worker that precaches the bundle.
- The offline runtime (P2) uses an **IndexedDB mutation queue** with an
  idempotency key (`native.offline`).
- **WebPush** (P3): `native.notifications.subscribe` on the client; `tempestweb
  vapid` + `webpush_router` on the server.
- Some PWA tests require a real device — see the manual verification.

For production health, see [Observability](observability.md). 🚀
