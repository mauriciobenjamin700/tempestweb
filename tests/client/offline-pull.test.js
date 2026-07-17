// Tests for client/offline/pull.js — P2 read-side delta-sync (pull).
import { test } from "node:test";
import assert from "node:assert/strict";
import { IDBFactory } from "fake-indexeddb";
import { createOfflineStore } from "../../client/offline/store.js";
import { createPull, createWatermark, mergeRemoteInto } from "../../client/offline/pull.js";

/** An in-memory Storage double. */
function fakeStorage() {
  const map = new Map();
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    removeItem: (k) => map.delete(k),
  };
}

/** An owner-scoped store over an isolated fake-indexeddb. */
function freshStore() {
  return createOfflineStore({
    databaseName: "tw-pull",
    tableName: "rows",
    keyPath: "id",
    ownerField: "owner",
    indexedDB: new IDBFactory(),
  });
}

test("createWatermark persists via storage and falls back to memory", () => {
  const wm = createWatermark("tw:wm", fakeStorage());
  assert.equal(wm.get(), null);
  wm.set("2026-01-01T00:00:00Z");
  assert.equal(wm.get(), "2026-01-01T00:00:00Z");

  const mem = createWatermark("tw:wm", null);
  mem.set("x");
  assert.equal(mem.get(), "x", "in-memory fallback without storage");
});

test("createPull follows the cursor, applies rows in order, advances watermark", async () => {
  const pages = [
    { rows: [{ id: "a" }, { id: "b" }], nextCursor: "c1", serverTime: "t1" },
    { rows: [{ id: "c" }], nextCursor: null, serverTime: "t2" },
  ];
  const seenSince = [];
  const applied = [];
  const wm = createWatermark("k", fakeStorage());
  wm.set("t0");
  const pull = createPull({
    pullPage: async (since, cursor) => {
      seenSince.push([since, cursor]);
      return pages.shift();
    },
    applyRemote: (row) => {
      applied.push(row.id);
    },
    watermark: wm,
  });
  const out = await pull.pull();
  assert.deepEqual(applied, ["a", "b", "c"], "rows applied in page+order");
  assert.deepEqual(out, { applied: 3, pages: 2 });
  assert.equal(seenSince[0][0], "t0", "first page reads from the watermark");
  assert.equal(seenSince[1][1], "c1", "second page follows nextCursor");
  assert.equal(wm.get(), "t2", "watermark advanced to the latest serverTime");
});

test("createPull is single-flight (concurrent pull bails)", async () => {
  let release;
  const gate = new Promise((r) => (release = r));
  const wm = createWatermark("k", fakeStorage());
  const pull = createPull({
    pullPage: async () => {
      await gate;
      return { rows: [{ id: "a" }], nextCursor: null, serverTime: "t1" };
    },
    applyRemote: () => {},
    watermark: wm,
  });
  const first = pull.pull();
  const second = await pull.pull();
  assert.deepEqual(second, { applied: 0, pages: 0, alreadyRunning: true });
  release();
  const firstOut = await first;
  assert.equal(firstOut.applied, 1);
});

test("createPull leaves the watermark untouched when no serverTime is returned", async () => {
  const wm = createWatermark("k", fakeStorage());
  wm.set("t0");
  const pull = createPull({
    pullPage: async () => ({ rows: [{ id: "a" }], nextCursor: null }),
    applyRemote: () => {},
    watermark: wm,
  });
  await pull.pull();
  assert.equal(wm.get(), "t0", "watermark unchanged without serverTime");
});

test("mergeRemoteInto upserts, deletes tombstones, and guards pending newer edits", async () => {
  const store = freshStore();
  await store.put({ id: "1", owner: "u", updated_at: 5, text: "local" });
  await store.put({ id: "2", owner: "u", text: "to-delete" });

  const pending = new Set(["1"]);
  const merge = mergeRemoteInto(store, {
    isPendingLocally: (key) => pending.has(key),
  });

  // Pending local (updated_at 5) is newer than the server row (3): keep local.
  await merge({ id: "1", owner: "u", updated_at: 3, text: "server-old" });
  assert.equal((await store.get("1")).text, "local", "pending newer local kept");

  // Tombstone deletes.
  await merge({ id: "2", owner: "u", deleted: true });
  assert.equal(await store.get("2"), null, "tombstone deleted the row");

  // Fresh remote row is upserted.
  await merge({ id: "3", owner: "u", updated_at: 9, text: "new" });
  assert.equal((await store.get("3")).text, "new", "new remote row inserted");
});

test("mergeRemoteInto overwrites a non-pending local row (last-write-wins)", async () => {
  const store = freshStore();
  await store.put({ id: "1", owner: "u", updated_at: 5, text: "local" });
  const merge = mergeRemoteInto(store); // isPendingLocally defaults to false
  await merge({ id: "1", owner: "u", updated_at: 3, text: "server" });
  assert.equal((await store.get("1")).text, "server", "server wins when not pending");
});
