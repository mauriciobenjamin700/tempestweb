// native/eyedropper.js — EyeDropper API glue for the Tier-3 seam.
//
// `new EyeDropper().open()` lets the user pick a screen color, resolving to an
// object with an `sRGBHex` string. A user-dismiss surfaces as an AbortError,
// mapped to `cancelled`.

import { CapabilityError } from "./index.js";

/**
 * Open the eyedropper and return the picked sRGB hex color.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{srgb_hex:string}>}
 * @throws {CapabilityError} unavailable / cancelled / failed.
 */
export async function eyedropperOpen(_args, deps) {
  const win = deps.window || /** @type {any} */ (globalThis);
  const EyeDropperCtor = win && win.EyeDropper;
  if (typeof EyeDropperCtor !== "function") {
    throw new CapabilityError("unavailable", "the EyeDropper API is not available");
  }
  try {
    const result = await new EyeDropperCtor().open();
    return { srgb_hex: result.sRGBHex };
  } catch (err) {
    if (err && err.name === "AbortError") {
      throw new CapabilityError("cancelled", err.message);
    }
    throw new CapabilityError("failed", err && err.message);
  }
}
