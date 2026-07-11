// native/usb.js — WebUSB (request) glue for the Tier-3 seam.
//
// `navigator.usb.requestDevice({filters})` opens the OS chooser and returns a
// `USBDevice`. The device is not JSON-able, so we hold it in a module-level
// registry keyed by an incrementing id and hand the id plus identifying fields
// back across the wire.

import { CapabilityError } from "./index.js";

/**
 * Live USB devices, keyed by the id handed back to Python.
 * @type {Map<number, any>}
 */
const _devices = new Map();

/** Monotonic id counter — stable in tests (never Math.random/Date). */
let _counter = 0;

/**
 * Whether the WebUSB API is available.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{supported:boolean}>}
 */
export async function usbIsSupported(_args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  return { supported: !!(nav && nav.usb) };
}

/**
 * Request a USB device and register it.
 * @param {{filters?:Array<Object>}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{id:number, vendor_id:number, product_id:number, product_name:string}>}
 * @throws {CapabilityError} unavailable / cancelled / failed.
 */
export async function usbRequest(args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  if (!nav || !nav.usb || typeof nav.usb.requestDevice !== "function") {
    throw new CapabilityError("unavailable", "the WebUSB API is not available");
  }
  let device;
  try {
    device = await nav.usb.requestDevice({ filters: args.filters || [] });
  } catch (err) {
    if (err && err.name === "AbortError") {
      throw new CapabilityError("cancelled", err.message);
    }
    throw new CapabilityError("failed", err && err.message);
  }
  _counter += 1;
  const id = _counter;
  _devices.set(id, device);
  return {
    id,
    vendor_id: device.vendorId,
    product_id: device.productId,
    product_name: device.productName || "",
  };
}
