// sw-teardown.test.js — the worker a build emits when the SW is switched off.
//
// It only earns its place if it actually retires the caching worker: turning
// `[pwa] service_worker` off while leaving a registered worker alive would keep
// serving the app shell from a precache the deploy has moved past, and nothing
// in a later deploy could reach it (tempestweb#161).
//
// The module registers its listeners on `self` at import time, so the fakes go on
// globalThis before the dynamic import.
import { test, before } from "node:test";
import assert from "node:assert/strict";

/** @type {Map<string, (event: any) => void>} */
const listeners = new Map();
const deleted = [];
let unregistered = 0;
let claimed = 0;
const navigated = [];

before(async () => {
  globalThis.self = {
    addEventListener(type, handler) {
      listeners.set(type, handler);
    },
    skipWaiting() {},
    registration: {
      unregister() {
        unregistered += 1;
        return Promise.resolve(true);
      },
    },
    clients: {
      claim() {
        claimed += 1;
        return Promise.resolve();
      },
      matchAll() {
        return Promise.resolve([
          {
            url: "https://panel.example/dashboard",
            navigate(url) {
              navigated.push(url);
            },
          },
        ]);
      },
    },
  };
  globalThis.caches = {
    keys: () => Promise.resolve(["tw-abc123", "tw-def456", "runtime"]),
    delete: (name) => {
      deleted.push(name);
      return Promise.resolve(true);
    },
  };
  await import("../../client/sw/sw-teardown.js");
});

test("it registers the two lifecycle listeners a worker needs", () => {
  assert.ok(listeners.has("install"));
  assert.ok(listeners.has("activate"));
});

test("activating clears every cache and unregisters the worker", async () => {
  let waited = null;
  listeners.get("activate")({
    waitUntil(promise) {
      waited = promise;
    },
  });
  assert.ok(waited, "activate must hold the event open with waitUntil");
  await waited;

  assert.equal(claimed, 1, "it claims the clients the old worker controlled");
  assert.deepEqual(
    deleted.sort(),
    ["runtime", "tw-abc123", "tw-def456"],
    "every cache goes: the old precache name cannot be predicted from here",
  );
  assert.equal(unregistered, 1);
});

test("controlled pages are reloaded, so nobody keeps the stale shell", () => {
  assert.deepEqual(navigated, ["https://panel.example/dashboard"]);
});
