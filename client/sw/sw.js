// sw.js — tempestweb service worker.  PHASES P1 (precache + update), P2 (runtime
// strategies + offline queue replay), P3 (WebPush handlers).
//
// Pure JS, no build step, no imports at runtime (a SW cannot use bare ES module
// specifiers without { type: "module" } support across browsers, so this file is
// self-contained and classic-worker-safe). It is also `node --check`-clean.
//
// The build step (Trilho C) replaces the __PRECACHE_MANIFEST__ /
// __CACHE_VERSION__ placeholders with the hashed asset list and a content hash.
// Until then the defaults below make the worker run as-is in dev.
//
// App-shell precache (cache-first): always the pure-JS client
// (dom/style/events/tempestweb + the active transport), index.html and icons; in
// Mode A also the Pyodide runtime, the tempest-core wheel and app.py. See
// ../../docs/plan.md §7 P1 for the contract.
//
// Files: client/sw/sw.js (this worker) + client/sw/register.js (registration).
// The offline queue lives in client/offline/{store,sync}.js; on a Background /
// Periodic Sync this worker drains it directly (dynamic import → drainOfflineQueue),
// so the queue empties with the tab closed, and falls back to pinging open clients
// if that import is unavailable (see replayFromSync).

/* global self, caches, clients, fetch, Response, Request, URL */

/**
 * @typedef {Object} PrecacheConfig
 * @property {string} version     Cache version tag (bumped per build hash).
 * @property {string[]} assets    App-shell URLs to precache (cache-first).
 */

// --- Build-injected config (placeholders replaced at build; safe defaults) ---

/** @type {string} */
const CACHE_VERSION = "__CACHE_VERSION__".includes("CACHE_VERSION")
  ? "tw-dev"
  : "__CACHE_VERSION__";

/** @type {string[]} */
const PRECACHE_ASSETS = (() => {
  const injected = "__PRECACHE_MANIFEST__";
  if (injected.includes("PRECACHE_MANIFEST")) {
    // Dev default app-shell (Mode A adds pyodide + wheel + app.py at build).
    return [
      "/",
      "/index.html",
      "/client/tempestweb.js",
      "/client/dom.js",
      "/client/style.js",
      "/client/events.js",
      "/client/transport.js",
    ];
  }
  try {
    return JSON.parse(injected);
  } catch {
    return [];
  }
})();

/** Names of the caches this worker owns, derived from the version. */
const PRECACHE = `${CACHE_VERSION}-precache`;
const RUNTIME = `${CACHE_VERSION}-runtime`;

/**
 * Max entries kept in the stale-while-revalidate runtime cache before the oldest
 * are evicted. Bounds unbounded growth from visiting many same-origin URLs.
 */
const RUNTIME_MAX_ENTRIES = 60;

// --- Pure helpers (exported for unit tests; harmless in the worker) ----------

/**
 * Decide the caching strategy for a request URL.
 *
 * App-shell assets are cache-first (instant offline after first load). API calls
 * (under /api/, /ws, /sse) are network-first/never-cached. Other same-origin GETs
 * use stale-while-revalidate. See P2 in the plan.
 *
 * @param {string} url        The request URL (absolute).
 * @param {string} origin     The worker's origin.
 * @param {string[]} shell    The precached app-shell asset URLs.
 * @returns {"cache-first"|"network-first"|"stale-while-revalidate"|"network-only"}
 */
export function chooseStrategy(url, origin, shell) {
  let parsed;
  try {
    parsed = new URL(url, origin);
  } catch {
    return "network-only";
  }
  // Cross-origin (CDNs, analytics) — don't manage; let the network handle it.
  if (parsed.origin !== origin) return "network-only";

  const path = parsed.pathname;
  // Never cache live data / transport endpoints.
  if (
    path.startsWith("/api/") ||
    path.startsWith("/ws") ||
    path.startsWith("/sse") ||
    path.startsWith("/webpush")
  ) {
    return "network-first";
  }

  // App-shell precached assets: cache-first.
  const shellPaths = shell.map((a) => {
    try {
      return new URL(a, origin).pathname;
    } catch {
      return a;
    }
  });
  if (shellPaths.includes(path)) return "cache-first";

  // Everything else same-origin: stale-while-revalidate.
  return "stale-while-revalidate";
}

