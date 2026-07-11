// native/network.js — online status + Network Information glue.
//
// `navigator.onLine` is always readable; the Network Information API
// (`navigator.connection`) is spotty across browsers, so we degrade every field
// to a safe default rather than throwing when it is absent.

/**
 * Report connectivity: online flag plus best-effort connection details.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{online:boolean, effective_type:string, downlink:number,
 *                    rtt:number, save_data:boolean}>}
 */
export async function networkState(_args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  return networkSnapshot(nav);
}

/**
 * Build the JSON-able connectivity snapshot shared by `networkState` and
 * `networkWatch`.
 * @param {?Navigator} nav
 * @returns {{online:boolean, effective_type:string, downlink:number,
 *            rtt:number, save_data:boolean}}
 */
function networkSnapshot(nav) {
  const online = nav ? nav.onLine !== false : true;
  const c = nav && /** @type {any} */ (nav).connection;
  return {
    online,
    effective_type: (c && c.effectiveType) || "unknown",
    downlink: c && c.downlink != null ? c.downlink : 0,
    rtt: c && c.rtt != null ? c.rtt : 0,
    save_data: !!(c && c.saveData),
  };
}

/**
 * Watch connectivity, streaming the current network snapshot per change (T-EV).
 *
 * Re-emits `{ event: <networkState snapshot> }` on window "online"/"offline" and
 * on `navigator.connection` "change". The returned function removes every
 * listener it attached.
 *
 * @param {Object} _args
 * @param {(payload:Object) => void} emit  Sink for shaped stream payloads.
 * @param {import("./index.js").NativeDeps} deps
 * @returns {() => void}  Teardown that removes the connectivity listeners.
 */
export function networkWatch(_args, emit, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  const win = deps.window || /** @type {any} */ (globalThis);
  const c = nav && /** @type {any} */ (nav).connection;
  const push = () => emit({ event: networkSnapshot(nav) });
  win.addEventListener("online", push);
  win.addEventListener("offline", push);
  if (c && typeof c.addEventListener === "function") c.addEventListener("change", push);
  return () => {
    win.removeEventListener("online", push);
    win.removeEventListener("offline", push);
    if (c && typeof c.removeEventListener === "function") c.removeEventListener("change", push);
  };
}
