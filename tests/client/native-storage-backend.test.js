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
// So these pin the wiring itself, in a process where IndexedDB works. The two
// runtimes that do not get one have their own files, because `browserDeps()`
// caches its store for the life of the module: `native-storage-fallback.test.js`
// (no `indexedDB`) and `native-storage-blocked.test.js` (an `indexedDB` that
// will not open).

import { test } from "node:test";
import assert from "node:assert/strict";
import { IDBFactory } from "fake-indexeddb";

import { browserDeps, dispatch } from "../../client/native/index.js";
import { createIdbKv, setKvCodec } from "../../client/native/idb-kv.js";
import { native } from "../../client/transpile/native.js";

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

// Read at load, before the migration case installs one: a value that lands
// anywhere in this process can only have landed in IndexedDB.
const HAD_LOCAL_STORAGE = globalThis.localStorage !== undefined;

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
  assert.equal(
    configured.value.supported,
    true,
    "Node 18+ ships CompressionStream; a skip here would hide the assertions below",
  );
  assert.equal(configured.value.active, "deflate");

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

test("Mode C reaches the same backend, keeping no store of its own", async () => {
  assert.equal(
    HAD_LOCAL_STORAGE,
    false,
    "no localStorage in this process, so a stored value can only be in IndexedDB",
  );
  await native.storage.put("mode-c", "through-the-facade");
  assert.equal(await native.storage.get("mode-c"), "through-the-facade");
  assert.equal(await rawRecord("mode-c"), "through-the-facade");
  assert.deepEqual(await native.storage.list_keys(), (await createIdbKv().keys()).sort());
});

test("the documented migration recipe moves a legacy localStorage value in", async () => {
  const legacy = new Map([
    ["notes", "written by 0.122.0"],
    ["draft", "also written by 0.122.0"],
  ]);
  globalThis.localStorage = /** @type {*} */ ({
    getItem: (name) => (legacy.has(name) ? legacy.get(name) : null),
    setItem: (name, value) => legacy.set(name, String(value)),
    removeItem: (name) => legacy.delete(name),
  });

  const MARK = "tw.storage.migrated.v1";
  const LEGACY = ["notes", "draft", "never-written"];

  if (!localStorage.getItem(MARK)) {
    let allOk = true;
    for (const name of LEGACY) {
      const content = localStorage.getItem(name);
      if (content === null) continue;
      const written = await dispatch(call("storage.put", { name, content }, `migrate-${name}`));
      allOk = allOk && written.ok;
    }
    if (allOk) localStorage.setItem(MARK, "1");
  }

  assert.equal(await rawRecord("notes"), "written by 0.122.0", "the value must reach IndexedDB");
  assert.equal(await rawRecord("draft"), "also written by 0.122.0");
  assert.equal(await rawRecord("never-written"), undefined, "an absent key is skipped");
  assert.equal(legacy.get(MARK), "1", "the mark stops the next boot from redoing it");
  assert.equal(legacy.get("notes"), "written by 0.122.0", "the original is left in place");
});
