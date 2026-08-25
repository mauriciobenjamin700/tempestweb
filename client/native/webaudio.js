// native/webaudio.js — Web Audio glue for the Tier-3 seam (T24).
//
// Three capabilities over one shared graph:
//
//   - `webaudio.tone`     one-shot beep on its own context (unchanged since N1).
//   - `webaudio.sequence` a whole phrase scheduled in ONE call, on a shared
//                         context + master bus, each step with an envelope.
//   - `webaudio.levels`   an AnalyserNode streaming rms/peak/bands, over the
//                         master bus ("output") or the microphone ("mic").
//
// A phrase crosses the wire once, not once per node: in Mode B every capability
// call is a round-trip, so an API shaped like the Web Audio node graph would put
// the network between an oscillator and its gain. What an app actually needs from
// "beyond a single tone" is scheduling and shaping, and both are per-phrase.
//
// Fire-and-forget: the handlers return as soon as the audio is scheduled.

import { CapabilityError } from "./index.js";

/**
 * @typedef {Object} SharedAudio
 * @property {AudioContext} ctx    The one context every scheduled step shares.
 * @property {GainNode} master     The bus every step connects to, and the
 *                                 analyser taps for `source: "output"`.
 */

/** @type {?SharedAudio} the lazily built shared graph. */
let shared = null;

/** @type {Set<OscillatorNode>} oscillators still scheduled, for `stop`. */
const live = new Set();

/**
 * Get (or build) the shared context and master bus.
 *
 * One context for the whole app, not one per phrase: a browser caps how many
 * contexts a page may open, and a beep-per-context app hits that cap. The bus
 * exists so the analyser has something to tap that is not the destination
 * (which cannot be read back).
 *
 * @param {import("./index.js").NativeDeps} deps
 * @returns {SharedAudio}
 * @throws {CapabilityError} unavailable — when the Web Audio API is absent.
 */
function ensureShared(deps) {
  const AudioContextCtor =
    deps.AudioContext || /** @type {any} */ (globalThis).AudioContext;
  if (typeof AudioContextCtor !== "function") {
    throw new CapabilityError("unavailable", "the Web Audio API is not available");
  }
  if (shared == null) {
    const ctx = new AudioContextCtor();
    const master = ctx.createGain();
    if (master.gain) master.gain.value = 1.0;
    master.connect(ctx.destination);
    shared = { ctx, master };
  }
  return shared;
}

/**
 * Ramp a step's gain: silence → peak over the attack, → silence over the release.
 *
 * A bare `gain.value` assignment is what makes a synthesized note click at both
 * edges — the waveform starts and stops mid-cycle at full amplitude. The ramps
 * are what "beyond a single tone" mostly means in practice.
 *
 * @param {GainNode} gain      The step's own gain node.
 * @param {number} peak        The step's target gain (0..1).
 * @param {number} start       Context time the step starts at, in seconds.
 * @param {number} end         Context time the step ends at, in seconds.
 * @param {number} attack      Attack length in seconds (clamped to the step).
 * @param {number} release     Release length in seconds (clamped to the step).
 * @returns {void}
 */
function shapeEnvelope(gain, peak, start, end, attack, release) {
  const param = gain.gain;
  if (!param || typeof param.setValueAtTime !== "function") {
    if (param) param.value = peak;
    return;
  }
  const span = Math.max(end - start, 0);
  const rise = Math.min(attack, span / 2);
  const fall = Math.min(release, span - rise);
  param.setValueAtTime(0, start);
  param.linearRampToValueAtTime(peak, start + rise);
  param.setValueAtTime(peak, Math.max(end - fall, start + rise));
  param.linearRampToValueAtTime(0, end);
}

/**
 * Play a short synthesized tone.
 * @param {{frequency:number, duration_ms:number, type?:string, volume?:number}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<Object>}
 * @throws {CapabilityError} unavailable / failed.
 */
