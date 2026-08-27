// What an IndexedDB failure looks like from the outside.
//
// Two things the store got wrong while every test injected a hand-written
// stand-in for it, so nothing exercised the real transaction plumbing:
//
//   1. `quota_exceeded` was documented and unreachable. `tempestweb/native/
//      storage.py` and docs/examples/file-storage.md promise
//      `NativeError("quota_exceeded")`, but a request that failed with
//      `QuotaExceededError` left the store as a plain throw, and the router
//      codes anything that is not a CapabilityError as the opaque "error".
//   2. A transaction that aborted read as a success. `withStore` resolved on the
//      request's `onsuccess`, which fires while the transaction is still open —
//      so a commit the browser threw away came back `ok: true`.
//
// The factory below is a stand-in for IndexedDB, not for the store: a request
// error aborts its transaction with `tx.error` set to that error, which is what
// the spec mandates and what makes case 1 reachable at all.

import { test } from "node:test";
import assert from "node:assert/strict";

import { CapabilityError, dispatch } from "../../client/native/index.js";
import { createIdbKv, StoreUnavailableError } from "../../client/native/idb-kv.js";

/**
 * Build an IDBFactory stand-in with a scripted outcome.
 *
 * @param {Object} [options]
 * @param {*} [options.openError]  Rejects the open request with this error.
 * @param {*} [options.openThrows]  Makes `open()` throw this synchronously.
 * @param {*} [options.requestError]  Fails the write request, aborting the tx.
 * @param {boolean} [options.abortAtCommit]  Succeeds the request, then aborts.
 * @returns {IDBFactory} The stand-in.
 */
function fakeIdb({
  openError = null,
  openThrows = null,
  requestError = null,
  abortAtCommit = false,
} = {}) {
  const factory = {
    open() {
      if (openThrows) throw openThrows;
      const open = { onsuccess: null, onerror: null, onupgradeneeded: null, result: null };
      const db = {
        objectStoreNames: { contains: () => true },
        close() {},
        transaction() {
          const tx = { oncomplete: null, onabort: null, error: null };
          tx.objectStore = () => ({
            put() {
              const request = { onsuccess: null, onerror: null, error: requestError };
              setTimeout(() => {
                if (requestError) {
                  if (request.onerror) request.onerror();
                  tx.error = requestError;
                  setTimeout(() => tx.onabort && tx.onabort(), 0);
                  return;
                }
                if (request.onsuccess) request.onsuccess();
                setTimeout(() => {
                  if (!abortAtCommit) {
                    if (tx.oncomplete) tx.oncomplete();
                    return;
                  }
                  tx.error = named("AbortError", "the commit failed");
                  if (tx.onabort) tx.onabort();
                }, 0);
              }, 0);
              return request;
            },
          });
          return tx;
        },
      };
      open.result = db;
      open.error = openError;
      setTimeout(() => {
        if (openError) {
          if (open.onerror) open.onerror();
          return;
        }
        if (open.onsuccess) open.onsuccess();
      }, 0);
      return open;
    },
  };
  return /** @type {*} */ (factory);
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

test("idb-kv: a quota failure carries the documented quota_exceeded code", async () => {
  const store = createIdbKv(fakeIdb({ requestError: named("QuotaExceededError", "no room") }));
  await assert.rejects(
    () => store.put("bulk", "x"),
    (err) => {
      assert.ok(
        err instanceof CapabilityError,
        `a bare ${err.constructor.name} reaches the router as error: "error"`,
      );
      assert.equal(err.code, "quota_exceeded");
      return true;
    },
  );
});

test("storage.put over a full store answers quota_exceeded, not error", async () => {
  const store = createIdbKv(fakeIdb({ requestError: named("QuotaExceededError", "no room") }));
  const result = await dispatch(
    {
      kind: "native_call",
      call_id: "c1",
      capability: "storage.put",
      args: { name: "k", content: "v" },
    },
    { store },
  );
  assert.equal(result.ok, false);
  assert.equal(result.error, "quota_exceeded");
});

test("idb-kv: a transaction that aborts at commit time is a failure", async () => {
  const store = createIdbKv(fakeIdb({ abortAtCommit: true }));
  await assert.rejects(
    () => store.put("k", "v"),
    /AbortError/,
    "resolving on the request's onsuccess reports a write the browser threw away",
  );
});

test("idb-kv: a database that will not open reports the store unavailable", async () => {
  const store = createIdbKv(fakeIdb({ openError: named("InvalidStateError", "private window") }));
  assert.ok(store, "the factory exists, so createIdbKv cannot tell yet");
  await assert.rejects(() => store.get("k"), StoreUnavailableError);
});

test("idb-kv: a factory whose open() throws also reports the store unavailable", async () => {
  const store = createIdbKv(fakeIdb({ openThrows: named("SecurityError", "storage is blocked") }));
  await assert.rejects(() => store.put("k", "v"), StoreUnavailableError);
});
