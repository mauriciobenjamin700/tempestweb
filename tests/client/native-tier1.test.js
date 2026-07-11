// Tests for the Tier-1 native capabilities added to client/native/*.
//
// Web APIs are injected as `deps` (fake navigator/document/screen), so these run
// under node:test with no real browser. Each capability is exercised for its
// success shape and for the CapabilityError code it raises when the API is absent.

import { test } from "node:test";
import assert from "node:assert/strict";

import { dispatch } from "../../client/native/index.js";

/** Build a native_call envelope. */
function call(capability, args = {}, callId = "c1") {
  return { kind: "native_call", call_id: callId, capability, args };
}

// --- vibration -------------------------------------------------------------

test("vibration.vibrate: forwards the pattern to navigator.vibrate", async () => {
  let seen;
  const navigator = { vibrate: (p) => (seen = p) };
  const res = await dispatch(call("vibration.vibrate", { pattern: [100, 30, 100] }), { navigator });
  assert.equal(res.ok, true);
  assert.deepEqual(res.value, {});
  assert.deepEqual(seen, [100, 30, 100]);
});

test("vibration.vibrate: unavailable when navigator.vibrate is missing", async () => {
  const res = await dispatch(call("vibration.vibrate", { pattern: 50 }), { navigator: {} });
  assert.equal(res.ok, false);
  assert.equal(res.error, "unavailable");
});

// --- badge -----------------------------------------------------------------

test("badge.set: passes the count through", async () => {
  const seen = [];
  const navigator = { setAppBadge: async (n) => seen.push(n) };
  const res = await dispatch(call("badge.set", { count: 5 }), { navigator });
  assert.equal(res.ok, true);
  assert.deepEqual(res.value, {});
  assert.deepEqual(seen, [5]);
});

test("badge.set: calls setAppBadge with no argument when count is null", async () => {
  let argc = -1;
  const navigator = {
    setAppBadge: async (...args) => {
      argc = args.length;
    },
  };
  const res = await dispatch(call("badge.set", { count: null }), { navigator });
  assert.equal(res.ok, true);
  assert.equal(argc, 0);
});

test("badge.set: unavailable when the App Badging API is missing", async () => {
  const res = await dispatch(call("badge.set", { count: 1 }), { navigator: {} });
  assert.equal(res.ok, false);
  assert.equal(res.error, "unavailable");
});

test("badge.clear: clears the badge", async () => {
  let cleared = 0;
  const navigator = { clearAppBadge: async () => (cleared += 1) };
  const res = await dispatch(call("badge.clear"), { navigator });
  assert.equal(res.ok, true);
  assert.equal(cleared, 1);
});

test("badge.clear: unavailable when the API is missing", async () => {
  const res = await dispatch(call("badge.clear"), { navigator: {} });
  assert.equal(res.ok, false);
  assert.equal(res.error, "unavailable");
});

// --- wakelock --------------------------------------------------------------

test("wakelock.request then release round-trips a sentinel by id", async () => {
  let released = 0;
  const sentinel = { release: async () => (released += 1) };
  const navigator = { wakeLock: { request: async (type) => {
    assert.equal(type, "screen");
    return sentinel;
  } } };
  const req = await dispatch(call("wakelock.request"), { navigator });
  assert.equal(req.ok, true);
  assert.equal(typeof req.value.id, "string");

  const rel = await dispatch(call("wakelock.release", { id: req.value.id }), { navigator });
  assert.equal(rel.ok, true);
  assert.deepEqual(rel.value, {});
  assert.equal(released, 1);
});

test("wakelock.request: unavailable when the Wake Lock API is missing", async () => {
  const res = await dispatch(call("wakelock.request"), { navigator: {} });
  assert.equal(res.ok, false);
  assert.equal(res.error, "unavailable");
});

test("wakelock.release: not_found for an unknown id", async () => {
  const res = await dispatch(call("wakelock.release", { id: "wakelock-does-not-exist" }), {});
  assert.equal(res.ok, false);
  assert.equal(res.error, "not_found");
});

// --- fullscreen ------------------------------------------------------------

test("fullscreen.enter: requests fullscreen on the document element", async () => {
  let entered = 0;
  const document = { documentElement: { requestFullscreen: async () => (entered += 1) } };
  const res = await dispatch(call("fullscreen.enter"), { document });
  assert.equal(res.ok, true);
  assert.deepEqual(res.value, { active: true });
  assert.equal(entered, 1);
});

test("fullscreen.enter: unavailable when requestFullscreen is missing", async () => {
  const res = await dispatch(call("fullscreen.enter"), { document: { documentElement: {} } });
  assert.equal(res.ok, false);
  assert.equal(res.error, "unavailable");
});

