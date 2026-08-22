// Tests for client/media.js — viewport reporting shared by all three modes.
//
// The reporting itself is one line; what needs pinning is the pacing. `resize`
// fires continuously while a window edge is dragged, and in Mode B every report
// is a socket round-trip plus a rebuild, so a burst must collapse to one report
// and an unchanged viewport must report nothing.
import { test } from "node:test";
import assert from "node:assert/strict";
import { installMedia } from "../../client/media.js";

/**
 * A fake window with controllable size and a manual animation-frame queue.
 * @param {{width?: number, height?: number, dark?: boolean}} [initial]
 */
function fakeWindow(initial = {}) {
  const listeners = new Map();
  const frames = [];
  return {
    innerWidth: initial.width ?? 1280,
    innerHeight: initial.height ?? 800,
    devicePixelRatio: 2,
    dark: initial.dark ?? false,
    addEventListener(type, fn) {
      listeners.set(type, [...(listeners.get(type) ?? []), fn]);
    },
    removeEventListener(type, fn) {
      listeners.set(type, (listeners.get(type) ?? []).filter((f) => f !== fn));
    },
    matchMedia(query) {
      const self = this;
      return {
        get matches() {
          return query.includes("dark") ? self.dark : false;
        },
        addEventListener(_type, fn) {
          listeners.set("dark", [...(listeners.get("dark") ?? []), fn]);
        },
        removeEventListener(_type, fn) {
          listeners.set("dark", (listeners.get("dark") ?? []).filter((f) => f !== fn));
        },
      };
    },
    requestAnimationFrame(fn) {
      frames.push(fn);
      return frames.length;
    },
    cancelAnimationFrame(id) {
      frames[id - 1] = null;
    },
    /** Test helper: fire every registered listener of a type. */
    fire(type) {
      for (const fn of listeners.get(type) ?? []) fn();
    },
    /** Test helper: run the queued animation frames. */
    flush() {
      const queued = frames.splice(0, frames.length);
      for (const fn of queued) if (fn) fn();
    },
    /** Test helper: how many listeners are still attached. */
    count(type) {
      return (listeners.get(type) ?? []).length;
    },
  };
}

/** A transport that only records what was sent. */
function sink() {
  const events = [];
  return { events, sendEvent(event) { events.push(event); } };
}

test("reports the viewport on install, so the first render is responsive", () => {
  const win = fakeWindow({ width: 390, height: 844 });
  const transport = sink();

  installMedia(transport, win);

  assert.equal(transport.events.length, 1);
  assert.deepEqual(transport.events[0], {
    type: "media",
    key: "",
    payload: {
      width: 390,
      height: 844,
      device_pixel_ratio: 2,
      platform_dark_mode: false,
      orientation: "portrait",
    },
  });
});

test("a burst of resizes collapses to one report per frame", () => {
  const win = fakeWindow({ width: 1280, height: 800 });
  const transport = sink();
  installMedia(transport, win);

  for (let w = 1279; w > 1269; w -= 1) {
    win.innerWidth = w;
    win.fire("resize");
  }
  win.flush();

  assert.equal(transport.events.length, 2, "install + one coalesced report");
  assert.equal(transport.events[1].payload.width, 1270, "reports the final size");
});

test("a frame whose viewport did not change reports nothing", () => {
  const win = fakeWindow({ width: 1024, height: 768 });
  const transport = sink();
  installMedia(transport, win);

  win.fire("resize");
  win.flush();

  assert.equal(transport.events.length, 1, "install only");
});

test("orientation flips with the aspect ratio", () => {
  const win = fakeWindow({ width: 390, height: 844 });
  const transport = sink();
  installMedia(transport, win);

  win.innerWidth = 844;
  win.innerHeight = 390;
  win.fire("resize");
  win.flush();

  assert.equal(transport.events[1].payload.orientation, "landscape");
});

test("a dark-mode change reports without a resize", () => {
  const win = fakeWindow();
  const transport = sink();
  installMedia(transport, win);

  win.dark = true;
  win.fire("dark");
  win.flush();

  assert.equal(transport.events.length, 2);
  assert.equal(transport.events[1].payload.platform_dark_mode, true);
});

test("dispose drops the listeners and the pending frame", () => {
  const win = fakeWindow();
  const transport = sink();
  const media = installMedia(transport, win);

  win.innerWidth = 500;
  win.fire("resize");
  media.dispose();
  win.flush();

  assert.equal(transport.events.length, 1, "the pending frame was cancelled");
  assert.equal(win.count("resize"), 0);
  assert.equal(win.count("dark"), 0);
});

test("no window is a no-op, not a crash", () => {
  const transport = sink();
  const media = installMedia(transport, null);
  media.dispose();
  assert.equal(transport.events.length, 0);
});
