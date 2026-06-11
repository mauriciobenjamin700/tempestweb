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
// The offline queue lives in client/offline/{store,sync}.js; this worker only
// pings open clients to replay it (see replayFromSync).

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
    const strategy = chooseStrategy(request.url, self.location.origin, PRECACHE_ASSETS);
    event.respondWith(handleFetch(request, strategy));
  });

  self.addEventListener("push", (event) => {
    event.waitUntil(
      (async () => {
        /** @type {Object} */
        let data = {};
        try {
          data = event.data ? event.data.json() : {};
        } catch {
          data = { body: event.data ? event.data.text() : "" };
        }
        const notification = buildNotification(data);
        if (notification) {
          await self.registration.showNotification(
            notification.title,
            notification.options,
          );
        }
      })(),
    );
  });

  self.addEventListener("notificationclick", (event) => {
    event.notification.close();
    const url = resolveClickUrl(
      event.notification.data,
      event.action || null,
      "/",
    );
    event.waitUntil(focusOrOpen(url));
  });

  // Background Sync: replay the durable offline queue when connectivity returns.
  self.addEventListener("sync", (event) => {
    if (event.tag === "tw-offline-replay") {
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
    const cache = await caches.open(PRECACHE);
    cache.put(request, response.clone());
    return response;
  }
  // stale-while-revalidate
  const cached = await caches.match(request);
  const networkPromise = fetch(request)
    .then(async (response) => {
      const cache = await caches.open(RUNTIME);
      cache.put(request, response.clone());
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
 * Replay the offline queue from a Background Sync event.
 *
 * Delegates to the page's sync module shape by posting a REPLAY message to all
 * clients (the queue lives in IndexedDB owned by client/pwa/sync.js). When no
 * client is open, the worker has no network helper here; the queue stays durable
 * and replays on the next open. P2.
 *
 * @returns {Promise<void>}
 */
async function replayFromSync() {
  const all = await clients.matchAll({ includeUncontrolled: true });
  for (const client of all) {
    client.postMessage({ type: "REPLAY_OFFLINE_QUEUE" });
  }
}