test("fullscreen.exit: exits fullscreen", async () => {
  let exited = 0;
  const document = { exitFullscreen: async () => (exited += 1) };
  const res = await dispatch(call("fullscreen.exit"), { document });
  assert.equal(res.ok, true);
  assert.deepEqual(res.value, { active: false });
  assert.equal(exited, 1);
});

test("fullscreen.exit: unavailable when exitFullscreen is missing", async () => {
  const res = await dispatch(call("fullscreen.exit"), { document: {} });
  assert.equal(res.ok, false);
  assert.equal(res.error, "unavailable");
});

test("fullscreen.state: reports the current fullscreen element", async () => {
  const active = await dispatch(call("fullscreen.state"), { document: { fullscreenElement: {} } });
  assert.deepEqual(active.value, { active: true });
  const inactive = await dispatch(call("fullscreen.state"), { document: { fullscreenElement: null } });
  assert.deepEqual(inactive.value, { active: false });
});

// --- visibility ------------------------------------------------------------

test("visibility.state: reports state and hidden", async () => {
  const res = await dispatch(call("visibility.state"), {
    document: { visibilityState: "hidden", hidden: true },
  });
  assert.equal(res.ok, true);
  assert.deepEqual(res.value, { state: "hidden", hidden: true });
});

test("visibility.state: degrades to visible without a document", async () => {
  const res = await dispatch(call("visibility.state"), {});
  assert.equal(res.ok, true);
  assert.deepEqual(res.value, { state: "visible", hidden: false });
});

// --- orientation -----------------------------------------------------------

test("orientation.lock: locks to a kind", async () => {
  let locked;
  const screen = { orientation: { lock: async (k) => (locked = k), unlock: () => {} } };
  const res = await dispatch(call("orientation.lock", { kind: "portrait" }), { screen });
  assert.equal(res.ok, true);
  assert.deepEqual(res.value, { locked: true });
  assert.equal(locked, "portrait");
});

test("orientation.lock: unavailable when the API is missing", async () => {
  const res = await dispatch(call("orientation.lock", { kind: "portrait" }), { screen: {} });
  assert.equal(res.ok, false);
  assert.equal(res.error, "unavailable");
});

test("orientation.lock: not_allowed when the lock rejects", async () => {
  const screen = { orientation: { lock: async () => { throw new Error("no fullscreen"); } } };
  const res = await dispatch(call("orientation.lock", { kind: "landscape" }), { screen });
  assert.equal(res.ok, false);
  assert.equal(res.error, "not_allowed");
});

test("orientation.unlock: releases the lock", async () => {
  let unlocked = 0;
  const screen = { orientation: { unlock: () => (unlocked += 1) } };
  const res = await dispatch(call("orientation.unlock"), { screen });
  assert.equal(res.ok, true);
  assert.equal(unlocked, 1);
});

test("orientation.state: reports type and angle", async () => {
  const screen = { orientation: { type: "portrait-primary", angle: 0 } };
  const res = await dispatch(call("orientation.state"), { screen });
  assert.equal(res.ok, true);
  assert.deepEqual(res.value, { type: "portrait-primary", angle: 0 });
});

test("orientation.state: unavailable without a screen orientation", async () => {
  const res = await dispatch(call("orientation.state"), { screen: {} });
  assert.equal(res.ok, false);
  assert.equal(res.error, "unavailable");
});

// --- quota -----------------------------------------------------------------

test("quota.estimate: reports usage and quota", async () => {
  const navigator = { storage: { estimate: async () => ({ usage: 42, quota: 1000 }) } };
  const res = await dispatch(call("quota.estimate"), { navigator });
  assert.equal(res.ok, true);
  assert.deepEqual(res.value, { usage: 42, quota: 1000 });
});

test("quota.estimate: defaults missing fields to zero", async () => {
  const navigator = { storage: { estimate: async () => ({}) } };
  const res = await dispatch(call("quota.estimate"), { navigator });
  assert.deepEqual(res.value, { usage: 0, quota: 0 });
});

test("quota.estimate: unavailable when StorageManager is missing", async () => {
  const res = await dispatch(call("quota.estimate"), { navigator: {} });
  assert.equal(res.ok, false);
  assert.equal(res.error, "unavailable");
});

test("quota.persist: returns the persisted flag", async () => {
  const navigator = { storage: { persist: async () => true } };
  const res = await dispatch(call("quota.persist"), { navigator });
  assert.equal(res.ok, true);
  assert.deepEqual(res.value, { persisted: true });
});

