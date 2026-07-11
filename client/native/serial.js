// native/serial.js — Web Serial (request) glue for the Tier-3 seam.
//
// `navigator.serial.requestPort({filters})` opens the OS chooser and returns a
// `SerialPort`. The port is not JSON-able, so we hold it in a module-level
// registry keyed by an incrementing id and hand only the id back across the wire.

import { CapabilityError } from "./index.js";

/**
 * Live serial ports, keyed by the id handed back to Python.
 * @type {Map<number, any>}
 */
const _ports = new Map();

/** Monotonic id counter — stable in tests (never Math.random/Date). */
let _counter = 0;

/**
 * Whether the Web Serial API is available.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{supported:boolean}>}
 */
export async function serialIsSupported(_args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  return { supported: !!(nav && nav.serial) };
}

/**
 * Request a serial port and register it.
 * @param {{filters?:Array<Object>}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{id:number}>}
 * @throws {CapabilityError} unavailable / cancelled / failed.
 */
export async function serialRequest(args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  if (!nav || !nav.serial || typeof nav.serial.requestPort !== "function") {
    throw new CapabilityError("unavailable", "the Web Serial API is not available");
  }
  const filters = args.filters;
  let port;
  try {
    port = await nav.serial.requestPort(filters && filters.length ? { filters } : {});
  } catch (err) {
    if (err && err.name === "AbortError") {
      throw new CapabilityError("cancelled", err.message);
    }
    throw new CapabilityError("failed", err && err.message);
  }
  _counter += 1;
  const id = _counter;
  _ports.set(id, port);
  return { id };
}
