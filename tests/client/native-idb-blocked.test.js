// What a version bump does to the tabs that are already running.
//
// `openDb` used to register `onupgradeneeded`, `onsuccess` and `onerror`. The
// events a version bump actually produces were missing, and each omission costs
// something different:
//
//   1. `onblocked` — fired at the tab trying to upgrade, because another tab
//      still holds the old version. Nothing settled the promise, so the
//      `storage` call never answered. Not slow: never.
//   2. `onversionchange` — fired at the tab holding the old version, asking it
//      to let go. Nothing listened, so it never let go, so (1) never cleared on
//      its own. The two failures fed each other.
//
// These tests use `fake-indexeddb` rather than a hand-written factory, because
// what is under test is sequencing the spec defines and a stand-in would be free
// to get wrong. Two facts below were found by running it, and both contradict
// the obvious implementation:
//
//   * `blocked` is **not** terminal — the request stays pending and still
//     succeeds once the blocker closes. Rejecting there would fail an open that
//     was about to work.
//   * a tab that is merely *using* the database while someone else upgrades gets
//     **no event at all**. Arming a timeout inside `onblocked` would rescue the
//     upgrading tab and leave every other tab hanging exactly as before.
//
// The `onversionchange` half ships now rather than with the bump that needs it,
// because it only helps if it is in the build that is ALREADY deployed when
// someone raises the version. Shipping it with the bump is one release too late.
//
// Every test carries an explicit `timeout`, which is not boilerplate: without the
// fix these do not fail, they HANG — the `storage` promise never settles, which
// is the defect itself. A regression has to reach CI as a red test, not as a job
// that runs until the runner kills it.

import { test } from "node:test";
import assert from "node:assert/strict";

import { IDBFactory } from "fake-indexeddb";

import {
  createIdbKv,
  StoreUnavailableError,
} from "../../client/native/idb-kv.js";
import { dispatch, StoreBlockedError } from "../../client/native/index.js";

const DB_NAME = "tempestweb";

/**
 * Hold `tempestweb` open at version 1 without listening for `versionchange`.
 *
 * Stands in for a tab running a build from before this file existed: it never
 * lets go, so an upgrade beside it stays blocked until something closes it by
 * hand. That is the state the deadline exists for.
 *
 * @param {IDBFactory} idb  The factory every "tab" in the test shares.
 * @returns {Promise<IDBDatabase>} The held connection.
 */
function holdOldVersion(idb) {
  return new Promise((resolve, reject) => {
    const open = /** @type {*} */ (idb).open(DB_NAME, 1);
    open.onupgradeneeded = () => open.result.createObjectStore("kv");
    open.onsuccess = () => resolve(open.result);
    open.onerror = () => reject(open.error);
  });
}

/**
 * Request version 2 of `tempestweb`, logging every event the request receives.
 *
 * @param {IDBFactory} idb  The factory every "tab" in the test shares.
 * @returns {{events: string[], settled: Promise<string>}} The event log, and a
 *          promise that settles only when the open itself does.
 */
function upgradeToV2(idb) {
  /** @type {string[]} */
  const events = [];
  const open = /** @type {*} */ (idb).open(DB_NAME, 2);
  const settled = new Promise((resolve) => {
    open.onblocked = () => events.push("blocked");
    open.onupgradeneeded = () => events.push("upgradeneeded");
    open.onsuccess = () => {
      events.push("success");
      open.result.close();
      resolve("success");
    };
    open.onerror = () => {
      events.push("error");
      resolve("error");
    };
  });
  return { events, settled };
}

/**
 * Await `promise`, or reject with `label` when it does not settle in time.
 *
 * Used wherever a regression's symptom is a hang rather than a wrong value. A
 * bare `await` there would run until the CI runner kills the job, and a job that
 * times out reads as flaky infrastructure instead of as the broken assertion it
 * is.
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

test(
  "blocked is not terminal: the open still succeeds once the holder closes",
  { timeout: 5000 },
  async () => {
    const idb = new IDBFactory();
    const held = await holdOldVersion(idb);
    const { events, settled } = upgradeToV2(idb);

    await new Promise((r) => setTimeout(r, 20));
    assert.deepEqual(events, ["blocked"], "only blocked so far");

    held.close();
    assert.equal(await within(settled, "the unblocked upgrade"), "success");
    assert.deepEqual(events, ["blocked", "upgradeneeded", "success"]);
  },
);

test(
  "a bystander's open receives no event while another tab upgrades",
  { timeout: 5000 },
  async () => {
    const idb = new IDBFactory();
    const held = await holdOldVersion(idb);
    const upgrading = upgradeToV2(idb);
    await new Promise((r) => setTimeout(r, 20));

    /** @type {string[]} */
    const seen = [];
    const bystander = /** @type {*} */ (idb).open(DB_NAME, 1);
    bystander.onblocked = () => seen.push("blocked");
    bystander.onsuccess = () => seen.push("success");
    bystander.onerror = () => seen.push("error");
    await new Promise((r) => setTimeout(r, 50));

    assert.deepEqual(
      seen,
      [],
      "this silence is the whole reason the deadline cannot live inside onblocked",
    );

    held.close();
    await upgrading.settled;
  },
);

