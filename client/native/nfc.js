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
