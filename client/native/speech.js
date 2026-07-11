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

/**
 * Listen for speech recognition results, streaming each transcript (T-EV).
 *
 * Each result emits `{ event: {transcript, is_final, confidence} }`; a
 * recognition error emits `{ error }`. Recognition runs continuously until the
 * returned function stops it.
 *
 * @param {{lang?:string, interim?:boolean}} args
 * @param {(payload:Object) => void} emit  Sink for shaped stream payloads.
 * @param {import("./index.js").NativeDeps} deps
 * @returns {() => void}  Teardown that stops the recognizer.
 * @throws {CapabilityError} unavailable — when the Speech Recognition API is absent.
 */
export function speechListen(args, emit, deps) {
  const g = /** @type {any} */ (globalThis);
  const R = deps.SpeechRecognition || g.SpeechRecognition || g.webkitSpeechRecognition;
  if (!R) {
    throw new CapabilityError("unavailable", "the Speech Recognition API is not available");
  }
  const r = new R();
  r.lang = args.lang || "";
  r.interimResults = !!args.interim;
  r.continuous = true;
  r.onresult = (ev) => {
    const res = ev.results[ev.results.length - 1];
    emit({
      event: {
        transcript: res[0].transcript,
        is_final: !!res.isFinal,
        confidence: res[0].confidence || 0,
      },
    });
  };
  r.onerror = (e) => emit({ error: (e && e.error) || "error" });
  r.start();
  return () => r.stop();
}
