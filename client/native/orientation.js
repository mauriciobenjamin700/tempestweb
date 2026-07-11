// native/orientation.js — Screen Orientation API glue.
//
// `screen.orientation.lock(kind)` requires fullscreen on most platforms and is
// unsupported on desktop; `unlock` and `state` are best-effort reads. Reached via
// `deps.screen` so the router stays testable under jsdom.

import { CapabilityError } from "./index.js";

/**
 * Lock the screen orientation to a kind (e.g. "portrait", "landscape").
 * @param {{kind:string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{locked:boolean}>}
 * @throws {CapabilityError} unavailable / not_allowed.
 */
export async function orientationLock(args, deps) {
  const screen = deps.screen || /** @type {any} */ (globalThis).screen;
  if (!screen || !screen.orientation || typeof screen.orientation.lock !== "function") {
    throw new CapabilityError("unavailable", "the Screen Orientation lock API is not available");
  }
  try {
    await screen.orientation.lock(args.kind);
  } catch (err) {
    throw new CapabilityError("not_allowed", err && err.message);
  }
  return { locked: true };
}

/**
 * Release any orientation lock.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<Object>}
 * @throws {CapabilityError} unavailable.
 */
export async function orientationUnlock(_args, deps) {
  const screen = deps.screen || /** @type {any} */ (globalThis).screen;
  if (!screen || !screen.orientation || typeof screen.orientation.unlock !== "function") {
    throw new CapabilityError("unavailable", "the Screen Orientation API is not available");
  }
  screen.orientation.unlock();
  return {};
}

/**
 * Report the current orientation type and angle.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{type:string, angle:number}>}
 * @throws {CapabilityError} unavailable.
 */
export async function orientationState(_args, deps) {
  const screen = deps.screen || /** @type {any} */ (globalThis).screen;
  if (!screen || !screen.orientation) {
    throw new CapabilityError("unavailable", "the Screen Orientation API is not available");
  }
  return {
    type: screen.orientation.type,
    angle: screen.orientation.angle,
  };
}
