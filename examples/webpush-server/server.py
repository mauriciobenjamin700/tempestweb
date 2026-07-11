"""End-to-end WebPush demo — VAPID + subscribe + send, in one FastAPI app.

Run it::

    # optional: pin a keypair so subscriptions survive restarts
    eval "$(tempestweb vapid --env)"   # exports VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY
    uv run uvicorn server:app --app-dir examples/webpush-server --reload

Open http://127.0.0.1:8000, click **Enable notifications** (grant permission),
then **Send test** — a system notification appears, delivered by the browser's
push service via the server's VAPID-signed request.

The server owns the VAPID keys, the subscription store and the send path
(:func:`tempestweb.server.webpush.webpush_router`). The browser owns the
subscribe flow (service worker + ``PushManager``). No secrets are committed: the
private key comes from the environment, falling back to an **ephemeral** dev
keypair (subscriptions then reset on restart).
"""

from __future__ import annotations

from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse

from tempestweb.server import (
    InMemorySubscriptionStore,
    VapidConfig,
    WebPushService,
    generate_vapid_keys,
    webpush_router,
)


def _vapid() -> VapidConfig:
    """Resolve VAPID config from the env, or a dev-only ephemeral keypair."""
    config = VapidConfig.from_env()
    if config.enabled:
        return config
    keys = generate_vapid_keys()
    return VapidConfig(public_key=keys.public_key, private_key=keys.private_key)


VAPID = _vapid()
SERVICE = WebPushService(VAPID, store=InMemorySubscriptionStore())

app = FastAPI(title="tempestweb webpush demo")
app.include_router(webpush_router(SERVICE))

# --- Minimal service worker: show a notification for each incoming push -------
_SW = """\
self.addEventListener("push", (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch { data = {}; }
  const title = data.title || "tempestweb";
  event.waitUntil(
    self.registration.showNotification(title, { body: data.body || "" }),
  );
});
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
});
"""

# --- Page: subscribe against the server's VAPID key, then trigger a send ------
_PAGE = """\
<!doctype html>
<meta charset="utf-8" />
<title>tempestweb webpush demo</title>
<h1>WebPush end-to-end</h1>
<button id="enable">Enable notifications</button>
<button id="send">Send test</button>
<pre id="log"></pre>
<script type="module">
const log = (m) => (document.getElementById("log").textContent += m + "\\n");
const b64ToU8 = (s) => {
  const pad = "=".repeat((4 - (s.length % 4)) % 4);
  const raw = atob((s + pad).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
};
const reg = await navigator.serviceWorker.register("/sw.js", { type: "classic" });
await navigator.serviceWorker.ready;

document.getElementById("enable").onclick = async () => {
  const perm = await Notification.requestPermission();
  if (perm !== "granted") return log("permission: " + perm);
  const { public_key } = await (await fetch("/webpush/vapid-public-key")).json();
  const sub = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: b64ToU8(public_key),
  });
  await fetch("/webpush/subscribe", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(sub.toJSON()),
  });
  log("subscribed: " + sub.endpoint.slice(0, 48) + "...");
};

document.getElementById("send").onclick = async () => {
  const res = await (await fetch("/webpush/send", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ title: "Hello", body: "from tempestweb" }),
  })).json();
  log("send -> " + JSON.stringify(res));
};
</script>
"""


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    """Serve the demo page."""
    return _PAGE


@app.get("/sw.js")
async def service_worker() -> Response:
    """Serve the minimal push-handling service worker (with a JS MIME type)."""
    return Response(content=_SW, media_type="text/javascript")