/**
 * Compute which existing cache names should be deleted on activate.
 *
 * Any cache not owned by the current version is stale and removed.
 *
 * @param {string[]} existing   All cache names currently present.
 * @param {string[]} keep       Cache names to keep (current version's caches).
 * @returns {string[]} Cache names to delete.
 */
export function stalecaches(existing, keep) {
  const keepSet = new Set(keep);
  return existing.filter((name) => !keepSet.has(name));
}

/**
 * Whether a Background/Periodic Sync tag belongs to the offline queue.
 *
 * The worker owns any tag under the ``tw-offline`` prefix — the one-off replay
 * tag (``tw-offline-replay``, registered automatically on enqueue) and any
 * periodic tag an app opts into via ``native.bgsync.register_periodic`` (e.g.
 * ``tw-offline-periodic``). Periodic Background Sync is permission-gated and
 * interval-driven, so it is deliberately the app's decision to register — the
 * worker only handles the wake-up when a matching tag fires.
 *
 * @param {*} tag   The sync event's tag.
 * @returns {boolean} True when the worker should drain the queue for this tag.
 */
export function isOfflineSyncTag(tag) {
  return typeof tag === "string" && tag.startsWith("tw-offline");
}

/**
 * Whether a response is safe to persist in a cache.
 *
 * Only successful, same-origin (``basic``) or plain responses are cacheable. An
 * error (``4xx``/``5xx``) or an opaque cross-origin response must never be
 * stored: caching a ``404``/``500`` would make the worker serve that failure as
 * a valid app-shell asset for the whole cache lifetime, and an opaque body can't
 * be validated. The response's own ``Cache-Control: no-store`` is honored too.
 *
 * @param {?Response} response   The fetched response (may be undefined).
 * @returns {boolean} True when the response may be written to a cache.
 */
export function isCacheable(response) {
  if (!response || !response.ok) return false;
  if (response.type && response.type !== "basic" && response.type !== "default") {
    return false;
  }
  const cc = response.headers && response.headers.get
    ? response.headers.get("cache-control")
    : null;
  if (cc && /(^|[,\s])no-store([,\s]|$)/i.test(cc)) return false;
  return true;
}

/**
 * Evict the oldest entries so a cache holds at most ``max`` responses.
 *
 * The Cache API returns keys in insertion order, so the excess at the front is
 * the least-recently-added; deleting it bounds the runtime cache's growth (a
 * stale-while-revalidate cache would otherwise accumulate every visited URL for
 * the cache version's lifetime). A no-op when the cache is within budget.
 *
 * @param {Cache} cache   The cache to trim (needs keys() + delete()).
 * @param {number} max    The maximum number of entries to keep.
 * @returns {Promise<number>} How many entries were evicted.
 */
export async function trimCache(cache, max) {
  const keys = await cache.keys();
  if (keys.length <= max) return 0;
  const excess = keys.slice(0, keys.length - max);
  for (const key of excess) await cache.delete(key);
  return excess.length;
}

/**
 * A minimal last-resort offline document for a navigation with no cached shell.
 *
 * Returned only when the network is down and neither the requested route nor the
 * app shell (``"/"``) is cached — a genuinely cold offline start.
 *
 * @returns {Response} A ``503`` HTML response.
 */
export function offlineFallbackResponse() {
  const body =
    "<!doctype html><meta charset=utf-8><title>Offline</title>" +
    '<body style="font:1rem system-ui;margin:2rem">' +
    "<h1>Offline</h1><p>This page isn't available offline yet.</p>";
  return new Response(body, {
    status: 503,
    headers: { "content-type": "text/html; charset=utf-8" },
  });
}

