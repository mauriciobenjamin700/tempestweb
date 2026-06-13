// native/onnx.js — onnxruntime-web glue for the ONNX inference capability.
//
// `onnxruntime` (the CPython C-extension) has no Pyodide wheel, so Python in the
// browser can't run an ONNX graph in-process. This bridge runs the graph in JS via
// onnxruntime-web (the WASM build, loaded as a global `ort`), driven through the
// same native_call seam as every other capability. The Python caller does its
// numpy pre/post-processing and ships only the raw tensor execution across here.
//
// Tensors cross the wire as base64-encoded raw bytes + a shape + a dtype string.
// Sessions are compiled once on `onnx.load` and cached by an opaque id used by
// `onnx.run`. The wasm execution provider is forced by default (the web build is
// missing some kernels — e.g. Resize — under the WebGPU provider).

import { CapabilityError } from "./index.js";

/** @type {Map<string, any>} Compiled sessions keyed by their issued id. */
const SESSIONS = new Map();

/** Monotonic counter for session ids (kept simple; one document, one worker). */
let SESSION_SEQ = 0;

/**
 * onnxruntime-web dtype string -> the matching TypedArray constructor.
 * @type {Record<string, any>}
 */
const DTYPE_CTORS = {
  float32: Float32Array,
  float64: Float64Array,
  int32: Int32Array,
  int16: Int16Array,
  int8: Int8Array,
  uint8: Uint8Array,
  uint16: Uint16Array,
  int64: typeof BigInt64Array !== "undefined" ? BigInt64Array : undefined,
  uint64: typeof BigUint64Array !== "undefined" ? BigUint64Array : undefined,
  bool: Uint8Array,
};

/**
 * Resolve the onnxruntime-web entry point.
 * @param {import("./index.js").NativeDeps} deps
 * @returns {any}
 * @throws {CapabilityError} unavailable — when onnxruntime-web is not loaded.
 */
function resolveOrt(deps) {
  const ort = (deps && /** @type {any} */ (deps).ort) || /** @type {any} */ (globalThis).ort;
  if (!ort || !ort.InferenceSession || !ort.Tensor) {
    throw new CapabilityError("unavailable", "onnxruntime-web (global `ort`) is not loaded");
  }
  return ort;
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
 * Encode raw bytes (an ArrayBuffer view) into a base64 string.
 * @param {ArrayBufferView} view
 * @returns {string}
 */
function bytesToB64(view) {
  const bytes = new Uint8Array(view.buffer, view.byteOffset, view.byteLength);
  let binary = "";
  for (let i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

/**
 * Build an onnxruntime-web Tensor from the wire shape.
 * @param {any} ort
 * @param {{data_base64:string,dims:number[],dtype:string}} t
 * @returns {any}
 * @throws {CapabilityError} bad_dtype — for an unsupported dtype.
 */
function toOrtTensor(ort, t) {
  const ctor = DTYPE_CTORS[t.dtype];
  if (!ctor) throw new CapabilityError("bad_dtype", `unsupported dtype: ${t.dtype}`);
  const bytes = b64ToBytes(t.data_base64);
  // Reinterpret the raw bytes as the typed array (copy via the underlying buffer).
  const typed = new ctor(bytes.buffer, bytes.byteOffset, bytes.byteLength / ctor.BYTES_PER_ELEMENT);
  return new ort.Tensor(t.dtype, typed, t.dims || []);
}

/**
 * Serialize an onnxruntime-web Tensor back to the wire shape.
 * @param {any} tensor
 * @returns {{data_base64:string,dims:number[],dtype:string}}
 */
function fromOrtTensor(tensor) {
  return {
    data_base64: bytesToB64(tensor.data),
    dims: Array.from(tensor.dims || []),
    dtype: String(tensor.type),
  };
}

/**
 * Compile an ONNX model into a cached inference session.
 * @param {{model_url:string,providers:string[]}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{session_id:string,input_names:string[],output_names:string[]}>}
 * @throws {CapabilityError} model_load — when the model fails to download/compile.
 */
export async function onnxLoad(args, deps) {
  const ort = resolveOrt(deps);
  let session;
  try {
    session = await ort.InferenceSession.create(args.model_url, {
      executionProviders: args.providers && args.providers.length ? args.providers : ["wasm"],
    });
  } catch (err) {
    throw new CapabilityError("model_load", err && err.message);
  }
  SESSION_SEQ += 1;
  const sessionId = `onnx-${SESSION_SEQ}`;
  SESSIONS.set(sessionId, session);
  return {
    session_id: sessionId,
    input_names: Array.from(session.inputNames || []),
    output_names: Array.from(session.outputNames || []),
  };
}

/**
 * Run a cached session and return its outputs in wire shape.
 * @param {{session_id:string,feeds:Record<string,{data_base64:string,dims:number[],dtype:string}>}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{outputs:Record<string,{data_base64:string,dims:number[],dtype:string}>}>}
 * @throws {CapabilityError} not_found — unknown session; inference — run failure.
 */
export async function onnxRun(args, deps) {
  const ort = resolveOrt(deps);
  const session = SESSIONS.get(args.session_id);
  if (!session) throw new CapabilityError("not_found", `unknown session: ${args.session_id}`);

  const feeds = {};
  for (const [name, tensor] of Object.entries(args.feeds || {})) {
    feeds[name] = toOrtTensor(ort, tensor);
  }

  let results;
  try {
    results = await session.run(feeds);
  } catch (err) {
    throw new CapabilityError("inference", err && err.message);
  }

  const outputs = {};
  for (const name of session.outputNames || Object.keys(results)) {
    if (results[name]) outputs[name] = fromOrtTensor(results[name]);
  }
  return { outputs };
}
