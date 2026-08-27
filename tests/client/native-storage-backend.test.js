// Which backend the `storage` capability actually writes into.
//
// `native/storage.js` prefers `deps.store` (IndexedDB) and falls back to
// localStorage when none is injected. Every test for it injected one or the
// other, so both branches were covered and the question that matters was not:
// what does the **browser** get? Nothing wired a store into `browserDeps()`, so
// the answer in Modes A and B was localStorage — measured in a real Chrome tab,
// with `indexedDB.databases()` empty and a 142,890-character value sitting in
// `localStorage`, under a capability whose docstring promises IndexedDB.
//
// Two things follow from the fallback that a persistence test cannot see: the
// ~5 MB localStorage cap (against IndexedDB's disk-proportional quota) and its
// synchronous writes on the main thread. A third is measurable: the `deflate`
// codec configures the IndexedDB store, so on localStorage `storage.configure`
// answered `active=deflate supported=True` and stored the value raw.
//
// So these pin the wiring itself.

import { test } from "node:test";
import assert from "node:assert/strict";
import { IDBFactory } from "fake-indexeddb";

import { browserDeps, dispatch } from "../../client/native/index.js";
import { createIdbKv, setKvCodec } from "../../client/native/idb-kv.js";

/** Build a native_call envelope. */
function call(capability, args = {}, callId = "c1") {
  return { kind: "native_call", call_id: callId, capability, args };
}

/**
 * Read what IndexedDB actually holds under a key, bypassing the decoder.
 *
 * @param {string} name
 * @returns {Promise<*>} The stored record: a string, or a codec envelope.
 */
function rawRecord(name) {
  return new Promise((resolve, reject) => {
    const open = globalThis.indexedDB.open("tempestweb");
    open.onerror = () => reject(open.error);
    open.onsuccess = () => {
      const db = open.result;
      const request = db.transaction("kv", "readonly").objectStore("kv").get(name);
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        resolve(request.result);
        db.close();
      };
    };
  });
}

// One factory for the file: `browserDeps()` builds its store once and holds it,
// exactly as a tab does, so swapping the global per test would leave the cached
// store pointing at a database no assertion can see.
globalThis.indexedDB = new IDBFactory();

test("browserDeps: hands the storage capability an IndexedDB store", async () => {
  const deps = browserDeps();
  assert.ok(deps.store, "browserDeps must carry a store, or storage falls back");
  assert.equal(typeof deps.store.put, "function");
  assert.equal(typeof deps.store.get, "function");
  assert.equal(typeof deps.store.keys, "function");
  assert.equal(typeof deps.store.remove, "function");
});

test("browserDeps: builds the store once, not once per dispatch", async () => {
  assert.equal(browserDeps().store, browserDeps().store);
});

test("storage: a value written through the default deps lands in IndexedDB", async () => {
  const written = await dispatch(
    call("storage.put", { name: "note", content: "persisted-value-42" }),
  );
  assert.equal(written.ok, true);

  const read = await dispatch(call("storage.get", { name: "note" }));
  assert.equal(read.ok, true);
  assert.equal(read.value.content, "persisted-value-42");

  const direct = createIdbKv(globalThis.indexedDB);
  assert.equal(await direct.get("note"), "persisted-value-42");
});

test("storage: the deflate codec reaches the store the writes go to", async () => {
  const configured = await dispatch(call("storage.configure", { codec: "deflate" }));
  assert.equal(configured.ok, true);
  if (!configured.value.supported) return;

  try {
    const bulk = "repetition ".repeat(4000);
    await dispatch(call("storage.put", { name: "bulk", content: bulk }));
    const read = await dispatch(call("storage.get", { name: "bulk" }));
    assert.equal(read.value.content, bulk);

    const stored = await rawRecord("bulk");
    assert.equal(
      stored && stored["$twcodec"],
      "deflate",
      "a configured deflate codec must store an envelope, not the raw string",
    );
    assert.ok(
      stored.bytes.byteLength < bulk.length / 4,
      `compressed ${stored.bytes.byteLength} bytes against ${bulk.length} characters`,
    );
  } finally {
    setKvCodec("json");
  }
});

test("storage: a runtime with no IndexedDB still stores, through localStorage", async () => {
  const previousLocal = globalThis.localStorage;
  const map = new Map();
  globalThis.localStorage = {
    get length() {
      return map.size;
    },
    key: (index) => [...map.keys()][index] ?? null,
    getItem: (name) => (map.has(name) ? map.get(name) : null),
    setItem: (name, value) => map.set(name, String(value)),
    removeItem: (name) => map.delete(name),
  };
  try {
    const deps = browserDeps();
    const written = await dispatch(
      call("storage.put", { name: "note", content: "fallback" }),
      { ...deps, store: undefined },
    );
    assert.equal(written.ok, true);
    assert.equal(map.get("note"), "fallback");
  } finally {
    globalThis.localStorage = previousLocal;
  }
});