/**
 * Serve a navigation request with an offline fallback to the cached app shell.
 *
 * SPA navigations to client-side routes (e.g. ``/orders/5``) have no precached
 * entry of their own, so an offline navigation must fall back to the cached shell
 * for the app to boot and route. Order: live network (cached for reuse) → the
 * exact cached response → the cached shell → a minimal offline document.
 *
 * @param {Request} request   The navigation request.
 * @param {Object} [deps]     Injected for tests.
 * @param {(req: Request) => Promise<Response>} [deps.fetchFn]    Network fetch.
 * @param {(req: (Request|string)) => Promise<?Response>} [deps.matchFn]  Cache match.
 * @param {string} [deps.shellUrl]   The shell URL to fall back to (default "/").
 * @returns {Promise<Response>} The response to serve.
 */
export async function handleNavigation(request, deps = {}) {
  const fetchFn = deps.fetchFn ?? ((r) => fetch(r));
  const matchFn = deps.matchFn ?? ((r) => caches.match(r));
  const shellUrl = deps.shellUrl ?? "/";
  try {
    const response = await fetchFn(request);
    if (isCacheable(response) && typeof caches !== "undefined") {
      const cache = await caches.open(RUNTIME);
      await cache.put(request, response.clone());
      await trimCache(cache, RUNTIME_MAX_ENTRIES);
    }
    return response;
  } catch (err) {
    const exact = await matchFn(request);
    if (exact) return exact;
    const shell = await matchFn(shellUrl);
    if (shell) return shell;
    return offlineFallbackResponse();
  }
}

/**
 * Build the fetch-based sender the worker uses to replay a queued mutation.
 *
 * Reconstructs the original request from a stored queue row and carries the
 * idempotency key so the server dedups a re-sent mutation — matching the
 * page-side sender in client/native/offline.js.
 *
 * @returns {(m: Object) => Promise<{ok: boolean, status: number}>} The sender.
 */
function workerSend() {
  return async (mutation) => {
    /** @type {Object} */
    const init = {
      method: mutation.method,
      headers: { "idempotency-key": mutation.idempotencyKey },
    };
    if (mutation.body !== undefined && mutation.body !== null) {
      init.headers["content-type"] = "application/json";
      init.body = JSON.stringify(mutation.body);
    }
    const res = await fetch(mutation.url, init);
    return { ok: res.ok, status: res.status };
  };
}

/**
 * Drain the durable offline queue from within the worker (P2 §1).
 *
 * Reuses the page's queue logic (client/offline/{store,sync}.js) so the replay
 * policy — FIFO, dead-letter, conflict lane — is identical whether the page or
 * the worker drains, and replays every owner present in the store (not just the
 * default). This is what lets a Background/Periodic Sync drain the queue with
 * the tab closed. The store, queue class and sender are injected so the logic is
 * unit-testable; production wires the dynamic import + the fetch sender.
 *
 * @param {Object} deps
 * @param {Function} deps.createOfflineStore   The OfflineStore factory.
 * @param {Function} deps.OfflineQueue         The OfflineQueue class.
 * @param {IDBFactory} [deps.indexedDB]        IDB factory override (tests).
 * @param {(m: Object) => Promise<{ok:boolean, status:number}>} [deps.send]
 *        Network sender (default: the worker's fetch sender).
 * @returns {Promise<{sent: number, owners: number}>} Drain outcome.
 */
export async function drainOfflineQueue(deps) {
  const store = deps.createOfflineStore({
    databaseName: "tempestweb-offline",
    tableName: "mutations",
    keyPath: "id",
    ownerField: "owner",
    indexedDB: deps.indexedDB,
  });
  const send = deps.send ?? workerSend();
  const queue = new deps.OfflineQueue({ store, send });
  const all = await store.listAll();
  const owners = [
    ...new Set(all.filter((r) => r.status === "pending").map((r) => r.owner)),
  ];
  let sent = 0;
  for (const owner of owners) {
    const out = await queue.replay(owner);
    sent += out.sent;
  }
  return { sent, owners: owners.length };
}

