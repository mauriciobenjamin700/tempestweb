// Tests for client/offline/store.js — P2 owner-scoped IndexedDB store.
import { test } from "node:test";
import assert from "node:assert/strict";
import { IDBFactory } from "fake-indexeddb";
import { createOfflineStore, persistStorage } from "../../client/offline/store.js";

/** Build a fresh store backed by an isolated fake-indexeddb instance. */
function freshStore(extra = {}) {
  return createOfflineStore({
    databaseName: "tw-test",
    tableName: "drafts",
    keyPath: "id",
    ownerField: "owner",
    indexedDB: new IDBFactory(),
    ...extra,
  });
}

test("put + get round-trips a record", async () => {
  const store = freshStore();
  await store.put({ id: "a", owner: "u1", title: "hello" });
  const got = await store.get("a");
  assert.deepEqual(got, { id: "a", owner: "u1", title: "hello" });
  store.close();
});

test("get returns null when absent", async () => {
  const store = freshStore();
  assert.equal(await store.get("nope"), null);
  store.close();
});

test("list is owner-scoped and returns [] for unknown owner", async () => {
  const store = freshStore();
  await store.bulkPut([
    { id: "a", owner: "u1", n: 1 },
    { id: "b", owner: "u2", n: 2 },
    { id: "c", owner: "u1", n: 3 },
  ]);
  const u1 = await store.list("u1");
  assert.deepEqual(u1.map((r) => r.id).sort(), ["a", "c"]);
  assert.deepEqual(await store.list("ghost"), []);
  store.close();
});

test("list sorts by orderBy, reverse and limit", async () => {
  const store = freshStore();
  await store.bulkPut([
    { id: "a", owner: "u1", n: 3 },
    { id: "b", owner: "u1", n: 1 },
    { id: "c", owner: "u1", n: 2 },
  ]);
  const asc = await store.list("u1", { orderBy: "n" });
  assert.deepEqual(asc.map((r) => r.n), [1, 2, 3]);
  const desc = await store.list("u1", { orderBy: "n", reverse: true });
  assert.deepEqual(desc.map((r) => r.n), [3, 2, 1]);
  const top = await store.list("u1", { orderBy: "n", limit: 2 });
  assert.deepEqual(top.map((r) => r.n), [1, 2]);
  store.close();
});

test("update merges a patch; returns null when absent", async () => {
  const store = freshStore();
  await store.put({ id: "a", owner: "u1", title: "old", n: 1 });
  const updated = await store.update("a", { title: "new" });
  assert.deepEqual(updated, { id: "a", owner: "u1", title: "new", n: 1 });
  assert.equal(await store.update("missing", { x: 1 }), null);
  store.close();
});

test("updateMany patches every owner row", async () => {
  const store = freshStore();
  await store.bulkPut([
    { id: "a", owner: "u1", seen: false },
    { id: "b", owner: "u1", seen: false },
    { id: "c", owner: "u2", seen: false },
  ]);
  const n = await store.updateMany("u1", { seen: true });
  assert.equal(n, 2);
  assert.equal((await store.get("a")).seen, true);
  assert.equal((await store.get("c")).seen, false);
  store.close();
});

test("delete and clear remove rows; count reflects owners", async () => {
  const store = freshStore();
  await store.bulkPut([
    { id: "a", owner: "u1" },
    { id: "b", owner: "u1" },
    { id: "c", owner: "u2" },
  ]);
  assert.equal(await store.count(), 3);
  assert.equal(await store.count("u1"), 2);
  await store.delete("a");
  assert.equal(await store.count("u1"), 1);
  const cleared = await store.clear("u1");
  assert.equal(cleared, 1);
  assert.equal(await store.count("u1"), 0);
  assert.equal(await store.count("u2"), 1);
  store.close();
});

test("constructor rejects missing config", () => {
  assert.throws(() => createOfflineStore({ tableName: "x" }), /databaseName/);
});

test("persistStorage returns false without a Storage API", async () => {
  assert.equal(await persistStorage({}), false);
  assert.equal(await persistStorage({ storage: {} }), false);
});

test("persistStorage delegates to navigator.storage.persist", async () => {
  let called = false;
  const nav = {
    storage: {
      persisted: async () => false,
      persist: async () => {
        called = true;
        return true;
      },
    },
  };
  assert.equal(await persistStorage(nav), true);
  assert.equal(called, true);
});

test("persistStorage short-circuits when already persisted", async () => {
  let persistCalls = 0;
  const nav = {
    storage: {
      persisted: async () => true,
      persist: async () => {
        persistCalls += 1;
        return true;
      },
    },
  };
  assert.equal(await persistStorage(nav), true);
  assert.equal(persistCalls, 0);
});
