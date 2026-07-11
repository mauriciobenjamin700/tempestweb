// Tests for the 11 STREAMING native capabilities on the event channel (T-EV).
//
// Web APIs are injected as `deps`, so these run under node:test with no real
// browser. Each capability: fire a synthetic event and assert the shaped
// `{event:{...}}` payload; assert the teardown removes the listener/stops the
// source; cover a missing-API "unavailable" path where applicable.

import { test } from "node:test";
import assert from "node:assert/strict";

import { EVENT_HANDLERS, CapabilityError } from "../../client/native/index.js";
import { batteryWatch } from "../../client/native/battery.js";
import { idleWatch } from "../../client/native/idle.js";
import { sensorsMotion, sensorsOrientation } from "../../client/native/sensors.js";
import { networkWatch } from "../../client/native/network.js";
import { orientationWatch } from "../../client/native/orientation.js";
import { visibilityWatch } from "../../client/native/visibility.js";
import { speechListen } from "../../client/native/speech.js";
import { tabsReceive } from "../../client/native/tabs.js";
import { midiMessages } from "../../client/native/midi.js";
import { gamepadWatch } from "../../client/native/gamepad.js";

/** A minimal EventTarget mock that records add/remove and can fire by type. */
function fakeTarget() {
  const listeners = new Map();
  return {
    listeners,
    addEventListener(type, fn) {
      if (!listeners.has(type)) listeners.set(type, new Set());
      listeners.get(type).add(fn);
    },
    removeEventListener(type, fn) {
      if (listeners.has(type)) listeners.get(type).delete(fn);
    },
    fire(type, event) {
      for (const fn of listeners.get(type) || []) fn(event);
    },
    count(type) {
      return (listeners.get(type) || new Set()).size;
    },
  };
}

/** Flush pending microtasks (for async setup in battery/midi handlers). */
function tick() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

// --- registry --------------------------------------------------------------

test("EVENT_HANDLERS registers exactly the 12 streaming capabilities", () => {
  assert.deepEqual(Object.keys(EVENT_HANDLERS).sort(), [
    "battery.watch",
    "gamepad.watch",
    "geolocation.watch",
    "idle.watch",
    "midi.messages",
    "network.watch",
    "orientation.watch",
    "sensors.motion",
    "sensors.orientation",
    "speech.listen",
    "tabs.receive",
    "visibility.watch",
  ]);
});

// --- battery.watch ----------------------------------------------------------

test("batteryWatch: emits current + on changes; teardown removes listeners", async () => {
  const b = Object.assign(fakeTarget(), {
    level: 0.5,
    charging: true,
    chargingTime: 1200,
    dischargingTime: Infinity,
  });
  const events = [];
  const unsub = batteryWatch({}, (p) => events.push(p), {
    navigator: { getBattery: () => Promise.resolve(b) },
  });
  await tick();
  // Emits current snapshot on resolve.
  assert.deepEqual(events[0], {
    event: { level: 0.5, charging: true, charging_time: 1200, discharging_time: Infinity },
  });
  b.level = 0.6;
  b.fire("levelchange");
  assert.equal(events.length, 2);
  assert.equal(events[1].event.level, 0.6);
  assert.equal(b.count("levelchange"), 1);
  unsub();
  assert.equal(b.count("levelchange"), 0);
});

test("batteryWatch: missing API throws CapabilityError('unavailable')", () => {
  assert.throws(
    () => batteryWatch({}, () => {}, { navigator: {} }),
    (err) => err instanceof CapabilityError && err.code === "unavailable",
  );
});

// --- idle.watch -------------------------------------------------------------

test("idleWatch: emits on change; teardown aborts the detector", async () => {
  let started = null;
  class FakeIdleDetector {
    constructor() {
      this.userState = "active";
      this.screenState = "unlocked";
      this._t = fakeTarget();
    }
    addEventListener(type, fn, opts) {
      this._t.addEventListener(type, fn);
      if (opts && opts.signal) opts.signal.addEventListener("abort", () => this._t.removeEventListener(type, fn));
    }
    start(opts) {
      started = opts;
      return Promise.resolve();
    }
    fire(type) {
      this._t.fire(type);
    }
    count(type) {
      return this._t.count(type);
    }
  }
  const d = new FakeIdleDetector();
  const events = [];
  const unsub = idleWatch({ threshold_seconds: 90 }, (p) => events.push(p), {
    IdleDetector: function () {
      return d;
    },
  });
  await tick();
  assert.equal(started.threshold, 90000);
  d.userState = "idle";
  d.fire("change");
  assert.deepEqual(events, [{ event: { user: "idle", screen: "unlocked" } }]);
  assert.equal(d.count("change"), 1);
  unsub();
  assert.equal(d.count("change"), 0);
});

test("idleWatch: missing API throws CapabilityError('unavailable')", () => {
  assert.throws(
    () => idleWatch({}, () => {}, { IdleDetector: undefined }),
    (err) => err instanceof CapabilityError && err.code === "unavailable",
  );
});

