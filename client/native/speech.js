// native/speech.js — Web Speech synthesis (text-to-speech) glue.
//
// `speechSynthesis.speak(utterance)` is fire-and-forget: we build the utterance,
// hand it to the queue, and resolve immediately without awaiting the spoken audio.
// `voices` reads the currently available voice list (may be empty until the
// browser's async `voiceschanged` event has fired).

import { CapabilityError } from "./index.js";

/**
 * Speak a phrase via the platform speech synthesizer (fire-and-forget).
 * @param {{text:string, lang?:string, rate?:number, pitch?:number, volume?:number}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<Object>}
 * @throws {CapabilityError} unavailable when speech synthesis is missing.
 */
export async function speechSpeak(args, deps) {
  const synth = deps.speechSynthesis || /** @type {any} */ (globalThis).speechSynthesis;
  const UtteranceCtor =
    deps.SpeechSynthesisUtterance || /** @type {any} */ (globalThis).SpeechSynthesisUtterance;
  if (!synth || typeof synth.speak !== "function" || !UtteranceCtor) {
    throw new CapabilityError("unavailable", "speech synthesis is not available");
  }
  const u = new UtteranceCtor(args.text || "");
  if (args.lang) u.lang = args.lang;
  if (typeof args.rate === "number") u.rate = args.rate;
  if (typeof args.pitch === "number") u.pitch = args.pitch;
  if (typeof args.volume === "number") u.volume = args.volume;
  synth.speak(u);
  return {};
}

/**
 * Cancel any queued/ongoing speech.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<Object>}
 * @throws {CapabilityError} unavailable when speech synthesis is missing.
 */
export async function speechCancel(_args, deps) {
  const synth = deps.speechSynthesis || /** @type {any} */ (globalThis).speechSynthesis;
  if (!synth || typeof synth.cancel !== "function") {
    throw new CapabilityError("unavailable", "speech synthesis is not available");
  }
  synth.cancel();
  return {};
}

/**
 * List the available synthesis voices.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{voices:Array<{name:string, lang:string, default:boolean}>}>}
 * @throws {CapabilityError} unavailable when speech synthesis is missing.
 */
export async function speechVoices(_args, deps) {
  const synth = deps.speechSynthesis || /** @type {any} */ (globalThis).speechSynthesis;
  if (!synth || typeof synth.getVoices !== "function") {
    throw new CapabilityError("unavailable", "speech synthesis is not available");
  }
  const voices = (synth.getVoices() || []).map((v) => ({
    name: v.name || "",
    lang: v.lang || "",
    default: !!v.default,
  }));
  return { voices };
}
