// asset-cache.js — cache large binaries (models, wasm, datasets) offline.  P2.
//
// A "download once, version it, refresh on manifest change, serve cache-first
// offline" helper, adopted from the famachapp-pwa model-sync pattern. It owns a
// dedicated Cache Storage bucket the page manages directly (separate from the
// service worker's precache/runtime caches), so a big asset is fetched a single
// time and then read from cache with no network on later loads.
//
// - ensureCached(request, opts): return the cached Response, downloading it once
//   if absent. Concurrent calls for the same URL share one in-flight fetch
//   (dedup), so a boot warmup and a lazy load racing don't double-download.
// - syncAssets(manifest, opts): compare a manifest `version` against the stored
//   one; on change, drop the listed assets and re-fetch them, then persist the
//   new version. Returns { refreshed } so callers can reset in-memory handles
//   (e.g. an ONNX/Pyodide session) when the bytes changed.
//
// Cache Storage, fetch and localStorage are injected, so it is unit-testable
// under Node with fakes. Degrades by throwing a clear error when Cache Storage or
// fetch is unavailable (callers can fall back to a direct fetch).

/** @type {Map<string, Promise<Response>>} */
const _inflight = new Map();

/** Default Cache Storage bucket for page-managed assets. */
const DEFAULT_BUCKET = "tw-assets";

/**
 * Resolve the URL string of a Request-or-URL argument.
 * @param {string|Request} request
 * @returns {string} The URL.
 */
function urlOf(request) {
  return typeof request === "string" ? request : request.url;
}

/**
 * Read a key from a Storage, swallowing access errors (private mode / SSR).
 * @param {?Storage} storage
 * @param {string} key
 * @returns {?string}
 */
function safeGet(storage, key) {
  if (!storage) return null;
  try {
    return storage.getItem(key);
  } catch {
    return null;
  }
}

/**
 * Write a key to a Storage, swallowing access errors.
 * @param {?Storage} storage
 * @param {string} key
 * @param {string} value
 * @returns {void}
 */
function safeSet(storage, key, value) {
  if (!storage) return;
  try {
    storage.setItem(key, value);
  } catch {
    // Best-effort; a blocked write just means the next boot re-checks the version.
  }
}

/**
 * Return a large asset from a dedicated cache, downloading it once if absent.
 *
 * Concurrent calls for the same URL share one in-flight fetch. Only a successful
 * response is cached; a failed fetch is returned as-is (and not stored) so the
 * next call retries.
 *
 * @param {string|Request} request   The asset URL (or Request).
 * @param {Object} [opts]
 * @param {string} [opts.bucket]     Cache Storage bucket name (default "tw-assets").
 * @param {CacheStorage} [opts.caches]   Cache Storage override (tests).
 * @param {typeof fetch} [opts.fetch]    fetch override (tests).
 * @returns {Promise<Response>} The cached (or freshly fetched) response.
 * @throws {Error} When Cache Storage or fetch is unavailable.
 */
export async function ensureCached(request, opts = {}) {
  const bucket = opts.bucket ?? DEFAULT_BUCKET;
  const cachesImpl =
    opts.caches ?? (typeof caches !== "undefined" ? caches : null);
  const fetchImpl = opts.fetch ?? (typeof fetch !== "undefined" ? fetch : null);
  if (!cachesImpl || !fetchImpl) {
    throw new Error("asset-cache requires Cache Storage and fetch");
  }
  const url = urlOf(request);
  const cache = await cachesImpl.open(bucket);
  const hit = await cache.match(url);
  if (hit) return hit;
  if (_inflight.has(url)) return _inflight.get(url);

  const pending = (async () => {
    const res = await fetchImpl(request);
    if (res && res.ok) await cache.put(url, res.clone());
    return res;
  })();
  _inflight.set(url, pending);
  try {
    return await pending;
  } finally {
    _inflight.delete(url);
  }
}

/**
 * @typedef {Object} AssetManifest
 * @property {string} version                 A hash/tag that changes when any asset changes.
 * @property {Array<{url: string}>} assets    The assets to keep cached.
 */

/**
 * Ensure the cached assets match a versioned manifest, refreshing on change.
 *
 * When the manifest `version` differs from the stored one, every listed asset is
 * dropped from the bucket and re-fetched, then the new version is persisted. When
 * the version is unchanged this is a no-op. Returns whether a refresh happened so
 * callers can invalidate in-memory handles built from the old bytes.
 *
 * @param {AssetManifest} manifest   The version + asset list.
 * @param {Object} [opts]
 * @param {string} [opts.bucket]        Cache bucket (default "tw-assets").
 * @param {string} [opts.versionKey]    Storage key for the stored version.
 * @param {Storage} [opts.storage]      Storage override (default localStorage).
 * @param {CacheStorage} [opts.caches]  Cache Storage override (tests).
 * @param {typeof fetch} [opts.fetch]   fetch override (tests).
 * @returns {Promise<{refreshed: boolean}>} Whether assets were re-downloaded.
 */
export async function syncAssets(manifest, opts = {}) {
  const bucket = opts.bucket ?? DEFAULT_BUCKET;
  const versionKey = opts.versionKey ?? `${bucket}:version`;
  const storage =
    opts.storage ?? (typeof localStorage !== "undefined" ? localStorage : null);
  const cachesImpl =
    opts.caches ?? (typeof caches !== "undefined" ? caches : null);

  const stored = safeGet(storage, versionKey);
  if (stored != null && stored === manifest.version) return { refreshed: false };

  const cache = cachesImpl ? await cachesImpl.open(bucket) : null;
  for (const asset of manifest.assets || []) {
    if (cache) await cache.delete(asset.url);
    await ensureCached(asset.url, {
      bucket,
      caches: cachesImpl,
      fetch: opts.fetch,
    });
  }
  safeSet(storage, versionKey, manifest.version);
  return { refreshed: true };
}
