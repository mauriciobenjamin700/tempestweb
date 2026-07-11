// native/vibration.js — Vibration API glue for the haptics capability.
//
// `navigator.vibrate` takes a single duration (ms) or a pattern array. It is a
// no-op on devices without a vibrator, and absent entirely on desktop — where we
// surface `unavailable` rather than silently succeeding.

import { CapabilityError } from "./index.js";

/**
 * Vibrate the device with a duration or pattern.
 * @param {{pattern: number|number[]}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<Object>}
 * @throws {CapabilityError} unavailable when the Vibration API is missing.
 */
export async function vibrationVibrate(args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  if (!nav || typeof nav.vibrate !== "function") {
    throw new CapabilityError("unavailable", "the Vibration API is not available");
  }
  nav.vibrate(args.pattern);
  return {};
}