export async function webaudioTone(args, deps) {
  const AudioContextCtor =
    deps.AudioContext || /** @type {any} */ (globalThis).AudioContext;
  if (typeof AudioContextCtor !== "function") {
    throw new CapabilityError("unavailable", "the Web Audio API is not available");
  }
  try {
    const ctx = new AudioContextCtor();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = args.type || "sine";
    osc.frequency.value = args.frequency;
    gain.gain.value = args.volume != null ? args.volume : 1.0;
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + (args.duration_ms || 0) / 1000);
    osc.onended = () => ctx.close();
    return {};
  } catch (err) {
    throw new CapabilityError("failed", err && err.message);
  }
}


/**
 * Schedule a whole phrase in one call.
 *
 * Every step gets its own oscillator and gain, connected to the shared master
 * bus, started at `start_ms` from now and stopped after `duration_ms`, with the
 * envelope shaped by :func:`shapeEnvelope`. Steps may overlap — that is how a
 * chord is written.
 *
 * Autoplay: a context created before the first user gesture starts `suspended`.
 * `resume()` is attempted and the result reports `blocked` rather than throwing,
 * matching `audio.play`: the phrase is still scheduled, and a later gesture
 * resumes it.
 *
 * @param {{steps: Array<{frequency:number, duration_ms:number, start_ms?:number,
 *          type?:string, gain?:number, attack_ms?:number, release_ms?:number}>}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{scheduled:number, ends_in_ms:number, blocked:boolean}>}
 * @throws {CapabilityError} unavailable / failed.
 */
export async function webaudioSequence(args, deps) {
  const { ctx, master } = ensureShared(deps);
  const steps = Array.isArray(args.steps) ? args.steps : [];
  try {
    if (ctx.state === "suspended" && typeof ctx.resume === "function") {
      await ctx.resume();
    }
  } catch {
    /* a refused resume is reported as blocked below, never thrown */
  }
  let ends = 0;
  try {
    const now = ctx.currentTime;
    for (const step of steps) {
      const start = now + (step.start_ms || 0) / 1000;
      const end = start + Math.max(step.duration_ms || 0, 0) / 1000;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = step.type || "sine";
      if (osc.frequency) osc.frequency.value = step.frequency;
      shapeEnvelope(
        gain,
        step.gain != null ? step.gain : 0.5,
        start,
        end,
        (step.attack_ms != null ? step.attack_ms : 5) / 1000,
        (step.release_ms != null ? step.release_ms : 40) / 1000,
      );
      osc.connect(gain);
      gain.connect(master);
      osc.start(start);
      osc.stop(end);
      live.add(osc);
      osc.onended = () => live.delete(osc);
      ends = Math.max(ends, (end - now) * 1000);
    }
  } catch (err) {
    throw new CapabilityError("failed", err && err.message);
  }
  return {
    scheduled: steps.length,
    ends_in_ms: Math.round(ends),
    blocked: ctx.state === "suspended",
  };
}

/**
 * Stop every step still scheduled or sounding.
 *
 * The oscillators are stopped, not the context: closing it would make the next
 * phrase pay for a new context, and a closed context cannot be reopened.
 *
 * @param {Object} _args        Unused — stopping is not parameterized.
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{stopped:number}>}
 */
export async function webaudioStop(_args, deps) {
  if (shared == null) return { stopped: 0 };
  let stopped = 0;
  for (const osc of Array.from(live)) {
    try {
      osc.stop(0);
      stopped += 1;
    } catch {
      /* an oscillator that already ended cannot be stopped again */
    }
    live.delete(osc);
  }
  return { stopped };
}

