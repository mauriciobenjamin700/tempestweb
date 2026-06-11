// Tests for client/router.js — URL -> navigate wire events.
import { test } from "node:test";
import assert from "node:assert/strict";
import { installRouter } from "../../client/router.js";

/** A mock Transport recording sendEvent calls. */
function mockTransport() {
  const events = [];
  return { events, onPatches() {}, sendEvent(e) { events.push(e); }, async close() {} };
}

/** A minimal fake window with a settable location.pathname and popstate listener. */
function fakeWindow(pathname) {
  const listeners = {};
  return {
    location: { pathname },
    addEventListener(type, fn) {
      (listeners[type] ??= []).push(fn);
    },
    removeEventListener(type, fn) {
      listeners[type] = (listeners[type] ?? []).filter((f) => f !== fn);
    },
    emit(type) {
      for (const fn of listeners[type] ?? []) fn();
    },
  };
}

test("installRouter reports the initial path as a navigate event", () => {
  const transport = mockTransport();
  const win = fakeWindow("/details");
  installRouter(transport, win);
  assert.deepEqual(transport.events, [
    { type: "navigate", key: "", payload: { path: "/details" } },
  ]);
});

test("popstate reports the new path", () => {
  const transport = mockTransport();
  const win = fakeWindow("/");
  installRouter(transport, win);
  win.location.pathname = "/about";
  win.emit("popstate");
  assert.equal(transport.events.length, 2);
  assert.deepEqual(transport.events[1], {
    type: "navigate",
    key: "",
    payload: { path: "/about" },
  });
});

test("dispose stops reporting popstate", () => {
  const transport = mockTransport();
  const win = fakeWindow("/");
  const router = installRouter(transport, win);
  router.dispose();
  win.location.pathname = "/x";
  win.emit("popstate");
  assert.equal(transport.events.length, 1); // only the initial report
});

test("installRouter is a no-op without a window", () => {
  const transport = mockTransport();
  const router = installRouter(transport, null);
  assert.equal(transport.events.length, 0);
  router.dispose();
});