/**
 * Build the notification options for an incoming push payload.
 *
 * Mirrors the React SDK's installPushHandler: a `transform` may return `null` to
 * drop a silent push; otherwise it shapes title/options. P3.
 *
 * @param {Object} data                       Parsed push JSON (may be {}).
 * @param {Object} [opts]                      Defaults and transform.
 * @param {string} [opts.defaultTitle]         Fallback title.
 * @param {string} [opts.defaultIcon]          Fallback icon URL.
 * @param {(d: Object) => ({title: string, options: Object}|null)} [opts.transform]
 *        Optional shaper; return null to suppress the notification.
 * @returns {{title: string, options: Object}|null} The notification, or null to drop.
 */
export function buildNotification(data, opts = {}) {
  const defaults = {
    defaultTitle: opts.defaultTitle ?? "tempestweb",
    defaultIcon: opts.defaultIcon ?? "/icons/icon-192.png",
  };
  if (typeof opts.transform === "function") {
    return opts.transform(data);
  }
  const title = data.title ?? defaults.defaultTitle;
  /** @type {Object} */
  const options = {
    body: data.body ?? "",
    icon: data.icon ?? defaults.defaultIcon,
    badge: data.badge ?? defaults.defaultIcon,
    data: data.data ?? {},
  };
  if (Array.isArray(data.actions)) options.actions = data.actions;
  if (data.tag) options.tag = data.tag;
  if (data.renotify) options.renotify = true;
  return { title, options };
}

/**
 * Resolve the URL a notification click should open/focus.
 *
 * The click routes via the core DeepLinkEvent: the push `data.url` (or a custom
 * action's url) wins; otherwise the fallback. P3.
 *
 * @param {Object} notificationData   The notification's `data` payload.
 * @param {?string} action            The action id clicked (or null for body).
 * @param {string} [fallbackUrl]      URL when no deep link is present.
 * @returns {string} The URL to open or focus.
 */
export function resolveClickUrl(notificationData, action, fallbackUrl = "/") {
  const data = notificationData || {};
  if (action && data.actions && typeof data.actions === "object") {
    const target = data.actions[action];
    if (typeof target === "string") return target;
  }
  if (typeof data.url === "string") return data.url;
  return fallbackUrl;
}

/**
 * Apply the Badging API based on a push payload, where supported.
 *
 * A numeric `data.badge_count` (or top-level `badge_count`) sets the app icon
 * badge; `0` clears it. Degrades silently where the Badging API is absent.
 *
 * @param {Object} data        Parsed push JSON.
 * @param {Object} [navigatorLike]   Object exposing setAppBadge/clearAppBadge
 *        (defaults to the global `navigator`; injectable for tests).
 * @returns {Promise<void>}
 */
export async function applyBadge(data, navigatorLike) {
  const nav =
    navigatorLike ?? (typeof navigator !== "undefined" ? navigator : undefined);
  if (!nav) return;
  const raw = data && (data.badge_count ?? (data.data && data.data.badge_count));
  if (typeof raw !== "number" || Number.isNaN(raw)) return;
  try {
    if (raw > 0 && typeof nav.setAppBadge === "function") {
      await nav.setAppBadge(raw);
    } else if (raw <= 0 && typeof nav.clearAppBadge === "function") {
      await nav.clearAppBadge();
    }
  } catch {
    // Badging is best-effort; never let it break the push handler.
  }
}

/**
 * Build the `push` event handler (P3), extracted so it is unit-testable.
 *
 * The returned handler parses the push payload, shows the notification (unless a
 * `transform` drops it) and applies the app badge. Injectable `registration` /
 * `navigator` keep it testable without a live ServiceWorkerGlobalScope.
 *
 * @param {Object} [opts]
 * @param {ServiceWorkerRegistration} [opts.registration]
 *        The registration to show notifications on (default: self.registration).
 * @param {Object} [opts.navigator]   Badging target (default: global navigator).
 * @param {string} [opts.defaultTitle]   Fallback notification title.
 * @param {string} [opts.defaultIcon]    Fallback notification icon URL.
 * @param {(d: Object) => ({title: string, options: Object}|null)} [opts.transform]
 *        Optional shaper; return null to suppress the notification.
 * @returns {(event: Object) => Promise<void>} The push handler body.
 */
