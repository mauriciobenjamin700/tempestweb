// native/gamepad.js — Gamepad API glue for the Tier-3 seam.
//
// `navigator.getGamepads()` returns a snapshot (with null holes for empty slots)
// of the connected gamepads' button/axis state. We drop the holes and serialize
// each pad's buttons and axes into a JSON-able shape.

import { CapabilityError } from "./index.js";

/**
 * Snapshot the connected gamepads' button and axis state.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{gamepads:Array<Object>}>}
 * @throws {CapabilityError} unavailable.
 */
export async function gamepadState(_args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  if (!nav || typeof nav.getGamepads !== "function") {
    throw new CapabilityError("unavailable", "the Gamepad API is not available");
  }
  const pads = Array.from(nav.getGamepads()).filter((g) => g);
  const gamepads = pads.map((g) => ({
    index: g.index,
    id: g.id,
    buttons: Array.from(g.buttons).map((b) => ({ pressed: b.pressed, value: b.value })),
    axes: Array.from(g.axes),
  }));
  return { gamepads };
}
