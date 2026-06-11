// native/geolocation.js — Geolocation API glue for the N3 geolocation capability.

import { CapabilityError } from "./index.js";

/**
 * Map a GeolocationPositionError code to a stable capability error code.
 * @param {number} code
 * @returns {string}
 */
function geoErrorCode(code) {
  // 1 = PERMISSION_DENIED, 2 = POSITION_UNAVAILABLE, 3 = TIMEOUT
  if (code === 1) return "permission_denied";
  if (code === 3) return "timeout";
  return "unavailable";
}

/**
 * Request a single position fix.
 * @param {{high_accuracy:boolean}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{latitude:number,longitude:number,accuracy:number,altitude:number|null}>}
 * @throws {CapabilityError} permission_denied / timeout / unavailable / insecure_context.
 */
export async function geolocationGet(args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  if (!nav || !nav.geolocation) {
    throw new CapabilityError("unavailable", "geolocation is not available");
  }
  return new Promise((resolve, reject) => {
    nav.geolocation.getCurrentPosition(
      (pos) => {
        const c = pos.coords;
        resolve({
          latitude: c.latitude,
          longitude: c.longitude,
          accuracy: typeof c.accuracy === "number" ? c.accuracy : 0.0,
          altitude: typeof c.altitude === "number" ? c.altitude : null,
        });
      },
      (err) => reject(new CapabilityError(geoErrorCode(err && err.code), err && err.message)),
      { enableHighAccuracy: Boolean(args.high_accuracy) },
    );
  });
}
