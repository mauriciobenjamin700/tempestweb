// native/recorder.js — MediaRecorder glue for audio / screen capture.
//
// A recording is stateful (a live MediaRecorder + its stream + the collected
// chunks), none of which is JSON-able, so we hold each session in a module-level
// registry keyed by a generated id and return only the id across the seam;
// `stop` looks it back up, assembles the blob, and base64-encodes the result.

import { CapabilityError } from "./index.js";

/**
 * Live recording sessions, keyed by the id handed back to Python.
 * @type {Map<string, {recorder:any, chunks:Array<any>, stream:any}>}
 */
const _sessions = new Map();

/** Monotonic id counter — never Math.random/Date, so ids are stable in tests. */
let _counter = 0;

/**
 * Start a media recording (microphone audio, or the screen) and return its id.
 * @param {{source?:string, mime_type?:string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{id:string}>}
 * @throws {CapabilityError} unavailable / permission_denied.
 */
export async function recorderStart(args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  const MediaRecorderCtor = deps.MediaRecorder || /** @type {any} */ (globalThis).MediaRecorder;
  if (!nav || !nav.mediaDevices || !MediaRecorderCtor) {
    throw new CapabilityError("unavailable", "media recording is not available");
  }
  let stream;
  try {
    if (args.source === "screen") {
      if (typeof nav.mediaDevices.getDisplayMedia !== "function") {
        throw new CapabilityError("unavailable", "screen capture is not available");
      }
      stream = await nav.mediaDevices.getDisplayMedia({ video: true });
    } else {
      if (typeof nav.mediaDevices.getUserMedia !== "function") {
        throw new CapabilityError("unavailable", "microphone capture is not available");
      }
      stream = await nav.mediaDevices.getUserMedia({ audio: true });
    }
  } catch (err) {
    if (err instanceof CapabilityError) throw err;
    const code = err && err.name === "NotAllowedError" ? "permission_denied" : "unavailable";
    throw new CapabilityError(code, err && err.message);
  }

  const recorder = new MediaRecorderCtor(
    stream,
    args.mime_type ? { mimeType: args.mime_type } : undefined,
  );
  const chunks = [];
  recorder.ondataavailable = (event) => {
    if (event && event.data) chunks.push(event.data);
  };
  recorder.start();

  _counter += 1;
  const id = `recorder-${_counter}`;
  _sessions.set(id, { recorder, chunks, stream });
  return { id };
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
    reader.onerror = () => reject(new CapabilityError("read_failed", "failed to read recording"));
    reader.readAsDataURL(blob);
  });
}

/**
 * Stop a recording by id and return its bytes as base64.
 * @param {{id:string}} args
 * @param {import("./index.js").NativeDeps} _deps
 * @returns {Promise<{data_base64:string, mime_type:string, size:number}>}
 * @throws {CapabilityError} not_found when the id is unknown.
 */
export async function recorderStop(args, _deps) {
  const session = _sessions.get(args.id);
  if (!session) {
    throw new CapabilityError("not_found", `no recording for id ${args.id}`);
  }
  const { recorder, chunks, stream } = session;
  await new Promise((resolve) => {
    recorder.onstop = () => resolve();
    recorder.stop();
  });
  const type = (chunks[0] && chunks[0].type) || recorder.mimeType || "application/octet-stream";
  const blob = new Blob(chunks, { type });
  for (const track of stream.getTracks ? stream.getTracks() : []) {
    if (typeof track.stop === "function") track.stop();
  }
  const data_base64 = await blobToBase64(blob);
  _sessions.delete(args.id);
  return { data_base64, mime_type: blob.type, size: blob.size };
}
