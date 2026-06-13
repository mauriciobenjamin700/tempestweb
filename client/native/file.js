// native/file.js — deliver a generated file via Web Share or anchor download.
//
// The browser has no synchronous "save file" call. A blob built in Python (a ZIP,
// a spreadsheet, an image) crosses the bridge as base64 and is delivered one of
// two ways: navigator.share({files:[...]}) when the Web Share API accepts files
// (typical on mobile), otherwise a programmatic <a download> click (desktop).
// The chosen path is reported back so the caller knows what happened.

import { CapabilityError } from "./index.js";

/**
 * Decode a base64 string into a Uint8Array of its raw bytes.
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
 * Share or download a generated file.
 * @param {{filename:string,data_base64:string,mime:string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{method:string,shared:boolean}>}
 * @throws {CapabilityError} share_cancelled / unavailable.
 */
export async function fileSave(args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  const doc = deps.document || /** @type {any} */ (globalThis).document;
  const mime = args.mime || "application/octet-stream";
  const filename = args.filename || "download";
  const bytes = b64ToBytes(args.data_base64);
  const blob = new Blob([bytes], { type: mime });

  // Prefer the Web Share API with a File when the platform supports sharing files.
  const FileCtor = /** @type {any} */ (globalThis).File;
  if (nav && typeof nav.share === "function" && FileCtor) {
    try {
      const file = new FileCtor([blob], filename, { type: mime });
      if (!nav.canShare || nav.canShare({ files: [file] })) {
        await nav.share({ files: [file], title: filename });
        return { method: "share", shared: true };
      }
    } catch (err) {
      // AbortError means the user dismissed the share sheet on purpose; surface it
      // rather than silently downloading behind their back.
      if (err && err.name === "AbortError") {
        throw new CapabilityError("share_cancelled", "share was cancelled");
      }
      // Any other share failure falls through to the download path below.
    }
  }

  if (!doc || typeof doc.createElement !== "function") {
    throw new CapabilityError("unavailable", "no document to anchor a download");
  }
  const url = URL.createObjectURL(blob);
  try {
    const anchor = doc.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    if (doc.body && doc.body.appendChild) doc.body.appendChild(anchor);
    anchor.click();
    if (anchor.remove) anchor.remove();
  } finally {
    URL.revokeObjectURL(url);
  }
  return { method: "download", shared: false };
}
