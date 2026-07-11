// native/nfc.js — Web NFC (write) glue for the Tier-3 seam.
//
// `new NDEFReader().write({records})` writes an NDEF message to a nearby tag.
// A user-dismiss/abort surfaces as an AbortError, mapped to `cancelled`.

import { CapabilityError } from "./index.js";

/**
 * Whether the Web NFC API is available.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{supported:boolean}>}
 */
export async function nfcIsSupported(_args, deps) {
  const win = deps.window || /** @type {any} */ (globalThis);
  return { supported: !!win && "NDEFReader" in win };
}

/**
 * Write an NDEF message to a nearby NFC tag.
 * @param {{records:Array<Object>}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<Object>}
 * @throws {CapabilityError} unavailable / cancelled / failed.
 */
export async function nfcWrite(args, deps) {
  const win = deps.window || /** @type {any} */ (globalThis);
  const NDEFReaderCtor = win && win.NDEFReader;
  if (typeof NDEFReaderCtor !== "function") {
    throw new CapabilityError("unavailable", "the Web NFC API is not available");
  }
  try {
    await new NDEFReaderCtor().write({ records: args.records || [] });
    return {};
  } catch (err) {
    if (err && err.name === "AbortError") {
      throw new CapabilityError("cancelled", err.message);
    }
    throw new CapabilityError("failed", err && err.message);
  }
}

/**
 * Convert an NDEF record's DataView payload to a base64 string.
 * @param {?DataView} data
 * @returns {string} The base64-encoded record bytes ("" when absent).
 */
function recordDataBase64(data) {
  if (!data || typeof data.byteLength !== "number") {
    return "";
  }
  let binary = "";
  for (let i = 0; i < data.byteLength; i += 1) {
    binary += String.fromCharCode(data.getUint8(i));
  }
  return btoa(binary);
}

/**
 * Stream NDEF messages as tags are read (event channel / T-EV).
 * @param {Object} _args
 * @param {(payload: Object) => void} emit  Called with `{event}` / `{error}`.
 * @param {import("./index.js").NativeDeps} deps
 * @returns {() => void} Teardown that aborts the scan.
 * @throws {CapabilityError} unavailable when the Web NFC API is absent.
 */
export function nfcScan(_args, emit, deps) {
  const win = deps.window || /** @type {any} */ (globalThis);
  const NDEFReaderCtor = win && win.NDEFReader;
  if (typeof NDEFReaderCtor !== "function") {
    throw new CapabilityError("unavailable", "the Web NFC API is not available");
  }
  const controller = new (deps.AbortController || globalThis.AbortController)();
  const reader = new NDEFReaderCtor();
  reader.onreading = (event) => {
    const records = [];
    const message = event && event.message;
    if (message && message.records) {
      for (const record of message.records) {
        records.push({
          record_type: record.recordType || "",
          media_type: record.mediaType || "",
          data_base64: recordDataBase64(record.data),
        });
      }
    }
    emit({ event: { serial_number: (event && event.serialNumber) || "", records } });
  };
  reader.onreadingerror = () => {
    emit({ error: "read_error", message: "failed to read the NFC tag" });
  };
  Promise.resolve(reader.scan({ signal: controller.signal })).catch((err) => {
    const code = err && err.name === "NotAllowedError" ? "permission_denied" : "failed";
    emit({ error: code, message: (err && err.message) || "" });
  });
  return () => controller.abort();
}
