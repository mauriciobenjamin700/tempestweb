// native/clipboard.js — Clipboard API glue for the N3 clipboard capability.
//
// Reads/writes require a secure context and (for reads) transient user
// activation; failures surface as `permission_denied`.

import { CapabilityError } from "./index.js";

/**
 * Read the current clipboard text.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{text:string}>}
 * @throws {CapabilityError} permission_denied / insecure_context / unavailable.
 */
export async function clipboardRead(_args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  if (!nav || !nav.clipboard || typeof nav.clipboard.readText !== "function") {
    throw new CapabilityError("unavailable", "clipboard read is not available");
  }
  try {
    const text = await nav.clipboard.readText();
    return { text: text || "" };
  } catch (err) {
    throw new CapabilityError("permission_denied", err && err.message);
  }
}

/**
 * Write text to the clipboard.
 * @param {{text:string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<Object>}
 * @throws {CapabilityError} permission_denied / insecure_context / unavailable.
 */
export async function clipboardWrite(args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  if (!nav || !nav.clipboard || typeof nav.clipboard.writeText !== "function") {
    throw new CapabilityError("unavailable", "clipboard write is not available");
  }
  try {
    await nav.clipboard.writeText(args.text || "");
    return {};
  } catch (err) {
    throw new CapabilityError("permission_denied", err && err.message);
  }
}