test("quota.persisted: returns the current persisted flag", async () => {
  const navigator = { storage: { persisted: async () => false } };
  const res = await dispatch(call("quota.persisted"), { navigator });
  assert.equal(res.ok, true);
  assert.deepEqual(res.value, { persisted: false });
});

// --- network ---------------------------------------------------------------

test("network.state: reports online + connection details", async () => {
  const navigator = {
    onLine: true,
    connection: { effectiveType: "4g", downlink: 10, rtt: 50, saveData: true },
  };
  const res = await dispatch(call("network.state"), { navigator });
  assert.equal(res.ok, true);
  assert.deepEqual(res.value, {
    online: true,
    effective_type: "4g",
    downlink: 10,
    rtt: 50,
    save_data: true,
  });
});

test("network.state: degrades gracefully without a connection object", async () => {
  const navigator = { onLine: false };
  const res = await dispatch(call("network.state"), { navigator });
  assert.equal(res.ok, true);
  assert.deepEqual(res.value, {
    online: false,
    effective_type: "unknown",
    downlink: 0,
    rtt: 0,
    save_data: false,
  });
});

// --- clipboard images ------------------------------------------------------

/** Install a minimal FileReader/Blob/ClipboardItem on globalThis for a test. */
function withClipboardGlobals(fn) {
  const prevFR = globalThis.FileReader;
  const prevCI = globalThis.ClipboardItem;
  class FakeFileReader {
    readAsDataURL(_blob) {
      // Emit a data URL whose base64 payload is "QUJD" (bytes "ABC").
      this.result = "data:image/png;base64,QUJD";
      if (this.onload) this.onload();
    }
  }
  globalThis.FileReader = FakeFileReader;
  globalThis.ClipboardItem = class {
    constructor(map) {
      this.map = map;
    }
  };
  return Promise.resolve()
    .then(fn)
    .finally(() => {
      globalThis.FileReader = prevFR;
      globalThis.ClipboardItem = prevCI;
    });
}

test("clipboard.read_image: returns the first image as base64", async () => {
  await withClipboardGlobals(async () => {
    const blob = { type: "image/png" };
    const navigator = {
      clipboard: {
        read: async () => [
          {
            types: ["text/plain"],
            getType: async () => ({}),
          },
          {
            types: ["image/png"],
            getType: async (t) => {
              assert.equal(t, "image/png");
              return blob;
            },
          },
        ],
      },
    };
    const res = await dispatch(call("clipboard.read_image"), { navigator });
    assert.equal(res.ok, true);
    assert.deepEqual(res.value, { data_base64: "QUJD", mime_type: "image/png" });
  });
});

test("clipboard.read_image: not_found when there is no image", async () => {
  await withClipboardGlobals(async () => {
    const navigator = {
      clipboard: { read: async () => [{ types: ["text/plain"], getType: async () => ({}) }] },
    };
    const res = await dispatch(call("clipboard.read_image"), { navigator });
    assert.equal(res.ok, false);
    assert.equal(res.error, "not_found");
  });
});

test("clipboard.read_image: unavailable when clipboard.read is missing", async () => {
  await withClipboardGlobals(async () => {
    const res = await dispatch(call("clipboard.read_image"), { navigator: { clipboard: {} } });
    assert.equal(res.ok, false);
    assert.equal(res.error, "unavailable");
  });
});

test("clipboard.read_image: permission_denied when read rejects", async () => {
  await withClipboardGlobals(async () => {
    const navigator = { clipboard: { read: async () => { throw new Error("blocked"); } } };
    const res = await dispatch(call("clipboard.read_image"), { navigator });
    assert.equal(res.ok, false);
    assert.equal(res.error, "permission_denied");
  });
});

test("clipboard.write_image: builds a ClipboardItem and writes it", async () => {
  await withClipboardGlobals(async () => {
    let written;
    const navigator = { clipboard: { write: async (items) => (written = items) } };
    const res = await dispatch(
      call("clipboard.write_image", { data_base64: "QUJD", mime_type: "image/png" }),
      { navigator },
    );
    assert.equal(res.ok, true);
    assert.deepEqual(res.value, {});
    assert.equal(written.length, 1);
    assert.ok(written[0].map["image/png"] instanceof Blob);
  });
});

test("clipboard.write_image: unavailable when clipboard.write is missing", async () => {
  await withClipboardGlobals(async () => {
    const res = await dispatch(
      call("clipboard.write_image", { data_base64: "QUJD", mime_type: "image/png" }),
      { navigator: { clipboard: {} } },
    );
    assert.equal(res.ok, false);
    assert.equal(res.error, "unavailable");
  });
});