export function installPushHandler(opts = {}) {
  return async function onPush(event) {
    /** @type {Object} */
    let data = {};
    try {
      data = event.data ? event.data.json() : {};
    } catch {
      data = { body: event.data ? event.data.text() : "" };
    }
    const notification = buildNotification(data, opts);
    if (notification) {
      const reg =
        opts.registration ??
        (typeof self !== "undefined" ? self.registration : undefined);
      if (reg) {
        await reg.showNotification(notification.title, notification.options);
      }
    }
    await applyBadge(data, opts.navigator);
  };
}

/**
 * Build the `notificationclick` event handler (P3), extracted for unit testing.
 *
 * The returned handler closes the notification, resolves the deep-link URL and
 * focuses/opens a client window on it. `focusOrOpen` is injectable so the routing
 * can be asserted without a live `clients` registry.
 *
 * @param {Object} [opts]
 * @param {string} [opts.fallbackUrl]   URL when the payload carries no deep link.
 * @param {(url: string) => Promise<void>} [opts.focusOrOpen]
 *        Override the focus/open routine (default: the worker's focusOrOpen).
 * @returns {(event: Object) => Promise<void>} The notificationclick handler body.
 */
export function installNotificationClickHandler(opts = {}) {
  const open = opts.focusOrOpen ?? focusOrOpen;
  const fallback = opts.fallbackUrl ?? "/";
  return async function onNotificationClick(event) {
    if (event.notification && typeof event.notification.close === "function") {
      event.notification.close();
    }
    const data = event.notification ? event.notification.data : {};
    const url = resolveClickUrl(data, event.action || null, fallback);
    await open(url);
  };
}

// --- Worker lifecycle (guarded so this file is also importable in tests) -----

if (typeof self !== "undefined" && typeof self.addEventListener === "function") {
  self.addEventListener("install", (event) => {
    event.waitUntil(
      (async () => {
        const cache = await caches.open(PRECACHE);
        await cache.addAll(PRECACHE_ASSETS);
        // Do NOT skipWaiting automatically — the page drives the update prompt.
      })(),
    );
  });

  self.addEventListener("activate", (event) => {
    event.waitUntil(
      (async () => {
        const names = await caches.keys();
        await Promise.all(
          stalecaches(names, [PRECACHE, RUNTIME]).map((n) => caches.delete(n)),
        );
        await self.clients.claim();
      })(),
    );
  });

  // The page posts {type:"SKIP_WAITING"} when the user confirms the update.
  self.addEventListener("message", (event) => {
    if (event.data && event.data.type === "SKIP_WAITING") {
      self.skipWaiting();
    }
  });

  self.addEventListener("fetch", (event) => {
    const request = event.request;
    if (request.method !== "GET") return; // mutations handled by the offline queue
    if (request.mode === "navigate") {
      event.respondWith(handleNavigation(request));
      return;
    }
    const strategy = chooseStrategy(request.url, self.location.origin, PRECACHE_ASSETS);
    event.respondWith(handleFetch(request, strategy));
  });

  const onPush = installPushHandler();
  self.addEventListener("push", (event) => {
    event.waitUntil(onPush(event));
  });

  const onNotificationClick = installNotificationClickHandler();
  self.addEventListener("notificationclick", (event) => {
    event.waitUntil(onNotificationClick(event));
  });

  self.addEventListener("sync", (event) => {
    if (isOfflineSyncTag(event.tag)) {
      event.waitUntil(replayFromSync());
    }
  });

  self.addEventListener("periodicsync", (event) => {
    if (isOfflineSyncTag(event.tag)) {
      event.waitUntil(replayFromSync());
    }
  });
}

// --- Worker-only async helpers (not exercised by node --check beyond syntax) -

/**
 * Serve a request according to the chosen strategy.
 * @param {Request} request   The fetch request.
 * @param {string} strategy   The strategy id from chooseStrategy.
 * @returns {Promise<Response>} The response.
 */
