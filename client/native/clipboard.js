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

/**
 * Read the raw bytes of a base64 string into a Uint8Array.
 * @param {string} b64
 * @returns {Uint8Array}
 */
function b64ToBytes(b64) {
  const binary = atob(b64 || "");
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

/**
 * Read the first image on the clipboard as base64 (async ClipboardItem API).
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{data_base64:string, mime_type:string}>}
 * @throws {CapabilityError} unavailable / permission_denied / not_found.
 */
export async function clipboardReadImage(_args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  const FileReaderCtor = /** @type {any} */ (globalThis).FileReader;
  if (!nav || !nav.clipboard || typeof nav.clipboard.read !== "function" || !FileReaderCtor) {
    throw new CapabilityError("unavailable", "clipboard image read is not available");
  }
  let items;
  try {
    items = await nav.clipboard.read();
  } catch (err) {
    throw new CapabilityError("permission_denied", err && err.message);
  }
  for (const item of items) {
    const type = (item.types || []).find((t) => t.startsWith("image/"));
    if (!type) continue;
    const blob = await item.getType(type);
    const dataUrl = await new Promise((resolve, reject) => {
      const reader = new FileReaderCtor();
      reader.onload = () => resolve(String(reader.result || ""));
      reader.onerror = () => reject(new CapabilityError("read_failed", "failed to read image"));
      reader.readAsDataURL(blob);
    });
    const comma = dataUrl.indexOf(",");
    return {
      data_base64: comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl,
      mime_type: type,
    };
  }
  throw new CapabilityError("not_found", "no image on the clipboard");
}

/**
 * Write an image (base64) to the clipboard (async ClipboardItem API).
 * @param {{data_base64:string, mime_type:string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<Object>}
 * @throws {CapabilityError} unavailable / permission_denied.
 */
export async function clipboardWriteImage(args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  const ClipboardItemCtor = /** @type {any} */ (globalThis).ClipboardItem;
  if (!nav || !nav.clipboard || typeof nav.clipboard.write !== "function" || !ClipboardItemCtor) {
    throw new CapabilityError("unavailable", "clipboard image write is not available");
  }
  const mimeType = args.mime_type || "image/png";
  const blob = new Blob([b64ToBytes(args.data_base64)], { type: mimeType });
  try {
    const item = new ClipboardItemCtor({ [mimeType]: blob });
    await nav.clipboard.write([item]);
    return {};
  } catch (err) {
    throw new CapabilityError("permission_denied", err && err.message);
  }
}
