// native/contacts.js — Contact Picker API glue for the Tier-3 seam.
//
// `navigator.contacts.select(properties, {multiple})` opens the OS contact
// picker and returns the chosen contacts. A user-dismiss surfaces as an
// AbortError, which we map to `cancelled`.

import { CapabilityError } from "./index.js";

/**
 * Whether the Contact Picker API is available.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{supported:boolean}>}
 */
export async function contactsIsSupported(_args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  return { supported: !!(nav && nav.contacts) };
}

/**
 * Open the OS contact picker for the requested properties.
 * @param {{properties?:Array<string>, multiple?:boolean}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{contacts:Array<Object>}>}
 * @throws {CapabilityError} unavailable / cancelled / failed.
 */
export async function contactsSelect(args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  if (!nav || !nav.contacts || typeof nav.contacts.select !== "function") {
    throw new CapabilityError("unavailable", "the Contact Picker API is not available");
  }
  try {
    const contacts = await nav.contacts.select(args.properties || [], {
      multiple: !!args.multiple,
    });
    return { contacts };
  } catch (err) {
    if (err && err.name === "AbortError") {
      throw new CapabilityError("cancelled", err.message);
    }
    throw new CapabilityError("failed", err && err.message);
  }
}
