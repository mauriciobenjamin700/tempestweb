// native/webaudio.js — Web Audio (short tone) glue for the Tier-3 seam.
//
// Synthesizes a brief oscillator tone through an `AudioContext`. Fire-and-forget:
// the handler returns as soon as the tone is scheduled; the context closes itself
// when the oscillator ends (we do NOT await the tone finishing).

import { CapabilityError } from "./index.js";

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
