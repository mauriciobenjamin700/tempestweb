// Tests for client/offline/sync-status.js — P2 observable sync state + controller.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createSyncStatus, createSyncController } from "../../client/offline/sync-status.js";

/** An event target the test can dispatch online/offline on. */
function fakeTarget() {
  const listeners = {};
  return {
    addEventListener(t, fn) {
      (listeners[t] ||= new Set()).add(fn);
    },
    removeEventListener(t, fn) {
      listeners[t]?.delete(fn);
    },
    fire(t) {
      for (const fn of listeners[t] || []) fn();
    },
    count(t) {
      return (listeners[t] || new Set()).size;
    },
  };
}

test("createSyncStatus notifies on subscribe and on change", () => {
  const store = createSyncStatus();
  const seen = [];
  const unsub = store.subscribe((s) => seen.push(s.phase));
  assert.deepEqual(seen, ["idle"], "fires immediately with current state");
  store.set({ phase: "syncing" });
  assert.deepEqual(seen, ["idle", "syncing"]);
  unsub();
  store.set({ phase: "idle" });
  assert.deepEqual(seen, ["idle", "syncing"], "no more after unsubscribe");
});

test("syncNow replays the queue, pulls, and records a summary", async () => {
  const queue = { replay: async () => ({ sent: 2, remaining: 1, failed: 0, conflicts: 0 }) };
  const pull = { pull: async () => ({ applied: 3 }) };
  const ctl = createSyncController({ queue, pull, now: () => 1234 });
  const summary = await ctl.syncNow();
  assert.deepEqual(summary, { sent: 2, remaining: 1, failed: 0, conflicts: 0, applied: 3 });
  const s = ctl.status.get();
  assert.equal(s.phase, "idle");
  assert.equal(s.lastSyncedAt, 1234);
  assert.equal(s.pending, 1);
  assert.equal(s.error, null);
});

test("syncNow is single-flight", async () => {
  let release;
  const gate = new Promise((r) => (release = r));
  let replays = 0;
  const queue = {
    replay: async () => {
      replays += 1;
      await gate;
      return { sent: 0, remaining: 0, failed: 0, conflicts: 0 };
    },
  };
  const ctl = createSyncController({ queue });
  const first = ctl.syncNow();
  await ctl.syncNow();
  assert.equal(replays, 1, "second call bailed while syncing");
  release();
  await first;
});

test("syncNow records an error and returns null on failure", async () => {
  const queue = {
    replay: async () => {
      throw new Error("boom");
    },
  };
  const ctl = createSyncController({ queue });
  const out = await ctl.syncNow();
  assert.equal(out, null);
  assert.equal(ctl.status.get().phase, "error");
  assert.equal(ctl.status.get().error, "boom");
});

test("refreshPending mirrors the queue size into the store", async () => {
  const ctl = createSyncController({ queue: { size: async () => 7, replay: async () => ({}) } });
  await ctl.refreshPending();
  assert.equal(ctl.status.get().pending, 7);
});

test("start reflects connectivity, flushes on boot and on reconnect", async () => {
  const target = fakeTarget();
  let replays = 0;
  const queue = {
    replay: async () => {
      replays += 1;
      return { sent: 0, remaining: 0, failed: 0, conflicts: 0 };
    },
  };
  const ctl = createSyncController({ queue });
  const teardown = ctl.start({ target, isOnline: () => true });
  assert.equal(ctl.status.get().online, true);
  await Promise.resolve();
  assert.equal(replays, 1, "boot flush");

  target.fire("online");
  await Promise.resolve();
  assert.equal(replays, 2, "flush on reconnect");

  target.fire("offline");
  assert.equal(ctl.status.get().online, false);

  teardown();
  assert.equal(target.count("online"), 0, "listeners removed");
});
