// native/filesystem.js — File System Access API glue (open/write/save).
//
// The API hands back live `FileSystemFileHandle` objects, which are not JSON-able
// and must survive between an open/save and a later write. We hold each handle in
// a module-level registry keyed by a generated id and return only the id across
// the seam; `write_file` looks the handle back up to stream bytes into it.

import { CapabilityError } from "./index.js";

/**
 * Live file handles, keyed by the id handed back to Python.
 * @type {Map<string, any>}
 */
const _handles = new Map();

/** Monotonic id counter — never Math.random/Date, so ids are stable in tests. */
let _counter = 0;

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
 * Read a base64 (no data-URL prefix) encoding of a Blob.
 * @param {Blob} blob
 * @returns {Promise<string>}
 */
function blobToBase64(blob) {
  const FileReaderCtor = /** @type {any} */ (globalThis).FileReader;
  return new Promise((resolve, reject) => {
    const reader = new FileReaderCtor();
    reader.onload = () => {
      const result = String(reader.result || "");
      const comma = result.indexOf(",");
      resolve(comma >= 0 ? result.slice(comma + 1) : result);
    };
    reader.onerror = () => reject(new CapabilityError("read_failed", "failed to read file"));
    reader.readAsDataURL(blob);
  });
}

/**
 * Open one or more files via the native picker, returning their bytes as base64.
 * @param {{accept?:Object, multiple?:boolean}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{files:Array<{id:string, name:string, mime_type:string, data_base64:string}>}>}
 * @throws {CapabilityError} unavailable / cancelled.
 */
export async function filesystemOpenFile(args, deps) {
  const win = deps.window || /** @type {any} */ (globalThis);
  if (!win || typeof win.showOpenFilePicker !== "function") {
    throw new CapabilityError("unavailable", "the File System Access API is not available");
  }
  const options = { multiple: !!args.multiple };
  if (args.accept && Object.keys(args.accept).length > 0) {
    options.types = [{ accept: args.accept }];
  }
  let handles;
  try {
    handles = await win.showOpenFilePicker(options);
  } catch (err) {
    if (err && err.name === "AbortError") {
      throw new CapabilityError("cancelled", "the file picker was dismissed");
    }
    throw new CapabilityError("unavailable", err && err.message);
  }
  const files = [];
  for (const handle of handles) {
    _counter += 1;
    const id = `filesystem-${_counter}`;
    _handles.set(id, handle);
    const file = await handle.getFile();
    const data_base64 = await blobToBase64(file);
    files.push({
      id,
      name: file.name || handle.name || "",
      mime_type: file.type || "application/octet-stream",
      data_base64,
    });
  }
  return { files };
}

/**
 * Write base64 bytes back to a previously opened file handle.
 * @param {{id:string, data_base64:string}} args
 * @param {import("./index.js").NativeDeps} _deps
 * @returns {Promise<{written:boolean}>}
 * @throws {CapabilityError} not_found when the id is unknown.
 */
export async function filesystemWriteFile(args, _deps) {
  const handle = _handles.get(args.id);
  if (!handle) {
    throw new CapabilityError("not_found", `no file handle for id ${args.id}`);
  }
  const writable = await handle.createWritable();
  await writable.write(new Blob([b64ToBytes(args.data_base64)]));
  await writable.close();
  return { written: true };
}

/**
 * Save bytes to a new file via the native save dialog, returning its handle id.
 * @param {{filename?:string, data_base64:string, mime_type?:string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{id:string, name:string}>}
 * @throws {CapabilityError} unavailable / cancelled.
 */
export async function filesystemSaveFile(args, deps) {
  const win = deps.window || /** @type {any} */ (globalThis);
  if (!win || typeof win.showSaveFilePicker !== "function") {
    throw new CapabilityError("unavailable", "the File System Access API is not available");
  }
  let handle;
  try {
    handle = await win.showSaveFilePicker({ suggestedName: args.filename || "download" });
  } catch (err) {
    if (err && err.name === "AbortError") {
      throw new CapabilityError("cancelled", "the save dialog was dismissed");
    }
    throw new CapabilityError("unavailable", err && err.message);
  }
  const writable = await handle.createWritable();
  await writable.write(
    new Blob([b64ToBytes(args.data_base64)], {
      type: args.mime_type || "application/octet-stream",
    }),
  );
  await writable.close();
  _counter += 1;
  const id = `filesystem-${_counter}`;
  _handles.set(id, handle);
  return { id, name: handle.name || args.filename || "" };
}
