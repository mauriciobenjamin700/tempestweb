// Tests for the client side of the native event channel (T-EV) — the streaming
// counterpart to the single-shot native_call path.
//
// Web APIs are injected as `deps`, so these run under node:test with no real
// browser. They cover subscribeDispatch/unsubscribeDispatch, the geolocation.watch
// streaming handler, and the Mode C facade `native.geolocation.watch`.

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  EVENT_HANDLERS,
  subscribeDispatch,
  unsubscribeDispatch,
  CapabilityError,
} from "../../client/native/index.js";
import { geolocationWatch } from "../../client/native/geolocation.js";
import { native } from "../../client/transpile/native.js";

// --- subscribeDispatch / unsubscribeDispatch -------------------------------

test("EVENT_HANDLERS registers exactly the streaming capabilities", () => {
  assert.deepEqual(Object.keys(EVENT_HANDLERS).sort(), ["geolocation.watch"]);
  assert.equal(typeof EVENT_HANDLERS["geolocation.watch"], "function");
});

test("subscribeDispatch: emits events; unsubscribeDispatch stops it", () => {
  let stopped = 0;
  let sink = null;
  const events = [];
  // A fake streaming capability: keeps the emit sink so the test can drive it.
  EVENT_HANDLERS["fake.stream"] = (args, emit) => {
    sink = emit;
    emit({ event: { n: args.start } });
    return () => {
      stopped += 1;
    };
  };
  try {
    subscribeDispatch(
      { sub_id: "s1", capability: "fake.stream", args: { start: 1 } },
      (p) => events.push(p),
      {},
    );
    sink({ event: { n: 2 } });
    unsubscribeDispatch("s1");
    // After teardown the registry entry is gone, so a repeat is a no-op.
    unsubscribeDispatch("s1");

    assert.deepEqual(events, [{ event: { n: 1 } }, { event: { n: 2 } }]);
    assert.equal(stopped, 1);
  } finally {
    delete EVENT_HANDLERS["fake.stream"];
  }
});

test("subscribeDispatch: unknown capability emits unknown_capability", () => {
  const events = [];
  subscribeDispatch(
    { sub_id: "sX", capability: "nope.stream", args: {} },
    (p) => events.push(p),
    {},
  );
  assert.equal(events.length, 1);
  assert.equal(events[0].error, "unknown_capability");
  assert.equal(events[0].message, "nope.stream");
});

test("subscribeDispatch: a synchronous CapabilityError becomes an {error} payload", () => {
  const events = [];
  EVENT_HANDLERS["boom.stream"] = () => {
    throw new CapabilityError("unavailable", "no api");
  };
  try {
    subscribeDispatch(
      { sub_id: "sB", capability: "boom.stream", args: {} },
      (p) => events.push(p),
      {},
    );
    assert.deepEqual(events, [{ error: "unavailable", message: "no api" }]);
  } finally {
    delete EVENT_HANDLERS["boom.stream"];
  }
});

test("unsubscribeDispatch: unknown id is a no-op", () => {
  assert.doesNotThrow(() => unsubscribeDispatch("never-subscribed"));
});

// --- geolocationWatch -------------------------------------------------------

/** Build a fake navigator.geolocation that captures its callbacks. */
function fakeGeo() {
  const state = { cleared: [], nextId: 7 };
  const geo = {
    watchPosition(onOk, onErr, opts) {
      state.onOk = onOk;
      state.onErr = onErr;
      state.opts = opts;
      return state.nextId;
    },
    clearWatch(id) {
      state.cleared.push(id);
      // Model the browser: a cleared watch stops delivering positions.
      state.onOk = () => {};
      state.onErr = () => {};
    },
  };
  return { geo, state };
}

test("geolocationWatch: streams shaped positions and clears the watch on teardown", () => {
  const { geo, state } = fakeGeo();
  const events = [];
  const unsub = geolocationWatch({ high_accuracy: true }, (p) => events.push(p), {
    navigator: { geolocation: geo },
  });
  assert.equal(state.opts.enableHighAccuracy, true);

  state.onOk({ coords: { latitude: -23.5, longitude: -46.6, accuracy: 12, altitude: 800 } });
  state.onOk({ coords: { latitude: -23.6, longitude: -46.7, accuracy: 0, altitude: null } });

  assert.deepEqual(events, [
    { event: { latitude: -23.5, longitude: -46.6, accuracy: 12, altitude: 800 } },
    { event: { latitude: -23.6, longitude: -46.7, accuracy: 0, altitude: null } },
  ]);

  unsub();
  assert.deepEqual(state.cleared, [7]);
});

test("geolocationWatch: missing API throws CapabilityError('unavailable')", () => {
  assert.throws(
    () => geolocationWatch({}, () => {}, { navigator: {} }),
    (err) => err instanceof CapabilityError && err.code === "unavailable",
  );
});

test("geolocationWatch: error callback maps code 1 to permission_denied", () => {
  const { geo, state } = fakeGeo();
  const events = [];
  geolocationWatch({}, (p) => events.push(p), { navigator: { geolocation: geo } });
  state.onErr({ code: 1, message: "denied" });
  assert.deepEqual(events, [{ error: "permission_denied", message: "denied" }]);
});

test("geolocationWatch: a non-permission error maps to unavailable", () => {
  const { geo, state } = fakeGeo();
  const events = [];
  geolocationWatch({}, (p) => events.push(p), { navigator: { geolocation: geo } });
  state.onErr({ code: 2, message: "no signal" });
  assert.deepEqual(events, [{ error: "unavailable", message: "no signal" }]);
});

// --- Mode C facade: native.geolocation.watch --------------------------------

test("native.geolocation.watch: delivers unwrapped positions; unsub stops delivery", () => {
  const { geo, state } = fakeGeo();
  const g = /** @type {any} */ (globalThis);
  // browserDeps() reads globalThis.navigator; point it at our fake for the test.
  // In Node navigator is a read-only getter, so redefine it via a descriptor.
  const priorDescriptor = Object.getOwnPropertyDescriptor(g, "navigator");
  Object.defineProperty(g, "navigator", {
    value: { geolocation: geo },
    configurable: true,
    writable: true,
  });
  try {
    const seen = [];
    const unsub = native.geolocation.watch((pos) => seen.push(pos));
    assert.equal(state.opts.enableHighAccuracy, true);

    state.onOk({ coords: { latitude: 1, longitude: 2, accuracy: 3, altitude: 4 } });
    assert.deepEqual(seen, [{ latitude: 1, longitude: 2, accuracy: 3, altitude: 4 }]);

    unsub();
    assert.deepEqual(state.cleared, [state.nextId]);
    // After unsubscribe, the underlying watch is cleared — no more delivery.
    state.onOk({ coords: { latitude: 9, longitude: 9, accuracy: 9, altitude: 9 } });
    assert.equal(seen.length, 1);
  } finally {
    if (priorDescriptor) Object.defineProperty(g, "navigator", priorDescriptor);
    else delete g.navigator;
  }
});
