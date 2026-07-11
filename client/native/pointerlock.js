// native/pointerlock.js — Pointer Lock glue for the Tier-3 seam.
//
// `element.requestPointerLock()` hides the cursor and delivers raw movement
// deltas; `document.exitPointerLock()` releases it. The target element is located
// via a CSS selector (defaulting to the document element).

import { CapabilityError } from "./index.js";

/**
 * Request pointer lock on the element matching `selector`.
 * @param {{selector?:string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<Object>}
 * @throws {CapabilityError} unavailable / not_found / failed.
 */
export async function pointerlockRequest(args, deps) {
  const doc = deps.document || /** @type {any} */ (globalThis).document;
  if (!doc) {
    throw new CapabilityError("unavailable", "the document is not available");
  }
  const el = args.selector ? doc.querySelector(args.selector) : doc.documentElement;
  if (!el) {
    throw new CapabilityError("not_found", "no element matched the selector");
  }
  if (typeof el.requestPointerLock !== "function") {
    throw new CapabilityError("unavailable", "the Pointer Lock API is not available");
  }
  try {
    el.requestPointerLock();
    return {};
  } catch (err) {
    throw new CapabilityError("failed", err && err.message);
  }
}

/**
 * Exit pointer lock.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<Object>}
 * @throws {CapabilityError} unavailable / failed.
 */
export async function pointerlockExit(_args, deps) {
  const doc = deps.document || /** @type {any} */ (globalThis).document;
  if (!doc || typeof doc.exitPointerLock !== "function") {
    throw new CapabilityError("unavailable", "the Pointer Lock API is not available");
  }
  try {
    doc.exitPointerLock();
    return {};
  } catch (err) {
    throw new CapabilityError("failed", err && err.message);
  }
}
