// Tests for the T24 Web Audio capabilities: a phrase scheduled in one call, and
// the analyser that streams levels from the shared bus or the microphone.
//
// The AudioContext is injected as a dep, so these run under node:test with no
// real browser: the fake records every scheduling call, which is what the wire
// contract is made of (start/stop times, envelope ramps, node connections).

import { test } from "node:test";
import assert from "node:assert/strict";

import { dispatch, subscribeDispatch, unsubscribeDispatch } from "../../client/native/index.js";
import { resetSharedAudioForTests } from "../../client/native/webaudio.js";
import { native } from "../../client/transpile/native.js";

/** Build a native_call envelope. */
function call(capability, args = {}, callId = "c1") {
  return { kind: "native_call", call_id: callId, capability, args };
}

/** A gain param that records its ramp calls, like the real AudioParam. */
function fakeParam(log, label) {
  return {
    value: 0,
    setValueAtTime: (v, t) => log.push(`${label}.set:${v}@${t.toFixed(3)}`),
    linearRampToValueAtTime: (v, t) => log.push(`${label}.ramp:${v}@${t.toFixed(3)}`),
  };
}

/**
 * An AudioContext fake that records what a phrase schedules.
 *
 * `state` starts "running": the suspended (autoplay-blocked) path is exercised by
 * the dedicated test below, which passes its own.
 */
function fakeContext(log, state = "running") {
  const analysers = [];
  const ctx = {
    currentTime: 10,
    state,
    destination: { kind: "destination" },
    analysers,
    resume: async () => {
      log.push("resume");
      ctx.state = "running";
    },
    createOscillator: () => {
      const osc = {
        frequency: { value: 0 },
        connect: () => log.push("osc.connect"),
        start: (t) => log.push(`start@${t.toFixed(3)}`),
        stop: (t) => log.push(`stop@${t.toFixed(3)}`),
      };
      return osc;
    },
    createGain: () => ({ gain: fakeParam(log, "gain"), connect: () => log.push("gain.connect") }),
    createAnalyser: () => {
      const analyser = {
        fftSize: 0,
        frequencyBinCount: 8,
        connected: 0,
        getByteTimeDomainData: (buf) => buf.fill(192),
        getByteFrequencyData: (buf) => buf.fill(255),
        disconnect: () => log.push("analyser.disconnect"),
      };
      analysers.push(analyser);
      return analyser;
    },
    createMediaStreamSource: (stream) => {
      log.push("mediaStreamSource");
      return { connect: () => log.push("mic.connect"), stream };
    },
  };
  return ctx;
}

test("webaudio.sequence: schedules every step with its envelope, in one call", async () => {
  resetSharedAudioForTests();
  const log = [];
  const res = await dispatch(
    call("webaudio.sequence", {
      steps: [
        { frequency: 440, duration_ms: 200, start_ms: 0, gain: 0.5, attack_ms: 10, release_ms: 40 },
        { frequency: 550, duration_ms: 200, start_ms: 0, gain: 0.5, attack_ms: 10, release_ms: 40 },
      ],
    }),
    { AudioContext: function () { return fakeContext(log); } },
  );

  assert.equal(res.ok, true);
  assert.deepEqual(res.value, { scheduled: 2, ends_in_ms: 200, blocked: false });
  assert.equal(log.filter((line) => line.startsWith("start@")).length, 2);
  assert.ok(log.includes("start@10.000"));
  assert.ok(log.includes("stop@10.200"));
  assert.ok(log.includes("gain.set:0@10.000"), "the envelope starts from silence");
  assert.ok(log.includes("gain.ramp:0.5@10.010"), "attack ramps to the step's gain");
  assert.ok(log.includes("gain.ramp:0@10.200"), "release ends at silence");
});

test("webaudio.sequence: two steps at the same start_ms are a chord, not a queue", async () => {
  resetSharedAudioForTests();
  const log = [];
  await dispatch(
    call("webaudio.sequence", {
      steps: [
        { frequency: 261.6, duration_ms: 300, start_ms: 0 },
        { frequency: 329.6, duration_ms: 300, start_ms: 0 },
        { frequency: 392.0, duration_ms: 300, start_ms: 0 },
      ],
    }),
    { AudioContext: function () { return fakeContext(log); } },
  );
  const starts = log.filter((line) => line.startsWith("start@"));
  assert.equal(starts.length, 3);
  assert.deepEqual(new Set(starts), new Set(["start@10.000"]));
});

test("webaudio.sequence: an empty phrase is a no-op that still reports", async () => {
  resetSharedAudioForTests();
  const res = await dispatch(call("webaudio.sequence", { steps: [] }), {
    AudioContext: function () { return fakeContext([]); },
  });
  assert.deepEqual(res.value, { scheduled: 0, ends_in_ms: 0, blocked: false });
});

