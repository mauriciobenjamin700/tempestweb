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
  return { gamepads: snapshotGamepads(nav) };
}

/**
 * Serialize the connected gamepads into a JSON-able array.
 * @param {?Navigator} nav
 * @returns {Array<Object>}
 */
function snapshotGamepads(nav) {
  if (!nav || typeof /** @type {any} */ (nav).getGamepads !== "function") return [];
  const pads = Array.from(/** @type {any} */ (nav).getGamepads()).filter((g) => g);
  return pads.map((g) => ({
    index: g.index,
    id: g.id,
    buttons: Array.from(g.buttons).map((b) => ({ pressed: b.pressed, value: b.value })),
    axes: Array.from(g.axes),
  }));
}

/**
 * Watch gamepad connections, streaming a snapshot per (dis)connect (T-EV).
 *
 * Re-emits `{ event: {gamepads: [...]} }` on window "gamepadconnected" and
 * "gamepaddisconnected". The returned function removes both listeners.
 *
 * @param {Object} _args
 * @param {(payload:Object) => void} emit  Sink for shaped stream payloads.
 * @param {import("./index.js").NativeDeps} deps
 * @returns {() => void}  Teardown that removes the gamepad listeners.
 */
export function gamepadWatch(_args, emit, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  const win = deps.window || /** @type {any} */ (globalThis);
  const push = () => emit({ event: { gamepads: snapshotGamepads(nav) } });
  win.addEventListener("gamepadconnected", push);
  win.addEventListener("gamepaddisconnected", push);
  return () => {
    win.removeEventListener("gamepadconnected", push);
    win.removeEventListener("gamepaddisconnected", push);
  };
}
