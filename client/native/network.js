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
  const online = nav ? nav.onLine !== false : true;
  const c = nav && nav.connection;
  return {
    online,
    effective_type: (c && c.effectiveType) || "unknown",
    downlink: c && c.downlink != null ? c.downlink : 0,
    rtt: c && c.rtt != null ? c.rtt : 0,
    save_data: !!(c && c.saveData),
  };
}