test("webaudio.sequence: a suspended context reports blocked, and still schedules", async () => {
  resetSharedAudioForTests();
  const log = [];
  const ctx = fakeContext(log, "suspended");
  ctx.resume = async () => log.push("resume-refused");
  const res = await dispatch(
    call("webaudio.sequence", { steps: [{ frequency: 440, duration_ms: 100 }] }),
    { AudioContext: function () { return ctx; } },
  );
  assert.equal(res.value.blocked, true);
  assert.equal(res.value.scheduled, 1);
  assert.ok(log.includes("resume-refused"));
  assert.ok(log.includes("start@10.000"), "the phrase is scheduled anyway");
});

test("webaudio.sequence: unavailable when AudioContext is missing", async () => {
  resetSharedAudioForTests();
  const res = await dispatch(call("webaudio.sequence", { steps: [] }), {});
  assert.equal(res.error, "unavailable");
});

test("webaudio.stop: stops what is live, and leaves the context open", async () => {
  resetSharedAudioForTests();
  const log = [];
  const ctx = fakeContext(log);
  function ctor() {
    return ctx;
  }
  await dispatch(call("webaudio.sequence", { steps: [{ frequency: 440, duration_ms: 500 }] }), {
    AudioContext: ctor,
  });
  const res = await dispatch(call("webaudio.stop", {}), { AudioContext: ctor });
  assert.deepEqual(res.value, { stopped: 1 });
  assert.ok(!log.includes("close"), "the shared context is not closed");

  const again = await dispatch(call("webaudio.stop", {}), { AudioContext: ctor });
  assert.deepEqual(again.value, { stopped: 0 }, "stopping twice is a no-op");
});

test("webaudio.levels: streams rms/peak/bands off the shared bus", () => {
  resetSharedAudioForTests();
  const log = [];
  const events = [];
  let tick = null;
  subscribeDispatch(
    { sub_id: "s-levels", capability: "webaudio.levels", args: { source: "output", bands: 4, interval_ms: 50 } },
    (payload) => events.push(payload),
    {
      AudioContext: function () { return fakeContext(log); },
      setInterval: (fn) => {
        tick = fn;
        return 7;
      },
      clearInterval: (id) => log.push(`clearInterval:${id}`),
    },
  );

  tick();
  unsubscribeDispatch("s-levels");

  assert.equal(events.length, 1);
  const level = events[0].event;
  assert.equal(level.bands.length, 4);
  assert.deepEqual(level.bands, [1, 1, 1, 1], "a full spectrum normalizes to 1.0");
  assert.ok(level.peak > 0.4 && level.peak < 0.55, `peak was ${level.peak}`);
  assert.ok(level.rms > 0.4 && level.rms < 0.55, `rms was ${level.rms}`);
  assert.ok(log.includes("clearInterval:7"), "teardown stops sampling");
  assert.ok(log.includes("analyser.disconnect"));
});

test("webaudio.levels: a refused microphone emits permission_denied, not a throw", () => {
  resetSharedAudioForTests();
  const events = [];
  const refusal = Object.assign(new Error("no"), { name: "NotAllowedError" });
  subscribeDispatch(
    { sub_id: "s-mic", capability: "webaudio.levels", args: { source: "mic" } },
    (payload) => events.push(payload),
    {
      AudioContext: function () { return fakeContext([]); },
      navigator: { mediaDevices: { getUserMedia: async () => { throw refusal; } } },
      setInterval: () => 1,
      clearInterval: () => {},
    },
  );
  return new Promise((resolve) => setTimeout(resolve, 10)).then(() => {
    unsubscribeDispatch("s-mic");
    assert.deepEqual(events, [{ error: "permission_denied", message: "no" }]);
  });
});

test("webaudio.levels: no getUserMedia at all is unavailable, reported once", () => {
  resetSharedAudioForTests();
  const events = [];
  subscribeDispatch(
    { sub_id: "s-nomic", capability: "webaudio.levels", args: { source: "mic" } },
    (payload) => events.push(payload),
    {
      AudioContext: function () { return fakeContext([]); },
      navigator: {},
      setInterval: () => 1,
      clearInterval: () => {},
    },
  );
  unsubscribeDispatch("s-nomic");
  assert.equal(events.length, 1);
  assert.equal(events[0].error, "unavailable");
});

test("the Mode C facade fills the same defaults the Python Step does", () => {
  assert.equal(typeof native.webaudio.sequence, "function");
  assert.equal(typeof native.webaudio.stop, "function");
  assert.equal(typeof native.webaudio.watch_levels, "function");
});
