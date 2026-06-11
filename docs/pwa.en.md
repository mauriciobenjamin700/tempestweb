# PWA & offline

The **PWA / offline-first / WebPush** layer (Track P) makes your app
**installable** and able to run **without a network**. It is shared by both modes
— you write the PWA shell once. 📱

!!! info "Under construction (Track P)"
    This layer is the roadmap's **Track P**. Phases P0–P5 are detailed in the
    [design plan](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/plan.md).
    This page describes the **planned surface** and the main flows.

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

    IndexedDB store + event queue/replay on reconnect (Background Sync).

-   :material-bell-ring: __WebPush (P3)__

    ---

    Subscribe in the browser; send via `tempest-fastapi-sdk[webpush]` (VAPID).

</div>

## P0 — Installable app

The first step is the **manifest** and capturing the install prompt. The client
stores the `beforeinstallprompt` event and your UI decides when to offer
"Install".

```python
from tempestweb.pwa import install


def view(app: object) -> object:
    """Show an Install button only when installation is available."""
    if install.can_prompt():
        return install_button(on_click=install.prompt)
    return already_installed_banner()
```

!!! tip "Mode A also benefits from the PWA"
    In Mode A, the service worker precache (P1) solves the **WASM bundle
    cold-start** — the second load opens instantly and offline.

## P1 — Service worker: offline after the 1st load

The service worker **precaches the app-shell** (hashed assets) and manages the
update cycle. When a new version is published, the UI shows "new version, reload";
on confirmation, `skipWaiting` activates the new version.

```python
from tempestweb.pwa import service_worker


async def setup_sw(app: object) -> None:
    """Register the service worker and wire the update lifecycle.

    Args:
        app: The running app handle.
    """
    await service_worker.register(
        url="/sw.js",
        on_update=lambda: app.set_state(lambda s: setattr(s, "update_ready", True)),
        on_error=lambda err: app.log.error("SW failed", error=err),
    )


async def apply_update() -> None:
    """Activate the waiting service worker and reload."""
    await service_worker.skip_waiting()
```

!!! check "Done when"
    The **second offline load** opens the app. Publishing a new version triggers
    the "reload" banner — and on confirmation, the app is already on the new
    version.

## P2 — Offline-first at runtime

The **IndexedDB** store (owner-scoped per domain) keeps data and state offline.
Mutations made offline enter a **durable queue** with an idempotency key (from
`native.http`) and **replay themselves** when the network returns (Background
Sync).

```python
from tempestweb.native import storage


async def save_draft(text: str) -> None:
    """Persist a draft to IndexedDB, surviving offline.

    Args:
        text: The draft body to store.
    """
    await storage.put("drafts", {"id": "current", "text": text})


async def list_drafts() -> list[dict[str, object]]:
    """List stored drafts, newest first.

    Returns:
        The drafts ordered by creation time, most recent first.
    """
    return await storage.list("drafts", order_by="created_at", reverse=True)
```

The per-mode divergence is only **behavior**, not API:

| | Mode A | Mode B |
|---|---|---|
| Offline data | Lives in the browser; offline is **full** | Last cached state (read-only) |
| Offline mutations | Applied locally | **Queued**; the server reconciles on reconnect |
| Online/offline banner | Tied to network status | Tied to WS/SSE connection status |

!!! warning "Replay needs idempotency"
    When the network returns, the queue re-sends the mutations. Without the
    `idempotency_key` from [`native.http`](capabilities.md), a replay could
    duplicate effects. That is why the offline queue depends on the HTTP
    capability.

## P3 — WebPush

The client `subscribe`s (with the VAPID public key); the server sends via
`tempest-fastapi-sdk[webpush]` (pywebpush).

```python
from tempestweb.pwa import webpush


async def enable_notifications(app: object) -> None:
    """Subscribe the browser to WebPush and persist the subscription.

    Args:
        app: The running app handle.
    """
    sub = await webpush.subscribe(vapid_public_key=app.settings.VAPID_PUBLIC_KEY)
    await app.native.http.request("POST", "/webpush/subscribe", json=sub.to_dict())
```

!!! danger "iOS/Safari requires the PWA installed"
    On iOS (16.4+), WebPush **only works with the PWA installed** to the home
    screen. On desktop and Android browsers it works without installing. Test on a
    real device — see [Manual verification](#manual-verification).

## P4 & P5 — CI gate and manifest extras

- **P4 — PWA gate in CI.** A job runs **Lighthouse PWA** (headless) + service
  worker tests; CI rejects a PR that breaks "installable", offline or push.
- **P5 — Manifest extras.** `share_target` (pairs with
  [`native.share`](capabilities.md)), shortcuts and file handlers.

## Manual verification

!!! note "What requires a real device/browser"
    Some PWA guarantees **cannot** be fully automated; CI uses headless Lighthouse
    (P4), but confirm by hand:

    - Install the app from the prompt and open it from the home screen.
    - Turn off the network and confirm the **2nd load** opens the app (offline).
    - Receive a WebPush notification — **on iOS, with the PWA installed**.

## Recap

- Track P makes the app **installable** (P0) and **offline after the 1st load**
  (P1).
- The offline runtime (P2) uses **IndexedDB + queue/replay** with an idempotency
  key.
- **WebPush** (P3) subscribes in the browser and sends via `tempest-fastapi-sdk`.
- **CI** (P4) locks regressions with Lighthouse; some tests need a real device.

The offline store is exposed to Python as the `storage` capability — see
[Capabilities](capabilities.md). For production health, see
[Observability](observability.md). 🚀
