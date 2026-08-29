// The store opens the database once, not once per operation (issue #195, item 2).
//
// `withStore` used to open and close the database on every call. Measured with a
// counting `IDBFactory`, five `put`s plus five `get`s cost **10 opens**. The
// object cached in `browserDeps()` saved allocating the store, and nothing else —
// its JSDoc said so.
//
// Holding the connection is not free, and that is why it could not ship first: an
// open connection is exactly what blocks another tab's upgrade. It became safe
// only once `versionchange` closed and dropped it, which is why that half shipped
// in the previous commit. The tests here pin both directions — the open count
// falls, and the connection still yields.
//
// One consequence only showed up once the connection was reused: after another
// tab upgrades, this build's reopen asks for the version it knows and gets
// `VersionError`. That used to be folded into `StoreUnavailableError`, which
// degrades the page to `localStorage` for good — splitting the app's data across
// two backends over a condition that means "reload for the new build". It now has
// its own code, and the case below pins that.
//
// Every case carries an explicit `timeout`, and the waits that could hang go
// through `within`: the failure mode of this area is a promise that never
// settles, and a CI job killed by the runner reads as flaky infrastructure
// rather than as the broken assertion it is.

import { test } from "node:test";
import assert from "node:assert/strict";

import { IDBFactory } from "fake-indexeddb";

import { createIdbKv } from "../../client/native/idb-kv.js";

/**
 * Wrap a factory so every `open()` is counted.
 *
 * @param {IDBFactory} real  The factory to delegate to.
 * @returns {{idb: IDBFactory, count: () => number, reset: () => void}} The
 *          counting factory and its tally.
 */
function counting(real) {
  let opens = 0;
  const idb = /** @type {*} */ ({
    open: (...args) => {
      opens += 1;
      return /** @type {*} */ (real).open(...args);
    },
    deleteDatabase: (...args) =>
      /** @type {*} */ (real).deleteDatabase(...args),
  });
  return { idb, count: () => opens, reset: () => (opens = 0) };
}

/**
 * Await `promise`, or reject with `label` when it does not settle in time.
 *
 * @param {Promise<*>} promise  The promise under test.
 * @param {string} label  What was being waited for, for the failure message.
 * @param {number} [ms]  How long to allow.
 * @returns {Promise<*>} What `promise` resolved to.
 */
function within(promise, label, ms = 1500) {
  return Promise.race([
    promise,
    new Promise((_, reject) =>
      setTimeout(
        () => reject(new Error(`${label} never settled within ${ms}ms`)),
        ms,
      ).unref?.(),
    ),
  ]);
}

test("ten operations cost one open, not ten", { timeout: 5000 }, async (t) => {
  const { idb, count } = counting(new IDBFactory());
  const store = /** @type {*} */ (createIdbKv(idb));
  t.after(() => store.close());

  for (let i = 0; i < 5; i += 1) await store.put(`k${i}`, "v");
  for (let i = 0; i < 5; i += 1) await store.get(`k${i}`);

  assert.equal(
    count(),
    1,
    "the store must reuse its connection; this was 10 before the change",
  );
});

test(
  "concurrent callers share one open, not one each",
  { timeout: 5000 },
  async (t) => {
    const { idb, count } = counting(new IDBFactory());
    const store = /** @type {*} */ (createIdbKv(idb));
    t.after(() => store.close());

    await Promise.all(
      Array.from({ length: 8 }, (_, i) => store.put(`p${i}`, "v")),
    );

    assert.equal(
      count(),
      1,
      "without single-flight, eight parallel writes each start their own open " +
        "and the caching buys nothing exactly when it matters most",
    );
    assert.equal(await store.get("p7"), "v", "and every write still landed");
  },
);

test("a failed open is not cached forever", { timeout: 5000 }, async (t) => {
  const real = new IDBFactory();
  let fail = true;
  const idb = /** @type {*} */ ({
    open: (...args) => {
      if (fail) throw new Error("SecurityError: storage blocked");
      return /** @type {*} */ (real).open(...args);
    },
  });
  const store = /** @type {*} */ (createIdbKv(idb));
  t.after(() => store.close());

  await assert.rejects(() => store.put("k", "v"));

  fail = false;
  await store.put("k", "v");
  assert.equal(
    await store.get("k"),
    "v",
    "a profile that recovers must be retried, not answered from a poisoned cache",
  );
});

test(
  "the held connection yields when another tab upgrades, and reopens loudly",
  { timeout: 5000 },
  async (t) => {
    const idb = new IDBFactory();
    const { idb: counted, count, reset } = counting(idb);
    const store = /** @type {*} */ (createIdbKv(counted));
    t.after(() => store.close());

    await store.put("before", "kept");
    assert.equal(count(), 1);

    const upgrade = new Promise((resolve) => {
      const open = /** @type {*} */ (idb).open("tempestweb", 2);
      open.onblocked = () => resolve("blocked");
      open.onsuccess = () => {
        open.result.close();
        resolve("success");
      };
      open.onerror = () => resolve("error");
    });

    assert.equal(
      await within(upgrade, "the upgrade beside a held store connection"),
      "success",
      "a held connection blocks an upgrade unless versionchange closes it",
    );

    reset();
    await assert.rejects(
      () => store.put("after", "x"),
      (err) => {
        assert.equal(
          err.code,
          "stale",
          "this build asks for version 1 against a database now at 2, so the " +
            "reopen must say so — coding it `unavailable` would degrade the " +
            "page to localStorage permanently and split the app's data in two",
        );
        assert.equal(err.name, "StoreStaleError");
        return true;
      },
    );
    assert.equal(
      count(),
      1,
      "the closed connection was dropped, so the call did try a fresh open",
    );
  },
);

test(
  "close releases the connection so an upgrade sails",
  { timeout: 5000 },
  async () => {
    const idb = new IDBFactory();
    const store = /** @type {*} */ (createIdbKv(/** @type {*} */ (idb)));
    await store.put("k", "v");
    store.close();

    /** @type {string[]} */
    const events = [];
    const upgrade = new Promise((resolve) => {
      const open = /** @type {*} */ (idb).open("tempestweb", 2);
      open.onblocked = () => events.push("blocked");
      open.onsuccess = () => {
        open.result.close();
        resolve("success");
      };
      open.onerror = () => resolve("error");
    });

    assert.equal(await within(upgrade, "the upgrade after close()"), "success");
    assert.deepEqual(events, [], "close() means the upgrade never even blocks");
  },
);

test(
  "a store reopens after close, rather than staying dead",
  { timeout: 5000 },
  async (t) => {
    const { idb, count } = counting(new IDBFactory());
    const store = /** @type {*} */ (createIdbKv(idb));
    t.after(() => store.close());

    await store.put("k", "v");
    store.close();
    assert.equal(await store.get("k"), "v", "the value survives the close");
    assert.equal(count(), 2, "one open before the close, one after");
  },
);