// --- sensors.orientation / sensors.motion -----------------------------------

test("sensorsOrientation: shapes deviceorientation; teardown removes listener", () => {
  const win = fakeTarget();
  const events = [];
  const unsub = sensorsOrientation({}, (p) => events.push(p), { window: win });
  win.fire("deviceorientation", { alpha: 10, beta: 20, gamma: 30, absolute: true });
  assert.deepEqual(events, [
    { event: { alpha: 10, beta: 20, gamma: 30, absolute: true } },
  ]);
  assert.equal(win.count("deviceorientation"), 1);
  unsub();
  assert.equal(win.count("deviceorientation"), 0);
});

test("sensorsMotion: shapes devicemotion; teardown removes listener", () => {
  const win = fakeTarget();
  const events = [];
  const unsub = sensorsMotion({}, (p) => events.push(p), { window: win });
  win.fire("devicemotion", {
    acceleration: { x: 1, y: 2, z: 3 },
    rotationRate: { alpha: 4, beta: 5, gamma: 6 },
    interval: 16,
  });
  assert.deepEqual(events, [
    {
      event: {
        acceleration: { x: 1, y: 2, z: 3 },
        rotation_rate: { alpha: 4, beta: 5, gamma: 6 },
        interval: 16,
      },
    },
  ]);
  assert.equal(win.count("devicemotion"), 1);
  unsub();
  assert.equal(win.count("devicemotion"), 0);
});

// --- network.watch ----------------------------------------------------------

test("networkWatch: emits snapshot on online/offline/change; teardown removes all", () => {
  const win = fakeTarget();
  const conn = Object.assign(fakeTarget(), {
    effectiveType: "4g",
    downlink: 10,
    rtt: 50,
    saveData: false,
  });
  const nav = { onLine: true, connection: conn };
  const events = [];
  const unsub = networkWatch({}, (p) => events.push(p), { navigator: nav, window: win });

  nav.onLine = false;
  win.fire("offline");
  assert.deepEqual(events[0], {
    event: { online: false, effective_type: "4g", downlink: 10, rtt: 50, save_data: false },
  });
  conn.effectiveType = "3g";
  conn.fire("change");
  assert.equal(events[1].event.effective_type, "3g");

  assert.equal(win.count("online"), 1);
  assert.equal(win.count("offline"), 1);
  assert.equal(conn.count("change"), 1);
  unsub();
  assert.equal(win.count("online"), 0);
  assert.equal(win.count("offline"), 0);
  assert.equal(conn.count("change"), 0);
});

// --- orientation.watch ------------------------------------------------------

test("orientationWatch: shapes change; teardown removes listener", () => {
  const orientation = Object.assign(fakeTarget(), { type: "portrait-primary", angle: 0 });
  const events = [];
  const unsub = orientationWatch({}, (p) => events.push(p), { screen: { orientation } });
  orientation.angle = 90;
  orientation.type = "landscape-primary";
  orientation.fire("change");
  assert.deepEqual(events, [
    { event: { type: "landscape-primary", angle: 90 } },
  ]);
  assert.equal(orientation.count("change"), 1);
  unsub();
  assert.equal(orientation.count("change"), 0);
});

test("orientationWatch: missing API throws CapabilityError('unavailable')", () => {
  assert.throws(
    () => orientationWatch({}, () => {}, { screen: {} }),
    (err) => err instanceof CapabilityError && err.code === "unavailable",
  );
});

// --- visibility.watch -------------------------------------------------------

test("visibilityWatch: shapes visibilitychange; teardown removes listener", () => {
  const doc = Object.assign(fakeTarget(), { visibilityState: "visible", hidden: false });
  const events = [];
  const unsub = visibilityWatch({}, (p) => events.push(p), { document: doc });
  doc.visibilityState = "hidden";
  doc.hidden = true;
  doc.fire("visibilitychange");
  assert.deepEqual(events, [{ event: { state: "hidden", hidden: true } }]);
  assert.equal(doc.count("visibilitychange"), 1);
  unsub();
  assert.equal(doc.count("visibilitychange"), 0);
});

// --- speech.listen ----------------------------------------------------------

test("speechListen: shapes results, maps onerror; teardown stops recognizer", () => {
  let stopped = 0;
  const instances = [];
  class FakeRecognition {
    constructor() {
      this.started = false;
      instances.push(this);
    }
    start() {
      this.started = true;
    }
    stop() {
      stopped += 1;
    }
  }
  const events = [];
  const unsub = speechListen({ lang: "pt-BR", interim: true }, (p) => events.push(p), {
    SpeechRecognition: FakeRecognition,
  });
  const r = instances[0];
  assert.equal(r.lang, "pt-BR");
  assert.equal(r.interimResults, true);
  assert.equal(r.continuous, true);
  assert.equal(r.started, true);

  r.onresult({ results: [[{ transcript: "olá", confidence: 0.9 }]] });
  // The last result object doubles as the array + isFinal flag.
  const lastResult = [{ transcript: "mundo", confidence: 0.8 }];
  lastResult.isFinal = true;
  r.onresult({ results: [lastResult] });
  assert.deepEqual(events, [
    { event: { transcript: "olá", is_final: false, confidence: 0.9 } },
    { event: { transcript: "mundo", is_final: true, confidence: 0.8 } },
  ]);

  r.onerror({ error: "no-speech" });
  assert.deepEqual(events[2], { error: "no-speech" });

  unsub();
  assert.equal(stopped, 1);
});