/**
 * Stream loudness and a coarse spectrum from the master bus or the microphone.
 *
 * Each tick emits `{ event: { rms, peak, bands } }`: `rms` and `peak` are 0..1
 * from the time-domain samples, and `bands` averages the frequency bins into
 * `bands` buckets (0..1 each). A failing microphone emits
 * `{ error, message }` — "permission_denied" when the user refuses, else
 * "unavailable" — the same shape `geolocation.watch` uses.
 *
 * `source: "output"` taps the shared bus, so an app can meter what it is itself
 * synthesizing with no microphone and no permission prompt.
 *
 * @param {{source?:string, interval_ms?:number, bands?:number, fft_size?:number}} args
 * @param {(payload:Object) => void} emit  Sink for shaped stream payloads.
 * @param {import("./index.js").NativeDeps} deps
 * @returns {() => void}  Teardown that stops sampling and releases the source.
 * @throws {CapabilityError} unavailable — when the Web Audio API is absent.
 */
export function webaudioLevels(args, emit, deps) {
  const { ctx, master } = ensureShared(deps);
  const interval = Math.max(args.interval_ms || 100, 16);
  const bandCount = Math.max(args.bands || 8, 1);
  const analyser = ctx.createAnalyser();
  analyser.fftSize = args.fft_size || 2048;
  const timeBuffer = new Uint8Array(analyser.fftSize);
  const freqBuffer = new Uint8Array(analyser.frequencyBinCount || bandCount);
  const setIntervalFn = deps.setInterval || globalThis.setInterval;
  const clearIntervalFn = deps.clearInterval || globalThis.clearInterval;

  let stopped = false;
  /** @type {?MediaStream} */
  let stream = null;

  const sample = () => {
    analyser.getByteTimeDomainData(timeBuffer);
    let sum = 0;
    let peak = 0;
    for (const value of timeBuffer) {
      const centred = (value - 128) / 128;
      sum += centred * centred;
      peak = Math.max(peak, Math.abs(centred));
    }
    analyser.getByteFrequencyData(freqBuffer);
    const width = Math.max(Math.floor(freqBuffer.length / bandCount), 1);
    const bands = [];
    for (let index = 0; index < bandCount; index += 1) {
      let total = 0;
      let counted = 0;
      for (let bin = index * width; bin < (index + 1) * width && bin < freqBuffer.length; bin += 1) {
        total += freqBuffer[bin];
        counted += 1;
      }
      bands.push(counted ? Number((total / counted / 255).toFixed(4)) : 0);
    }
    emit({
      event: {
        rms: Number(Math.sqrt(sum / timeBuffer.length).toFixed(4)),
        peak: Number(peak.toFixed(4)),
        bands,
      },
    });
  };

  const timer = setIntervalFn(() => {
    if (!stopped) sample();
  }, interval);

  if ((args.source || "output") === "mic") {
    const media = (deps.navigator || /** @type {any} */ (globalThis).navigator)
      .mediaDevices;
    if (!media || typeof media.getUserMedia !== "function") {
      emit({ error: "unavailable", message: "getUserMedia is not available" });
    } else {
      media
        .getUserMedia({ audio: true })
        .then((granted) => {
          if (stopped) {
            for (const track of granted.getTracks()) track.stop();
            return;
          }
          stream = granted;
          ctx.createMediaStreamSource(granted).connect(analyser);
        })
        .catch((err) => {
          emit({
            error: err && err.name === "NotAllowedError"
              ? "permission_denied"
              : "unavailable",
            message: (err && err.message) || "",
          });
        });
    }
  } else {
    master.connect(analyser);
  }

  return () => {
    stopped = true;
    clearIntervalFn(timer);
    try {
      analyser.disconnect();
    } catch {
      /* an analyser never connected cannot be disconnected */
    }
    if (stream) {
      for (const track of stream.getTracks()) track.stop();
      stream = null;
    }
  };
}

/**
 * Drop the shared graph, so the next call builds a fresh one.
 *
 * For tests only: a module-level context would otherwise leak between cases,
 * and a fake context from one case would serve the next.
 *
 * @returns {void}
 */
export function resetSharedAudioForTests() {
  shared = null;
  live.clear();
}
