// Two owners on one origin stop sharing a keyspace (issue #195).
//
// The capability keyed IndexedDB by the raw name the app passed, so on a device
// where two people signed in — Mode B, two logins — the second one's `put`
// overwrote the first one's value, `list_keys()` returned both sets, and
// `remove()` reached across.
//
// The damage was not theoretical and not confined to keys the app chose:
// `tempestweb/query/persistence.py` restores its cache by walking `list_keys()`
// and keeping what carries its own prefix. Before scoping, user B's boot filled
// the QueryCache with API responses user A had persisted. That is why the
// listing here returns the app's own names with the owner prefix stripped —
// a caller that filters the listing has to keep working unchanged.
//
// Scoping is derived in `client/native/storage.js`, above the backend choice, so
// the `localStorage` fallback is scoped too. Every test below therefore runs
// twice: once with an IndexedDB store injected, once with none. The fallback is
// the profile nobody watches, and the one where an unscoped keyspace would sit
// unnoticed.

import { test } from "node:test";
import assert from "node:assert/strict";

import { IDBFactory } from "fake-indexeddb";

import { createIdbKv } from "../../client/native/idb-kv.js";
import {
  resetStorageOwner,
  storageConfigure,
  storageGet,
  storageList,
  storagePut,
  storageRemove,
} from "../../client/native/storage.js";

/**
 * A `localStorage` stand-in: the fallback backend, in memory.
 *
 * @returns {Storage} Enough of the interface for the capability.
 */
function memoryLocalStorage() {
  /** @type {Map<string, string>} */
  const map = new Map();
  return /** @type {*} */ ({
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    removeItem: (k) => map.delete(k),
    key: (i) => [...map.keys()][i] ?? null,
    get length() {
      return map.size;
    },
  });
}

/**
 * Build the two backend profiles the capability can run on.
 *
 * @returns {{name: string, make: () => Object}[]} One entry per profile, each
 *          with a factory — a fresh backend per test, so one case cannot leave
 *          a key behind that changes the meaning of the next.
 */
function backends() {
  return [
    {
      name: "IndexedDB",
      make: () => ({ store: createIdbKv(/** @type {*} */ (new IDBFactory())) }),
    },
    {
      name: "localStorage fallback",
      make: () => ({ localStorage: memoryLocalStorage() }),
    },
  ];
}

/**
 * Point the capability at an owner.
 *
 * @param {string} owner  The owner, or `""` for the unscoped default.
 * @param {Object} deps  The backend profile.
 * @returns {Promise<Object>} The configure result.
 */
function asOwner(owner, deps) {
  return storageConfigure({ codec: "json", owner }, /** @type {*} */ (deps));
}

