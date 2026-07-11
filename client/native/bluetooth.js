// native/bluetooth.js — Web Bluetooth (GATT) glue for the Tier-3 seam.
//
// A `BluetoothDevice` and its connected `BluetoothRemoteGATTServer` are not
// JSON-able, so we hold them in a module-level registry keyed by an incrementing
// id and hand only the id (plus the device name) back across the wire. `read`
// and `write` look the server back up and traffic characteristic bytes as base64.

import { CapabilityError } from "./index.js";

/**
 * Live device/server pairs, keyed by the id handed back to Python.
 * @type {Map<number, {device: any, server: any}>}
 */
const _devices = new Map();

/** Monotonic id counter — stable in tests (never Math.random/Date). */
let _counter = 0;

/**
 * Decode a base64 string into a Uint8Array.
 * @param {string} b64
 * @returns {Uint8Array}
 */
function bytesFromBase64(b64) {
  const binary = atob(b64 || "");
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

/**
 * Encode a DataView (or ArrayBufferView) as a base64 string.
 * @param {DataView|ArrayBufferView} view
 * @returns {string}
 */
function base64FromView(view) {
  const bytes = new Uint8Array(view.buffer, view.byteOffset, view.byteLength);
  let binary = "";
  for (let i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

/**
 * Whether the Web Bluetooth API is available.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{supported:boolean}>}
 */
export async function bluetoothIsSupported(_args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  return { supported: !!(nav && nav.bluetooth) };
}

/**
 * Request a Bluetooth device, connect its GATT server, and register it.
 * @param {{filters?:Array<Object>, optional_services?:Array<string>}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{id:number, name:string}>}
 * @throws {CapabilityError} unavailable / cancelled / failed.
 */
export async function bluetoothRequest(args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  if (!nav || !nav.bluetooth || typeof nav.bluetooth.requestDevice !== "function") {
    throw new CapabilityError("unavailable", "the Web Bluetooth API is not available");
  }
  const filters = Array.isArray(args.filters) ? args.filters : [];
  const optionalServices = args.optional_services || [];
  let device;
  try {
    device = await nav.bluetooth.requestDevice(
      filters.length
        ? { filters, optionalServices }
        : { acceptAllDevices: true, optionalServices },
    );
  } catch (err) {
    if (err && err.name === "AbortError") {
      throw new CapabilityError("cancelled", err.message);
    }
    throw new CapabilityError("failed", err && err.message);
  }
  let server;
  try {
    server = await device.gatt.connect();
  } catch (err) {
    throw new CapabilityError("failed", err && err.message);
  }
  _counter += 1;
  const id = _counter;
  _devices.set(id, { device, server });
  return { id, name: device.name || "" };
}

/**
 * Read a GATT characteristic value as base64.
 * @param {{id:number, service:string, characteristic:string}} args
 * @param {import("./index.js").NativeDeps} _deps
 * @returns {Promise<{data_base64:string}>}
 * @throws {CapabilityError} not_found / failed.
 */
export async function bluetoothRead(args, _deps) {
  const entry = _devices.get(args.id);
  if (!entry) {
    throw new CapabilityError("not_found", `no bluetooth device for id ${args.id}`);
  }
  try {
    const service = await entry.server.getPrimaryService(args.service);
    const characteristic = await service.getCharacteristic(args.characteristic);
    const value = await characteristic.readValue();
    return { data_base64: base64FromView(value) };
  } catch (err) {
    throw new CapabilityError("failed", err && err.message);
  }
}

/**
 * Write base64 bytes to a GATT characteristic.
 * @param {{id:number, service:string, characteristic:string, data_base64:string}} args
 * @param {import("./index.js").NativeDeps} _deps
 * @returns {Promise<Object>}
 * @throws {CapabilityError} not_found / failed.
 */
export async function bluetoothWrite(args, _deps) {
  const entry = _devices.get(args.id);
  if (!entry) {
    throw new CapabilityError("not_found", `no bluetooth device for id ${args.id}`);
  }
  try {
    const service = await entry.server.getPrimaryService(args.service);
    const characteristic = await service.getCharacteristic(args.characteristic);
    await characteristic.writeValue(bytesFromBase64(args.data_base64));
    return {};
  } catch (err) {
    throw new CapabilityError("failed", err && err.message);
  }
}
