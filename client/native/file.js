// native/file.js — file output (share/download) and input (pick).
//
// The browser has no synchronous file I/O. `file.save` delivers a blob built in
// Python via navigator.share({files:[...]}) (when the platform accepts files) or
// an <a download> click (desktop). `file.pick` opens a file input and reads the
// chosen file back as base64 — the gallery path the FilePicker widget can't carry
// (its event exposes only a uri/name, not bytes).

import { CapabilityError } from "./index.js";

/**
 * Open a native file picker and return the chosen file as base64.
 *
 * Both ways out of the dialog settle the promise. Dismissing it — the X, or Esc
 * — fires **`cancel`**, never `change`, so listening only for `change` left the
 * promise pending forever: in Mode B the `native_call` never came back, the
 * handler stayed parked on its `await`, and since a session dispatches events in
 * series the whole app went dead until a reload. Every exit also removes the
 * input, which used to leak one orphan `<input type="file">` per cancellation.
 *
 * The `change`-with-no-file branch is kept as well: it costs nothing and covers
 * a browser too old for `cancel` (added in Chrome 113, Firefox 118, Safari 16.4).
 *
 * @param {{accept?:string,capture?:string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{data_base64:string,mime:string,name:string}>}
 * @throws {CapabilityError} unavailable / cancelled / read_failed.
 */
export async function filePick(args, deps) {
  const doc = deps.document || /** @type {any} */ (globalThis).document;
  const FileReaderCtor = /** @type {any} */ (globalThis).FileReader;
  if (!doc || typeof doc.createElement !== "function" || !FileReaderCtor) {
    throw new CapabilityError("unavailable", "no document/FileReader to pick a file");
  }
  return await new Promise((resolve, reject) => {
    const input = doc.createElement("input");
    input.type = "file";
    input.accept = args.accept || "image/*";
    if (args.capture) input.capture = args.capture;
    input.style.position = "fixed";
    input.style.left = "-9999px";

    let done = false;

    /**
     * Detach the input, then settle. Guarded so a browser that fires both
     * `cancel` and `change` settles once and removes the node once.
     * @param {() => void} settle
     * @returns {void}
     */
    const finish = (settle) => {
      if (done) return;
      done = true;
      if (input.remove) input.remove();
      settle();
    };
    const cancelled = () =>
      finish(() => reject(new CapabilityError("cancelled", "no file selected")));

    input.oncancel = cancelled;
    input.onchange = () => {
      const file = input.files && input.files[0];
      if (!file) {
        cancelled();
        return;
      }
      const reader = new FileReaderCtor();
      reader.onload = () => {
        const result = String(reader.result || "");
        const comma = result.indexOf(",");
        finish(() =>
          resolve({
            data_base64: comma >= 0 ? result.slice(comma + 1) : result,
            mime: file.type || "application/octet-stream",
            name: file.name || "",
          }),
        );
      };
      reader.onerror = () =>
        finish(() => reject(new CapabilityError("read_failed", "failed to read file")));
      reader.readAsDataURL(file);
    };
    if (doc.body && doc.body.appendChild) doc.body.appendChild(input);
    input.click();
  });
}

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
 *
 * Prefers the Web Share API with a File when the platform supports sharing files,
 * and otherwise falls back to an <a download> click. If the user dismisses the
 * share sheet (AbortError) this surfaces share_cancelled rather than silently
 * downloading behind their back; any other share failure falls through to the
 * download path.
 *
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

  const FileCtor = /** @type {any} */ (globalThis).File;
  if (nav && typeof nav.share === "function" && FileCtor) {
    try {
      const file = new FileCtor([blob], filename, { type: mime });
      if (!nav.canShare || nav.canShare({ files: [file] })) {
        await nav.share({ files: [file], title: filename });
        return { method: "share", shared: true };
      }
    } catch (err) {
      if (err && err.name === "AbortError") {
        throw new CapabilityError("share_cancelled", "share was cancelled");
      }
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
