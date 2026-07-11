// native/battery.js — Battery Status API glue for the battery.watch streaming cap.
//
// `navigator.getBattery()` resolves a BatteryManager whose level/charging state
// updates fire "levelchange"/"chargingchange"/"chargingtimechange"/
// "dischargingtimechange" events. getBattery is async, so the setup runs after a
// microtask; the returned teardown is synchronous (a `cancelled` flag guards the
// late-bound listener removal) so subscribeDispatch can store a plain function.

import { CapabilityError } from "./index.js";

/**
 * Watch the device battery, streaming a shaped payload per update (T-EV).
 *
 * Emits the current snapshot and then re-emits on every battery state change:
 * `{ event: {level, charging, charging_time, discharging_time} }`. If the
 * BatteryManager cannot be obtained, emits `{ error: "unavailable" }`. The
 * returned function removes the listeners once the manager has resolved.
 *
 * @param {Object} _args
 * @param {(payload:Object) => void} emit  Sink for shaped stream payloads.
 * @param {import("./index.js").NativeDeps} deps
 * @returns {() => void}  Teardown that removes the battery listeners.
 * @throws {CapabilityError} unavailable — when the Battery Status API is absent.
 */
export function batteryWatch(_args, emit, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  if (!nav || typeof nav.getBattery !== "function") {
    throw new CapabilityError("unavailable", "the Battery Status API is not available");
  }
  const events = [
    "levelchange",
    "chargingchange",
    "chargingtimechange",
    "dischargingtimechange",
  ];
  let cancelled = false;
  /** @type {?(() => void)} */
  let teardown = null;
  Promise.resolve(nav.getBattery())
    .then((b) => {
      if (cancelled) return;
      const push = () =>
        emit({
          event: {
            level: b.level,
            charging: b.charging,
            charging_time: b.chargingTime,
            discharging_time: b.dischargingTime,
          },
        });
      push();
      events.forEach((ev) => b.addEventListener(ev, push));
      teardown = () => events.forEach((ev) => b.removeEventListener(ev, push));
    })
    .catch((err) => {
      if (!cancelled) emit({ error: "unavailable", message: (err && err.message) || "" });
    });
  return () => {
    cancelled = true;
    if (teardown) teardown();
  };
}
