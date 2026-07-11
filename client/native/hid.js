// native/hid.js — WebHID glue for the Tier-3 seam.
//
// `navigator.hid.requestDevice({filters})` opens the OS chooser and returns the
// granted devices. We serialize each device's identifying fields; a user-dismiss
// resolves to an empty list (no throw), matching the WebHID behavior.

import { CapabilityError } from "./index.js";

/**
 * Whether the WebHID API is available.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{supported:boolean}>}
 */
export async function hidIsSupported(_args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  return { supported: !!(nav && nav.hid) };
}

/**
 * Request HID device access and return the granted devices.
 * @param {{filters?:Array<Object>}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{devices:Array<{product_name:string, vendor_id:number, product_id:number}>}>}
 * @throws {CapabilityError} unavailable / cancelled / failed.
 */
export async function hidRequest(args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  if (!nav || !nav.hid || typeof nav.hid.requestDevice !== "function") {
    throw new CapabilityError("unavailable", "the WebHID API is not available");
  }
  let devices;
  try {
    devices = await nav.hid.requestDevice({ filters: args.filters || [] });
  } catch (err) {
    if (err && err.name === "AbortError") {
      throw new CapabilityError("cancelled", err.message);
    }
    throw new CapabilityError("failed", err && err.message);
  }
  return {
    devices: (devices || []).map((d) => ({
      product_name: d.productName || "",
      vendor_id: d.vendorId,
      product_id: d.productId,
    })),
  };
}
