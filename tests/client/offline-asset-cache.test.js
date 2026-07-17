// Tests for client/offline/asset-cache.js — P2 large-binary caching.
import { test } from "node:test";
import assert from "node:assert/strict";
import { ensureCached, syncAssets } from "../../client/offline/asset-cache.js";

/** A minimal CacheStorage double. */
function fakeCaches() {
  const buckets = new Map();
  return {
    async open(name) {
      if (!buckets.has(name)) {
        const store = new Map();
        buckets.set(name, {
          match: async (url) => store.get(url),
          put: async (url, res) => store.set(url, res),
          delete: async (url) => store.delete(url),
          _store: store,
        });
      }
      return buckets.get(name);
    },
    _buckets: buckets,
  };
}

/** A fetch double that counts calls per URL and returns a cacheable response. */
function countingFetch(ok = true) {
  const calls = {};
  const fetch = async (url) => {
    calls[url] = (calls[url] || 0) + 1;
    return { ok, url, clone() { return this; } };
  };
  return { fetch, calls };
}

/** An in-memory Storage double. */
function fakeStorage() {
  const map = new Map();
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
  };
}

test("ensureCached downloads once, then serves from cache", async () => {
  const caches = fakeCaches();
  const { fetch, calls } = countingFetch();
  const a = await ensureCached("/models/m.onnx", { caches, fetch });
  const b = await ensureCached("/models/m.onnx", { caches, fetch });
  assert.equal(a.url, "/models/m.onnx");
  assert.equal(b.url, "/models/m.onnx");
  assert.equal(calls["/models/m.onnx"], 1, "fetched exactly once");
});

test("ensureCached dedups concurrent fetches for the same URL", async () => {
  const caches = fakeCaches();
  const { fetch, calls } = countingFetch();
  const [a, b] = await Promise.all([
    ensureCached("/big.wasm", { caches, fetch }),
    ensureCached("/big.wasm", { caches, fetch }),
  ]);
  assert.ok(a && b);
  assert.equal(calls["/big.wasm"], 1, "one in-flight fetch shared");
});

test("ensureCached does not cache a failed response (retries next call)", async () => {
  const caches = fakeCaches();
  const { fetch, calls } = countingFetch(false);
  await ensureCached("/x", { caches, fetch });
  await ensureCached("/x", { caches, fetch });
  assert.equal(calls["/x"], 2, "not cached, so re-fetched");
});

test("syncAssets downloads all on first run and records the version", async () => {
  const caches = fakeCaches();
  const { fetch, calls } = countingFetch();
  const storage = fakeStorage();
  const manifest = { version: "v1", assets: [{ url: "/a" }, { url: "/b" }] };
  const out = await syncAssets(manifest, { caches, fetch, storage });
  assert.deepEqual(out, { refreshed: true });
  assert.equal(calls["/a"], 1);
  assert.equal(calls["/b"], 1);
  assert.equal(storage.getItem("tw-assets:version"), "v1");
});

test("syncAssets is a no-op when the version is unchanged", async () => {
  const caches = fakeCaches();
  const { fetch, calls } = countingFetch();
  const storage = fakeStorage();
  const manifest = { version: "v1", assets: [{ url: "/a" }] };
  await syncAssets(manifest, { caches, fetch, storage });
  const out = await syncAssets(manifest, { caches, fetch, storage });
  assert.deepEqual(out, { refreshed: false });
  assert.equal(calls["/a"], 1, "no re-download on unchanged version");
});

test("syncAssets re-downloads when the version changes", async () => {
  const caches = fakeCaches();
  const { fetch, calls } = countingFetch();
  const storage = fakeStorage();
  await syncAssets({ version: "v1", assets: [{ url: "/a" }] }, { caches, fetch, storage });
  const out = await syncAssets(
    { version: "v2", assets: [{ url: "/a" }] },
    { caches, fetch, storage },
  );
  assert.deepEqual(out, { refreshed: true });
  assert.equal(calls["/a"], 2, "stale asset dropped and re-fetched");
  assert.equal(storage.getItem("tw-assets:version"), "v2");
});
