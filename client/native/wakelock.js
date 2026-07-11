// native/wakelock.js — Screen Wake Lock API glue.
//
// `navigator.wakeLock.request("screen")` returns a sentinel that keeps the screen
// awake until released (or auto-released when the page is hidden). The sentinel is
// not JSON-able, so we hold it in a module-level registry keyed by a generated id
// string and return only the id across the seam; `release` looks it back up.

import { CapabilityError } from "./index.js";

/**
 * Live wake-lock sentinels, keyed by the id handed back to Python.
 * @type {Map<string, any>}
 */
const _sentinels = new Map();

/** Monotonic id counter — never Math.random/Date, so ids are stable in tests. */
let _counter = 0;

/**
 * Request a screen wake lock and return its opaque id.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{id:string}>}
 * @throws {CapabilityError} unavailable / not_allowed.
 */
export async function wakelockRequest(_args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  if (!nav || !nav.wakeLock || typeof nav.wakeLock.request !== "function") {
    throw new CapabilityError("unavailable", "the Wake Lock API is not available");
  }
  let sentinel;
  try {
    sentinel = await nav.wakeLock.request("screen");
  } catch (err) {
    throw new CapabilityError("not_allowed", err && err.message);
  }
  _counter += 1;
  const id = `wakelock-${_counter}`;
  _sentinels.set(id, sentinel);
  return { id };
}

/**
 * Release a previously acquired wake lock by id.
 * @param {{id:string}} args
 * @param {import("./index.js").NativeDeps} _deps
 * @returns {Promise<Object>}
 * @throws {CapabilityError} not_found when the id is unknown.
 */
export async function wakelockRelease(args, _deps) {
  const sentinel = _sentinels.get(args.id);
  if (!sentinel) {
    throw new CapabilityError("not_found", `no wake lock for id ${args.id}`);
  }
  await sentinel.release();
  _sentinels.delete(args.id);
  return {};
}