test("speechListen: missing API throws CapabilityError('unavailable')", () => {
  assert.throws(
    () => speechListen({}, () => {}, { SpeechRecognition: undefined }),
    (err) => err instanceof CapabilityError && err.code === "unavailable",
  );
});

// --- tabs.receive -----------------------------------------------------------

test("tabsReceive: shapes messages; teardown closes the channel", () => {
  let closed = 0;
  let channelName = null;
  class FakeBroadcastChannel {
    constructor(name) {
      channelName = name;
      this.onmessage = null;
    }
    close() {
      closed += 1;
    }
  }
  const events = [];
  const unsub = tabsReceive({ channel: "room" }, (p) => events.push(p), {
    BroadcastChannel: FakeBroadcastChannel,
  });
  assert.equal(channelName, "room");
  // The handler wires onmessage; simulate an inbound message via the instance.
  // We can reach the instance by capturing it — simplest: re-create through deps.
  // Instead, drive the stored onmessage directly.
  // (No global instance capture needed: onmessage is set on the created channel.)
  // Re-run with capture:
  unsub();
  assert.equal(closed, 1);

  let captured = null;
  class CapturingBC {
    constructor() {
      captured = this;
      this.onmessage = null;
    }
    close() {}
  }
  const evs = [];
  tabsReceive({ channel: "x" }, (p) => evs.push(p), { BroadcastChannel: CapturingBC });
  captured.onmessage({ data: { hello: 1 } });
  assert.deepEqual(evs, [{ event: { message: { hello: 1 } } }]);
});

test("tabsReceive: missing API throws CapabilityError('unavailable')", () => {
  // Node exposes a global BroadcastChannel, so the deps fallback would find it;
  // shadow it for this test to exercise the missing-API path.
  const g = /** @type {any} */ (globalThis);
  const prior = Object.getOwnPropertyDescriptor(g, "BroadcastChannel");
  Object.defineProperty(g, "BroadcastChannel", { value: undefined, configurable: true, writable: true });
  try {
    assert.throws(
      () => tabsReceive({ channel: "x" }, () => {}, { BroadcastChannel: undefined }),
      (err) => err instanceof CapabilityError && err.code === "unavailable",
    );
  } finally {
    if (prior) Object.defineProperty(g, "BroadcastChannel", prior);
    else delete g.BroadcastChannel;
  }
});

// --- midi.messages ----------------------------------------------------------

test("midiMessages: shapes input messages; teardown detaches handlers", async () => {
  const input = { id: "in-1", onmidimessage: null };
  const access = { inputs: { values: () => [input].values() } };
  const events = [];
  const unsub = midiMessages({}, (p) => events.push(p), {
    navigator: { requestMIDIAccess: () => Promise.resolve(access) },
  });
  await tick();
  assert.equal(typeof input.onmidimessage, "function");
  input.onmidimessage({ data: [144, 60, 100], timeStamp: 42 });
  assert.deepEqual(events, [
    { event: { input_id: "in-1", data: [144, 60, 100], timestamp: 42 } },
  ]);
  unsub();
  assert.equal(input.onmidimessage, null);
});

test("midiMessages: missing API throws CapabilityError('unavailable')", () => {
  assert.throws(
    () => midiMessages({}, () => {}, { navigator: {} }),
    (err) => err instanceof CapabilityError && err.code === "unavailable",
  );
});

// --- gamepad.watch ----------------------------------------------------------

test("gamepadWatch: emits snapshot on (dis)connect; teardown removes listeners", () => {
  const pad = {
    index: 0,
    id: "Pad",
    buttons: [{ pressed: true, value: 1 }],
    axes: [0.5, -0.5],
  };
  const win = fakeTarget();
  const nav = { getGamepads: () => [pad] };
  const events = [];
  const unsub = gamepadWatch({}, (p) => events.push(p), { navigator: nav, window: win });
  win.fire("gamepadconnected");
  assert.deepEqual(events, [
    {
      event: {
        gamepads: [
          { index: 0, id: "Pad", buttons: [{ pressed: true, value: 1 }], axes: [0.5, -0.5] },
        ],
      },
    },
  ]);
  assert.equal(win.count("gamepadconnected"), 1);
  assert.equal(win.count("gamepaddisconnected"), 1);
  unsub();
  assert.equal(win.count("gamepadconnected"), 0);
  assert.equal(win.count("gamepaddisconnected"), 0);
});