for (const { name, make } of backends()) {
  test(
    `${name}: one owner cannot read another's value`,
    { timeout: 5000 },
    async (t) => {
      t.after(resetStorageOwner);
      const deps = make();

      await asOwner("alice", deps);
      await storagePut(
        { name: "notes", content: "alice's" },
        /** @type {*} */ (deps),
      );

      await asOwner("bob", deps);
      await assert.rejects(
        () => storageGet({ name: "notes" }, /** @type {*} */ (deps)),
        (err) => err.code === "not_found",
        "bob must not see alice's key at all",
      );

      await storagePut(
        { name: "notes", content: "bob's" },
        /** @type {*} */ (deps),
      );
      await asOwner("alice", deps);
      const back = await storageGet({ name: "notes" }, /** @type {*} */ (deps));
      assert.equal(
        back.content,
        "alice's",
        "bob's write must not have overwritten it",
      );
    },
  );

  test(
    `${name}: list_keys returns one owner's names, unprefixed`,
    { timeout: 5000 },
    async (t) => {
      t.after(resetStorageOwner);
      const deps = make();

      await asOwner("alice", deps);
      await storagePut(
        { name: "notes", content: "a" },
        /** @type {*} */ (deps),
      );
      await storagePut(
        { name: "draft", content: "a" },
        /** @type {*} */ (deps),
      );
      await asOwner("bob", deps);
      await storagePut(
        { name: "notes", content: "b" },
        /** @type {*} */ (deps),
      );

      await asOwner("alice", deps);
      const listed = await storageList({}, /** @type {*} */ (deps));
      assert.deepEqual(
        [...listed.keys].sort(),
        ["draft", "notes"],
        "the names must come back as the app wrote them — a caller that filters " +
          "this listing by its own prefix (query/persistence.py) matches nothing " +
          "if the owner prefix is still attached",
      );
    },
  );

  test(
    `${name}: remove cannot reach another owner's key`,
    { timeout: 5000 },
    async (t) => {
      t.after(resetStorageOwner);
      const deps = make();

      await asOwner("alice", deps);
      await storagePut(
        { name: "notes", content: "alice's" },
        /** @type {*} */ (deps),
      );

      await asOwner("bob", deps);
      await assert.rejects(
        () => storageRemove({ name: "notes" }, /** @type {*} */ (deps)),
        (err) => err.code === "not_found",
        "removing a name bob never wrote must not delete alice's",
      );

      await asOwner("alice", deps);
      const back = await storageGet({ name: "notes" }, /** @type {*} */ (deps));
      assert.equal(back.content, "alice's");
    },
  );

  test(
    `${name}: a key written before scoping stays readable`,
    { timeout: 5000 },
    async (t) => {
      t.after(resetStorageOwner);
      const deps = make();

      await storagePut(
        { name: "legacy", content: "from before" },
        /** @type {*} */ (deps),
      );

      await asOwner("alice", deps);
      await assert.rejects(
        () => storageGet({ name: "legacy" }, /** @type {*} */ (deps)),
        (err) => err.code === "not_found",
        "an owner's keyspace starts empty; the legacy data is not carried across",
      );

      await asOwner("", deps);
      const back = await storageGet(
        { name: "legacy" },
        /** @type {*} */ (deps),
      );
      assert.equal(
        back.content,
        "from before",
        "the default owner writes keys raw, so nothing already on disk moved",
      );
    },
  );

  test(
    `${name}: the default owner does not list a scoped owner's keys`,
    { timeout: 5000 },
    async (t) => {
      t.after(resetStorageOwner);
      const deps = make();

      await storagePut(
        { name: "legacy", content: "raw" },
        /** @type {*} */ (deps),
      );
      await asOwner("alice", deps);
      await storagePut(
        { name: "secret", content: "alice's" },
        /** @type {*} */ (deps),
      );

      await asOwner("", deps);
      const listed = await storageList({}, /** @type {*} */ (deps));
      assert.deepEqual(
        listed.keys,
        ["legacy"],
        "configure() back to the default must not expose a real owner's data",
      );
    },
  );
}

test(
  "configure echoes the owner it settled on",
  { timeout: 5000 },
  async (t) => {
    t.after(resetStorageOwner);
    const deps = { localStorage: memoryLocalStorage() };

    const scoped = await asOwner("alice", deps);
    assert.equal(scoped.owner, "alice");

    const reset = await storageConfigure({}, /** @type {*} */ (deps));
    assert.equal(
      reset.owner,
      "",
      "configure() with no arguments resets the owner, exactly as it resets the codec",
    );
  },
);

test(
  "the owner is armed even with no IndexedDB store",
  { timeout: 5000 },
  async (t) => {
    t.after(resetStorageOwner);
    const deps = { localStorage: memoryLocalStorage() };

    const settled = await asOwner("alice", deps);
    assert.equal(
      settled.active,
      "json",
      "the codec is only armed when a store exists — localStorage holds strings",
    );
    assert.equal(
      settled.owner,
      "alice",
      "the owner must NOT copy that guard: scoping the degraded profile is the " +
        "whole reason the derivation lives above the backend choice",
    );
  },
);

test(
  "a legacy name containing the separator is still readable by exact get",
  { timeout: 5000 },
  async (t) => {
    t.after(resetStorageOwner);
    const deps = { localStorage: memoryLocalStorage() };

    const odd = "we\u0000ird";
    await storagePut({ name: odd, content: "kept" }, /** @type {*} */ (deps));

    const back = await storageGet({ name: odd }, /** @type {*} */ (deps));
    assert.equal(back.content, "kept", "an exact lookup still finds it");

    const listed = await storageList({}, /** @type {*} */ (deps));
    assert.deepEqual(
      listed.keys,
      [],
      "but it is indistinguishable from a scoped key, so the default owner's " +
        "listing skips it — pinned rather than guarded, because rejecting a NUL " +
        "on every write costs a check for a name that has never occurred",
    );
  },
);
