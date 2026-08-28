// A profile where IndexedDB exists and will not open.
//
// This is the regression that wiring a store into `browserDeps()` opened.
// `createIdbKv()` decides there is a store from `globalThis.indexedDB` alone, so
// a Chrome origin whose storage the user blocked (`SecurityError`) or a Firefox
// private window (`InvalidStateError`) got a store object that fails every
// operation — and `native/storage.js` prefers an injected store, so the
// localStorage fallback was never reached. Measured before the fix, with
// `indexedDB.open()` firing `onerror`:
//
//   dispatch(storage.put) -> {"ok":false,"error":"error","message":"SecurityError: ..."}
//   localStorage          -> untouched
//
// The same profile on the previous release wrote and read through localStorage,
// so this was a straight loss of the capability. These pin the fallback being
// reachable again, and the dead store being dropped rather than retried forever.
//
// Own file, own process: `browserDeps()` caches its store for the life of the
// module, exactly as a tab does, so a failing factory cannot share a process
// with a working one.

import { test } from "node:test";
import assert from "node:assert/strict";

import { browserDeps, dispatch } from "../../client/native/index.js";

/** Build a native_call envelope. */
function call(capability, args = {}, callId = "c1") {
  return { kind: "native_call", call_id: callId, capability, args };
}

/**
 * A DOMException stand-in: what matters downstream is `name`.
 *
 * @param {string} name
 * @param {string} message
 * @returns {Error}
 */
function named(name, message) {
  return Object.assign(new Error(message), { name });
}

/** What localStorage holds, so the assertions can look at the backend itself. */
const kept = new Map();

globalThis.localStorage = /** @type {*} */ ({
  get length() {
    return kept.size;
  },
  key: (index) => [...kept.keys()][index] ?? null,
  getItem: (name) => (kept.has(name) ? kept.get(name) : null),
  setItem: (name, value) => kept.set(name, String(value)),
  removeItem: (name) => kept.delete(name),
});

/** How many times the runtime was asked to open the database. */
let opens = 0;

globalThis.indexedDB = /** @type {*} */ ({
  open() {
    opens += 1;
    const request = {
      onsuccess: null,
      onerror: null,
      onupgradeneeded: null,
      error: named("SecurityError", "the operation is insecure"),
    };
    setTimeout(() => request.onerror && request.onerror(), 0);
    return request;
  },
});

test("browserDeps hands out a store, because indexedDB is there to see", () => {
  assert.ok(
    browserDeps().store,
    "the existence of the factory is all createIdbKv can check synchronously",
  );
});

test("storage.put degrades to localStorage instead of failing the write", async () => {
  const written = await dispatch(call("storage.put", { name: "note", content: "fallback-value" }));
  assert.equal(written.ok, true, `a blocked profile must still store: ${written.message}`);
  assert.equal(kept.get("note"), "fallback-value", "the value must land in localStorage");

  const read = await dispatch(call("storage.get", { name: "note" }));
  assert.equal(read.ok, true);
  assert.equal(read.value.content, "fallback-value");
});

test("the store that will not open is dropped, not retried on every call", async () => {
  assert.equal(browserDeps().store, undefined, "the dead store must not be handed out again");

  const before = opens;
  const written = await dispatch(call("storage.put", { name: "second", content: "2" }));
  assert.equal(written.ok, true);
  assert.equal(kept.get("second"), "2");
  assert.equal(opens, before, "a dropped store must not reopen the database");
});

test("storage.configure stops promising deflate once the backend is localStorage", async () => {
  const configured = await dispatch(call("storage.configure", { codec: "deflate" }));
  assert.equal(configured.ok, true);
  assert.equal(configured.value.requested, "deflate");
  assert.equal(configured.value.active, "json", "localStorage holds strings, not bytes");
});

test("storage.list_keys and remove keep working on the fallback", async () => {
  const listed = await dispatch(call("storage.list"));
  assert.deepEqual([...listed.value.keys].sort(), ["note", "second"]);

  const removed = await dispatch(call("storage.remove", { name: "note" }));
  assert.equal(removed.ok, true);
  assert.equal(kept.has("note"), false);

  const gone = await dispatch(call("storage.remove", { name: "note" }));
  assert.equal(gone.ok, false);
  assert.equal(gone.error, "not_found");
});
