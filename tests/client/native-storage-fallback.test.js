// A runtime with no IndexedDB at all, storing through localStorage.
//
// The point is what `browserDeps()` decides, not what the fallback branch does
// with a store handed to it — `tests/client/native.test.js` already covers the
// branch. A version of this case that called `browserDeps()` and then threw the
// store away by hand (`{ ...deps, store: undefined }`) could not fail: it would
// pass just the same if `browserDeps()` handed out a store in a runtime that has
// no IndexedDB, which is precisely the wiring under test.
//
// So this asserts the decision first, and dispatches with the default deps.
//
// Own file, own process: no `globalThis.indexedDB` is installed anywhere in it,
// and `browserDeps()` caches its answer for the life of the module. A sibling
// file that installs a factory would poison this one.

import { test } from "node:test";
import assert from "node:assert/strict";

import { browserDeps, dispatch } from "../../client/native/index.js";

/** Build a native_call envelope. */
function call(capability, args = {}, callId = "c1") {
  return { kind: "native_call", call_id: callId, capability, args };
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

test("this process really has no IndexedDB", () => {
  assert.equal(globalThis.indexedDB, undefined, "no test in this file may install one");
});

test("browserDeps hands out no store where there is no IndexedDB", () => {
  assert.equal(browserDeps().store, undefined);
});

test("storage stores and reads back through localStorage", async () => {
  const written = await dispatch(call("storage.put", { name: "note", content: "fallback" }));
  assert.equal(written.ok, true, `the capability must still work: ${written.message}`);
  assert.equal(kept.get("note"), "fallback", "the value must land in localStorage");

  const read = await dispatch(call("storage.get", { name: "note" }));
  assert.equal(read.ok, true);
  assert.equal(read.value.content, "fallback");
});

test("storage.configure reports json, because localStorage cannot hold bytes", async () => {
  const configured = await dispatch(call("storage.configure", { codec: "deflate" }));
  assert.equal(configured.ok, true);
  assert.equal(configured.value.requested, "deflate");
  assert.equal(
    configured.value.active,
    "json",
    "answering deflate here promises a compression that never happens",
  );
});

test("a raw write stays raw: nothing on this backend is an envelope", async () => {
  const bulk = "repetition ".repeat(4000);
  await dispatch(call("storage.put", { name: "bulk", content: bulk }));
  assert.equal(kept.get("bulk"), bulk, "localStorage holds the string it was given");
  assert.equal(kept.get("bulk").length, bulk.length);
});
