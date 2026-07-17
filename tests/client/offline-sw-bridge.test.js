// Tests for client/offline/sw-bridge.js — P2 SW→page message routing.
import { test } from "node:test";
import assert from "node:assert/strict";
import { installSyncBridge, SW_MESSAGES } from "../../client/offline/sw-bridge.js";

/** A ServiceWorkerContainer double the test can post messages through. */
function fakeContainer() {
  const listeners = new Set();
  return {
    addEventListener(type, fn) {
      if (type === "message") listeners.add(fn);
    },
    removeEventListener(type, fn) {
      if (type === "message") listeners.delete(fn);
    },
    post(data) {
      for (const fn of listeners) fn({ data });
    },
    count() {
      return listeners.size;
    },
  };
}

test("installSyncBridge dispatches known message types to handlers", () => {
  const container = fakeContainer();
  const calls = [];
  installSyncBridge(
    {
      [SW_MESSAGES.PULL]: () => calls.push("pull"),
      [SW_MESSAGES.DRAINED]: (d) => calls.push(`drained:${d.remaining}`),
    },
    { container },
  );
  container.post({ type: SW_MESSAGES.PULL });
  container.post({ type: SW_MESSAGES.DRAINED, remaining: 2 });
  assert.deepEqual(calls, ["pull", "drained:2"]);
});

test("installSyncBridge ignores unknown types and malformed messages", () => {
  const container = fakeContainer();
  let hits = 0;
  installSyncBridge({ [SW_MESSAGES.PULL]: () => (hits += 1) }, { container });
  container.post({ type: "SOMETHING_ELSE" });
  container.post(null);
  container.post({ noType: true });
  assert.equal(hits, 0);
});

test("installSyncBridge teardown removes the listener", () => {
  const container = fakeContainer();
  let hits = 0;
  const teardown = installSyncBridge(
    { [SW_MESSAGES.PULL]: () => (hits += 1) },
    { container },
  );
  teardown();
  assert.equal(container.count(), 0);
  container.post({ type: SW_MESSAGES.PULL });
  assert.equal(hits, 0);
});

test("installSyncBridge is a no-op without a service worker container", () => {
  const teardown = installSyncBridge({}, { container: null });
  assert.equal(typeof teardown, "function");
  teardown();
});