test(
  "an open that never settles answers `blocked`, not `unavailable`",
  { timeout: 5000 },
  async () => {
    const idb = new IDBFactory();
    const held = await holdOldVersion(idb);
    const upgrading = upgradeToV2(idb);
    await new Promise((r) => setTimeout(r, 20));

    const store = /** @type {*} */ (
      createIdbKv(/** @type {*} */ (idb), { openTimeoutMs: 40 })
    );
    await assert.rejects(
      () => store.put("k", "v"),
      (err) => {
        assert.ok(
          err instanceof StoreBlockedError,
          `expected StoreBlockedError, got ${err && err.name}`,
        );
        assert.equal(err.code, "blocked");
        assert.ok(
          !(err instanceof StoreUnavailableError),
          "must not be StoreUnavailableError — that degrades to localStorage and " +
            "splits the app's data across two backends",
        );
        return true;
      },
    );

    held.close();
    await upgrading.settled;
  },
);

test(
  "the blocked code survives the router, so Python sees NativeError('blocked')",
  { timeout: 5000 },
  async () => {
    const idb = new IDBFactory();
    const held = await holdOldVersion(idb);
    const upgrading = upgradeToV2(idb);
    await new Promise((r) => setTimeout(r, 20));

    const store = createIdbKv(/** @type {*} */ (idb), { openTimeoutMs: 40 });
    const result = await dispatch(
      {
        call_id: "1",
        capability: "storage.put",
        args: { name: "k", content: "v" },
      },
      /** @type {*} */ ({ store }),
    );

    assert.equal(result.ok, false);
    assert.equal(
      result.error,
      "blocked",
      "the opaque 'error' code would tell the app nothing actionable",
    );

    held.close();
    await upgrading.settled;
  },
);

test(
  "a connection that arrives after the deadline is closed, not kept",
  { timeout: 5000 },
  async () => {
    const idb = new IDBFactory();
    const held = await holdOldVersion(idb);
    const upgrading = upgradeToV2(idb);
    await new Promise((r) => setTimeout(r, 20));

    const store = /** @type {*} */ (
      createIdbKv(/** @type {*} */ (idb), { openTimeoutMs: 40 })
    );
    await assert.rejects(() => store.put("k", "v"), StoreBlockedError);

    held.close();
    assert.equal(await upgrading.settled, "success");

    const after = upgradeToV2(idb);
    await new Promise((r) => setTimeout(r, 40));
    assert.ok(
      !after.events.includes("blocked"),
      "the abandoned open was kept alive and is now blocking the next upgrade: " +
        JSON.stringify(after.events),
    );
  },
);

test(
  "a healthy open still resolves well inside the deadline",
  { timeout: 5000 },
  async () => {
    const idb = new IDBFactory();
    const store = /** @type {*} */ (
      createIdbKv(/** @type {*} */ (idb), { openTimeoutMs: 2000 })
    );
    await store.put("k", "v");
    assert.equal(await store.get("k"), "v");
  },
);

test(
  "an open connection yields when another tab upgrades",
  { timeout: 5000 },
  async () => {
    const idb = new IDBFactory();
    const store = /** @type {*} */ (
      createIdbKv(/** @type {*} */ (idb), { openTimeoutMs: 2000 })
    );
    await store.put("legacy", "kept");

    const held = await new Promise((resolve, reject) => {
      const open = /** @type {*} */ (idb).open(DB_NAME, 1);
      open.onsuccess = () => resolve(open.result);
      open.onerror = () => reject(open.error);
    });
    let closed = false;
    const original = held.close.bind(held);
    held.onversionchange = () => {
      closed = true;
      original();
    };

    const { settled } = upgradeToV2(idb);
    assert.equal(await settled, "success");
    assert.ok(closed, "the holder was asked to close, and did");
  },
);

test(
  "the store's own connections do not block a later upgrade",
  { timeout: 5000 },
  async () => {
    const idb = new IDBFactory();
    const store = /** @type {*} */ (
      createIdbKv(/** @type {*} */ (idb), { openTimeoutMs: 200 })
    );
    await store.put("legacy", "legacy-value");

    const { events, settled } = upgradeToV2(idb);
    assert.equal(
      await within(settled, "the upgrade beside a held store connection"),
      "success",
    );
    assert.deepEqual(
      events,
      ["upgradeneeded", "success"],
      "the store holds its connection open now, so this only passes because " +
        "`versionchange` closes it — without that handler the upgrade never " +
        "completes and every later storage call is stuck behind it",
    );
  },
);
