// Tests for client/offline/sync.js — P2 offline mutation queue + replay.
import { test } from "node:test";
import assert from "node:assert/strict";
import { IDBFactory } from "fake-indexeddb";
import { createOfflineStore } from "../../client/offline/store.js";
import {
  OfflineQueue,
  registerBackgroundSync,
  replayOnReconnect,
  QUEUE_TAG,
} from "../../client/offline/sync.js";

/** Build a queue backed by an isolated fake-indexeddb store. */
function freshQueue(send) {
  const store = createOfflineStore({
    databaseName: "tw-queue",
    tableName: "mutations",
    keyPath: "id",
    ownerField: "owner",
    indexedDB: new IDBFactory(),
  });
  return new OfflineQueue({ store, send, owner: "u1" });
}

test("enqueue persists a pending mutation with an idempotency key", async () => {
  const queue = freshQueue(async () => ({ ok: true }));
  const row = await queue.enqueue({ method: "POST", url: "/api/x", body: { a: 1 } });
  assert.equal(row.status, "pending");
  assert.ok(row.idempotencyKey, "auto-generated idempotency key");
  assert.equal(await queue.size(), 1);
});

test("enqueue honors an explicit idempotency key", async () => {
  const queue = freshQueue(async () => ({ ok: true }));
  const row = await queue.enqueue({
    method: "PUT",
    url: "/api/y",
    idempotencyKey: "fixed-key",
  });
  assert.equal(row.idempotencyKey, "fixed-key");
});

test("replay sends pending mutations in FIFO order and drains the queue", async () => {
  /** @type {string[]} */
  const seen = [];
  const queue = freshQueue(async (m) => {
    seen.push(m.url);
    return { ok: true };
  });
  await queue.enqueue({ method: "POST", url: "/a" });
  await queue.enqueue({ method: "POST", url: "/b" });
  await queue.enqueue({ method: "POST", url: "/c" });
  const out = await queue.replay();
  assert.deepEqual(seen, ["/a", "/b", "/c"]);
  assert.deepEqual(out, { sent: 3, remaining: 0 });
  assert.equal(await queue.size(), 0);
});

test("replay stops at the first failure preserving order, increments attempts", async () => {
  let calls = 0;
  const queue = freshQueue(async () => {
    calls += 1;
    return { ok: calls === 1 }; // first ok, second fails
  });
  await queue.enqueue({ method: "POST", url: "/a" });
  await queue.enqueue({ method: "POST", url: "/b" });
  await queue.enqueue({ method: "POST", url: "/c" });
  const out = await queue.replay();
  assert.equal(out.sent, 1);
  assert.equal(out.remaining, 2);
  const pending = await queue.pending();
  assert.equal(pending[0].url, "/b");
  assert.equal(pending[0].attempts, 1, "failed attempt counted");
});

test("replay treats a thrown send as a failure (no crash, stays queued)", async () => {
  const queue = freshQueue(async () => {
    throw new Error("network down");
  });
  await queue.enqueue({ method: "POST", url: "/a" });
  const out = await queue.replay();
  assert.deepEqual(out, { sent: 0, remaining: 1 });
});

test("replay is idempotent under re-entry (no double send while in flight)", async () => {
  let resolveSend;
  let sendCount = 0;
  const queue = freshQueue((m) => {
    sendCount += 1;
    return new Promise((r) => {
      resolveSend = () => r({ ok: true });
    });
  });
  await queue.enqueue({ method: "POST", url: "/a" });
  const first = queue.replay();
  const second = await queue.replay(); // should bail: already replaying
  assert.equal(second.sent, 0);
  resolveSend();
  await first;
  assert.equal(sendCount, 1, "only one in-flight send");
});

test("registerBackgroundSync returns false without a SyncManager", async () => {
  assert.equal(await registerBackgroundSync({}), false);
  assert.equal(await registerBackgroundSync({ sync: {} }), false);
});

test("registerBackgroundSync registers the queue tag when supported", async () => {
  let registered = null;
  const reg = { sync: { register: async (tag) => (registered = tag) } };
  assert.equal(await registerBackgroundSync(reg), true);
  assert.equal(registered, QUEUE_TAG);
});

test("replayOnReconnect replays immediately when online and on 'online' event", async () => {
  let replays = 0;
  /** @type {Record<string, Set<Function>>} */
  const listeners = {};
  const target = {
    addEventListener(t, fn) {
      (listeners[t] = listeners[t] || new Set()).add(fn);
    },
    removeEventListener(t, fn) {
      listeners[t]?.delete(fn);
    },
    dispatch(t) {
      for (const fn of listeners[t] || []) fn();
    },
  };
  const fakeQueue = { replay: async () => (replays += 1) };
  const teardown = replayOnReconnect(/** @type {any} */ (fakeQueue), {
    target,
    isOnline: () => true,
  });
  assert.equal(replays, 1, "immediate replay when online");
  target.dispatch("online");
  assert.equal(replays, 2);
  teardown();
  target.dispatch("online");
  assert.equal(replays, 2, "no replay after teardown");
});

test("replayOnReconnect does not replay while offline", async () => {
  let replays = 0;
  const fakeQueue = { replay: async () => (replays += 1) };
  replayOnReconnect(/** @type {any} */ (fakeQueue), {
    target: { addEventListener() {}, removeEventListener() {} },
    isOnline: () => false,
  });
  assert.equal(replays, 0);
});
