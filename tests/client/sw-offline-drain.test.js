// Tests for the service-worker queue drainer — client/sw/sw.js drainOfflineQueue
// (P2 §1: drain the durable offline queue with the tab closed).
import { test } from "node:test";
import assert from "node:assert/strict";
import { IDBFactory } from "fake-indexeddb";
import { drainOfflineQueue } from "../../client/sw/sw.js";
import { createOfflineStore } from "../../client/offline/store.js";
import { OfflineQueue } from "../../client/offline/sync.js";

/** A store over the worker's fixed db/table, backed by an isolated IDB. */
function seedStore(indexedDB) {
  return createOfflineStore({
    databaseName: "tempestweb-offline",
    tableName: "mutations",
    keyPath: "id",
    ownerField: "owner",
    indexedDB,
  });
}

/** A pending queue row with sensible defaults. */
function row(overrides) {
  return {
    id: overrides.id,
    owner: overrides.owner ?? "default",
    idempotencyKey: overrides.idempotencyKey ?? `k-${overrides.id}`,
    method: overrides.method ?? "POST",
    url: overrides.url,
    body: overrides.body ?? null,
    seq: overrides.seq ?? 1,
    attempts: 0,
    status: overrides.status ?? "pending",
  };
}

test("store.listAll returns every row across owners", async () => {
  const idb = new IDBFactory();
  const store = seedStore(idb);
  await store.put(row({ id: "1", owner: "u1", url: "/a" }));
  await store.put(row({ id: "2", owner: "u2", url: "/b" }));
  const all = await store.listAll();
  assert.equal(all.length, 2);
});

test("drainOfflineQueue replays pending mutations across every owner", async () => {
  const idb = new IDBFactory();
  const store = seedStore(idb);
  await store.put(row({ id: "1", owner: "u1", url: "/a", seq: 1 }));
  await store.put(row({ id: "2", owner: "u1", url: "/b", seq: 2 }));
  await store.put(row({ id: "3", owner: "u2", url: "/c", seq: 3 }));

  const seen = [];
  const send = async (m) => {
    seen.push(m.url);
    return { ok: true, status: 200 };
  };
  const out = await drainOfflineQueue({
    createOfflineStore,
    OfflineQueue,
    indexedDB: idb,
    send,
  });
  assert.equal(out.sent, 3);
  assert.equal(out.owners, 2);
  assert.deepEqual(seen.sort(), ["/a", "/b", "/c"]);
  assert.equal((await store.listAll()).length, 0, "queue drained");
});

test("drainOfflineQueue honors the shared policy: 409 parks, 400 dead-letters", async () => {
  const idb = new IDBFactory();
  const store = seedStore(idb);
  await store.put(row({ id: "1", owner: "u1", url: "/conflict", seq: 1 }));
  await store.put(row({ id: "2", owner: "u1", url: "/bad", seq: 2 }));
  await store.put(row({ id: "3", owner: "u1", url: "/ok", seq: 3 }));

  const send = async (m) => {
    if (m.url === "/conflict") return { ok: false, status: 409 };
    if (m.url === "/bad") return { ok: false, status: 400 };
    return { ok: true, status: 200 };
  };
  const out = await drainOfflineQueue({
    createOfflineStore,
    OfflineQueue,
    indexedDB: idb,
    send,
  });
  assert.equal(out.sent, 1, "only /ok accepted");
  const all = await store.listAll();
  const byUrl = Object.fromEntries(all.map((r) => [r.url, r.status]));
  assert.equal(byUrl["/conflict"], "conflict");
  assert.equal(byUrl["/bad"], "failed");
  assert.equal(byUrl["/ok"], undefined, "accepted row removed");
});

test("drainOfflineQueue is a no-op on an empty queue", async () => {
  const idb = new IDBFactory();
  const out = await drainOfflineQueue({
    createOfflineStore,
    OfflineQueue,
    indexedDB: idb,
    send: async () => assert.fail("nothing to send"),
  });
  assert.deepEqual(out, { sent: 0, owners: 0 });
});
