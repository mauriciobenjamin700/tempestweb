// native/fullscreen.js — Fullscreen API glue.
//
// Entering fullscreen requires transient user activation. `enter`/`exit` drive
// the document element; `state` reports whether an element is currently
// fullscreen without any gesture requirement.

import { CapabilityError } from "./index.js";

/**
 * Enter fullscreen on the document element.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{active:boolean}>}
 * @throws {CapabilityError} unavailable / not_allowed.
 */
export async function fullscreenEnter(_args, deps) {
  const doc = deps.document || /** @type {any} */ (globalThis).document;
  const el = doc && doc.documentElement;
  if (!el || typeof el.requestFullscreen !== "function") {
    throw new CapabilityError("unavailable", "the Fullscreen API is not available");
  }
  try {
    await el.requestFullscreen();
  } catch (err) {
    throw new CapabilityError("not_allowed", err && err.message);
  }
  return { active: true };
}

/**
 * Exit fullscreen.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{active:boolean}>}
 * @throws {CapabilityError} unavailable.
 */
export async function fullscreenExit(_args, deps) {
  const doc = deps.document || /** @type {any} */ (globalThis).document;
  if (!doc || typeof doc.exitFullscreen !== "function") {
    throw new CapabilityError("unavailable", "the Fullscreen API is not available");
  }
  await doc.exitFullscreen();
  return { active: false };
}

/**
 * Report whether an element is currently fullscreen.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{active:boolean}>}
 */
export async function fullscreenState(_args, deps) {
  const doc = deps.document || /** @type {any} */ (globalThis).document;
  return { active: !!(doc && doc.fullscreenElement) };
}
