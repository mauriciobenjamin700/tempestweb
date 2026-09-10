// Tests for client/native/sync.js — the configurable sync capability.
//
// Drives the handlers through the real dispatch router with an injected sync
// controller (deps.syncController) so no IndexedDB / network is needed.
import { test } from "node:test";
import assert from "node:assert/strict";
import { IDBFactory } from "fake-indexeddb";
import { dispatch, subscribeDispatch } from "../../client/native/index.js";

/** A fake sync controller with a controllable observable state. */
function fakeController(initial = {}) {
  let state = {
    phase: "idle",
    online: true,
    pending: 0,
    lastSyncedAt: null,
    lastSummary: null,
    error: null,
    ...initial,
  };
  const subs = new Set();
  return {
    syncNow: async () => {
      state = { ...state, phase: "idle", lastSyncedAt: 111, pending: 0 };
      for (const fn of subs) fn(state);
      return { sent: 2, remaining: 0, failed: 0, conflicts: 0, applied: 3 };
    },
    refreshPending: async () => {},
    status: {
      get: () => state,
      subscribe: (fn) => {
        subs.add(fn);
        fn(state);
        return () => subs.delete(fn);
      },
    },
    _emit: (patch) => {
      state = { ...state, ...patch };
      for (const fn of subs) fn(state);
    },
  };
}

/** Configure a source with an injected controller, returning that controller. */
async function configure(name, controller) {
  await dispatch(
    { call_id: "1", capability: "sync.configure", args: { name, url: "/api/x", database: "d", table: "t" } },
    { syncController: controller },
  );
  return controller;
}

test("sync.configure registers a source and sync.now runs it", async () => {
  const ctl = await configure("notes", fakeController());
  const res = await dispatch({ call_id: "2", capability: "sync.now", args: { name: "notes" } }, {});
  assert.equal(res.ok, true);
  assert.deepEqual(res.value, { sent: 2, remaining: 0, failed: 0, conflicts: 0, applied: 3 });
  void ctl;
});

test("sync.status returns the snake_case wire state", async () => {
  await configure("s1", fakeController({ pending: 4, phase: "syncing" }));
  const res = await dispatch({ call_id: "3", capability: "sync.status", args: { name: "s1" } }, {});
  assert.equal(res.ok, true);
  assert.equal(res.value.pending, 4);
  assert.equal(res.value.phase, "syncing");
  assert.ok("last_synced_at" in res.value, "camelCase mapped to snake_case");
  assert.ok("last_summary" in res.value);
});

test("sync.now on an unconfigured source reports unavailable", async () => {
  const res = await dispatch({ call_id: "4", capability: "sync.now", args: { name: "nope" } }, {});
  assert.equal(res.ok, false);
  assert.match(String(res.error || res.message || ""), /not configured|unavailable/i);
});

test("sync.watch streams state changes (snake_case) until unsubscribed", async () => {
  const ctl = await configure("w1", fakeController({ pending: 1 }));
  const events = [];
  subscribeDispatch(
    { sub_id: "sub-1", capability: "sync.watch", args: { name: "w1" } },
    (payload) => events.push(payload),
    {},
  );
  assert.equal(events.length, 1, "emits current state immediately");
  assert.equal(events[0].event.pending, 1);
  ctl._emit({ pending: 0, phase: "idle" });
  assert.equal(events.length, 2);
  assert.equal(events[1].event.pending, 0);
  assert.ok("last_synced_at" in events[1].event);
});

// --- the real pull path ----------------------------------------------------
//
// Every test above injects `deps.syncController`, so `buildSource`'s own
// `pullPage` — the code that reads the HTTP response — never runs. That gap is
// why it could read a field the response did not carry and still ship green.

test("sync.now: the real pullPage reads rows off the HTTP response", async () => {
  const deps = {
    indexedDB: new IDBFactory(),
    fetch: async () => ({
      status: 200,
      ok: true,
      headers: { get: () => "application/json" },
      text: async () =>
        JSON.stringify({
          rows: [{ id: "r1", owner: "me", title: "pulled" }],
          next_cursor: null,
          server_time: "2026-01-01T00:00:00Z",
        }),
    }),
  };
  await dispatch(
    {
      call_id: "rp1",
      capability: "sync.configure",
      args: {
        name: "real-pull",
        url: "/api/sync",
        database: "tw-real-pull",
        table: "rows",
      },
    },
    deps,
  );
  const res = await dispatch(
    { call_id: "rp2", capability: "sync.now", args: { name: "real-pull" } },
    deps,
  );
  assert.equal(res.ok, true);
  assert.equal(res.value.applied, 1);
});