async function handleFetch(request, strategy) {
  if (strategy === "network-only" || strategy === "network-first") {
    try {
      return await fetch(request);
    } catch (err) {
      const cached = await caches.match(request);
      if (cached) return cached;
      throw err;
    }
  }
  if (strategy === "cache-first") {
    const cached = await caches.match(request);
    if (cached) return cached;
    const response = await fetch(request);
    if (isCacheable(response)) {
      const cache = await caches.open(PRECACHE);
      cache.put(request, response.clone());
    }
    return response;
  }
  // stale-while-revalidate
  const cached = await caches.match(request);
  const networkPromise = fetch(request)
    .then(async (response) => {
      if (isCacheable(response)) {
        const cache = await caches.open(RUNTIME);
        await cache.put(request, response.clone());
        await trimCache(cache, RUNTIME_MAX_ENTRIES);
      }
      return response;
    })
    .catch(() => cached);
  return cached || networkPromise;
}

/**
 * Focus an existing client on `url` or open a new window.
 * @param {string} url   The URL to focus or open.
 * @returns {Promise<void>}
 */
async function focusOrOpen(url) {
  const all = await clients.matchAll({ type: "window", includeUncontrolled: true });
  for (const client of all) {
    if ("focus" in client) {
      client.postMessage({ type: "DEEP_LINK", url });
      return client.focus();
    }
  }
  if (clients.openWindow) await clients.openWindow(url);
}

/**
 * Post a message to every controlled client (open tab), best-effort.
 * @param {Object} message   The structured-clonable message to post.
 * @returns {Promise<void>}
 */
async function notifyClients(message) {
  const all = await clients.matchAll({ includeUncontrolled: true });
  for (const client of all) client.postMessage(message);
}

/**
 * Drain the offline queue from a Background/Periodic Sync event (P2 §1).
 *
 * Dynamically imports the page's queue modules and drains IndexedDB directly, so
 * the queue empties even with no tab open. On success it pings any open client to
 * refresh its UI/count (OFFLINE_QUEUE_DRAINED) and to reconcile the read side
 * (OFFLINE_PULL — the page holds the auth token the worker lacks). If the import
 * or the drain fails
 * (e.g. the modules are unreachable — the SW ships only in the wasm/transpile
 * artifacts that serve /client/ — or IndexedDB is unavailable in this worker), it
 * degrades to the legacy behavior — asking an open client to replay
 * (REPLAY_OFFLINE_QUEUE) — so the queue is never stranded.
 *
 * Concurrency: the worker drain and the page's replayOnReconnect can fire at the
 * same time (the OfflineQueue single-flight guard is per-instance, not shared
 * across the worker and the page). A mutation can therefore be sent twice; the
 * idempotency key is the sole guard against a double-apply — the server dedups on
 * it, so a concurrent double-send is safe, never duplicated. `delete` is
 * idempotent too, so both drainers converge on an empty queue.
 *
 * The loader/notifier are injected so both the success and the fallback paths are
 * unit-testable without a live ServiceWorkerGlobalScope.
 *
 * @param {Object} [deps]
 * @param {() => Promise<{createOfflineStore: Function, OfflineQueue: Function}>} [deps.loadModules]
 *        Resolve the queue modules (default: dynamic import of /client/offline/*).
 * @param {(message: Object) => Promise<void>} [deps.notify]
 *        Post a message to open clients (default: notifyClients).
 * @param {(d: Object) => Promise<{sent:number, owners:number}>} [deps.drain]
 *        The drainer (default: drainOfflineQueue).
 * @returns {Promise<void>}
 */
async function replayFromSync(deps = {}) {
  const loadModules =
    deps.loadModules ??
    (async () => {
      const [store, sync] = await Promise.all([
        import("/client/offline/store.js"),
        import("/client/offline/sync.js"),
      ]);
      return { createOfflineStore: store.createOfflineStore, OfflineQueue: sync.OfflineQueue };
    });
  const notify = deps.notify ?? notifyClients;
  const drain = deps.drain ?? drainOfflineQueue;
  try {
    const { createOfflineStore, OfflineQueue } = await loadModules();
    const result = await drain({ createOfflineStore, OfflineQueue });
    await notify({ type: "OFFLINE_QUEUE_DRAINED", ...result });
    await notify({ type: "OFFLINE_PULL" });
  } catch (err) {
    await notify({ type: "REPLAY_OFFLINE_QUEUE" });
  }
}

export { replayFromSync };
