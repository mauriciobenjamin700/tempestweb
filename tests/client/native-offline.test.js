// Tests for client/native/offline.js — the offline-queue native capability.
//
// Drives the handlers through the real dispatch router with an injected queue
// (deps.offlineQueue) so no IndexedDB is needed, asserting the wire shapes the
// Python `Mutation` / `ReplayResult` models validate.
import { test } from "node:test";
import assert from "node:assert/strict";
import { IDBFactory } from "fake-indexeddb";
import { dispatch } from "../../client/native/index.js";
import { createOfflineStore } from "../../client/offline/store.js";
import { OfflineQueue } from "../../client/offline/sync.js";

/** A queue backed by an isolated fake-indexeddb store + a scripted sender. */
function freshQueue(send) {
  const store = createOfflineStore({
    databaseName: "tw-native-offline",
    tableName: "mutations",
    keyPath: "id",
    ownerField: "owner",
    indexedDB: new IDBFactory(),
  });
  return new OfflineQueue({ store, send, owner: "default" });
}

/** Run a capability through the router with an injected queue. */
async function callCap(capability, args, queue) {
  return dispatch({ call_id: "1", capability, args }, { offlineQueue: queue });
}

test("offline.enqueue persists a pending mutation and returns the wire shape", async () => {
  const queue = freshQueue(async () => ({ ok: false })); // stay offline
  const res = await callCap(
    "offline.enqueue",
    { method: "POST", url: "/api/todos", body: { title: "x" } },
    queue,
  );
  assert.equal(res.ok, true);
  assert.equal(res.value.method, "POST");
  assert.equal(res.value.url, "/api/todos");
  assert.equal(res.value.status, "pending");
  assert.ok(res.value.idempotency_key, "carries an idempotency key");
});

test("offline.size and offline.pending reflect the queue", async () => {
  const queue = freshQueue(async () => ({ ok: false }));
  await callCap("offline.enqueue", { method: "POST", url: "/a" }, queue);
  await callCap("offline.enqueue", { method: "PUT", url: "/b" }, queue);
  const size = await callCap("offline.size", {}, queue);
  assert.equal(size.value.size, 2);
  const pending = await callCap("offline.pending", {}, queue);
  assert.equal(pending.value.mutations.length, 2);
  // FIFO: first enqueued is first out.
  assert.equal(pending.value.mutations[0].url, "/a");
});

test("offline.replay drains the queue when the sender accepts", async () => {
  const sent = [];
  const queue = freshQueue(async (m) => {
    sent.push(m.url);
    return { ok: true, status: 200 };
  });
  await callCap("offline.enqueue", { method: "POST", url: "/a" }, queue);
  await callCap("offline.enqueue", { method: "POST", url: "/b" }, queue);
  const res = await callCap("offline.replay", {}, queue);
  assert.equal(res.value.sent, 2);
  assert.equal(res.value.remaining, 0);
  assert.deepEqual(sent, ["/a", "/b"]);
});

test("offline.replay stops at the first failure, preserving FIFO", async () => {
  let calls = 0;
  const queue = freshQueue(async () => {
    calls += 1;
    return { ok: calls === 1, status: calls === 1 ? 200 : 503 };
  });
  await callCap("offline.enqueue", { method: "POST", url: "/a" }, queue);
  await callCap("offline.enqueue", { method: "POST", url: "/b" }, queue);
  const res = await callCap("offline.replay", {}, queue);
  assert.equal(res.value.sent, 1);
  assert.equal(res.value.remaining, 1);
  assert.equal(res.value.failed, 0);
  assert.equal(res.value.conflicts, 0);
});

test("offline.failed lists dead-lettered mutations (permanent 4xx)", async () => {
  const queue = freshQueue(async () => ({ ok: false, status: 400 }));
  await callCap("offline.enqueue", { method: "POST", url: "/bad" }, queue);
  const replay = await callCap("offline.replay", {}, queue);
  assert.equal(replay.value.failed, 1);
  assert.equal(replay.value.remaining, 0);
  const failed = await callCap("offline.failed", {}, queue);
  assert.equal(failed.value.mutations.length, 1);
  assert.equal(failed.value.mutations[0].url, "/bad");
  assert.equal(failed.value.mutations[0].status, "failed");
});

test("offline.conflicts lists 409-parked mutations without blocking", async () => {
  const queue = freshQueue(async (m) =>
    m.url === "/c" ? { ok: false, status: 409 } : { ok: true, status: 200 },
  );
  await callCap("offline.enqueue", { method: "PUT", url: "/c" }, queue);
  await callCap("offline.enqueue", { method: "POST", url: "/ok" }, queue);
  const replay = await callCap("offline.replay", {}, queue);
  assert.equal(replay.value.sent, 1);
  assert.equal(replay.value.conflicts, 1);
  const conflicts = await callCap("offline.conflicts", {}, queue);
  assert.equal(conflicts.value.mutations.length, 1);
  assert.equal(conflicts.value.mutations[0].url, "/c");
  assert.equal(conflicts.value.mutations[0].status, "conflict");
});

test("building the real queue requests durable storage (best-effort)", async () => {
  let persisted = false;
  const navigator = {
    storage: {
      persist: async () => {
        persisted = true;
        return true;
      },
      persisted: async () => false,
    },
  };
  const res = await dispatch(
    { call_id: "1", capability: "offline.enqueue", args: { method: "POST", url: "/x" } },
    { indexedDB: new IDBFactory(), navigator },
  );
  assert.equal(res.ok, true);
  assert.equal(persisted, true, "navigator.storage.persist() was requested");
});
