// native/compact.js — fetch a compact model's bytes for the Python reader.
//
// The compact format (`.tmc`) exists to run a tabular model with no inference
// runtime at all: onnxruntime-web is 13.96 MB of WebAssembly (3.58 MB gzipped)
// and a linear model is 660 bytes, so for an app whose only model is tabular the
// runtime *is* the download. The reader is `tempestweb/tabular/compact.py` — a
// dot product and a chain of comparisons, in Python.
//
// So this capability moves bytes and nothing else: Python cannot fetch, and the
// bytes have to arrive somehow. They come through the same asset cache
// `native/onnx.js` uses, so a model downloads once per version rather than once
// per session, and concurrent loads of the same URL are deduplicated.
//
// Base64 is the wire form every binary payload here uses (see `Tensor` in
// native/onnx.js), so the reader decodes with `base64.b64decode` and no new
// convention enters the bridge.

import { CapabilityError } from "./index.js";
import { ensureCached } from "../offline/asset-cache.js";

/**
 * Encode raw bytes into a base64 string.
 * @param {ArrayBuffer} buffer
 * @returns {string}
 */
function toBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

/**
 * Fetch a compact model through the shared asset cache.
 *
 * Degrades to a plain fetch when Cache Storage is missing or the cache write
 * fails: a cold cache is slower, not broken — the same rule `native/onnx.js`
 * follows.
 *
 * @param {{model_url: string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{bytes: string, size: number}>} The model as base64 plus its byte length.
 * @throws {CapabilityError} model_load — when the model cannot be downloaded.
 */
export async function compactLoad(args, deps) {
  const url = (args && args.model_url) || "";
  if (!url) throw new CapabilityError("model_load", "compact.load needs a model_url");

  const fetcher = (deps && deps.fetch) || globalThis.fetch;
  let response = null;
  try {
    response = await ensureCached(url, {
      caches: deps && /** @type {any} */ (deps).caches,
      fetch: deps && deps.fetch,
    });
  } catch {
    response = null;
  }
  if (!response || !response.ok) {
    try {
      response = await fetcher(url);
    } catch (error) {
      const detail = String((error && error.message) || error);
      throw new CapabilityError("model_load", `compact model fetch failed: ${url} (${detail})`);
    }
  }
  if (!response || !response.ok) {
    const status = response ? response.status : 0;
    throw new CapabilityError("model_load", `compact model fetch failed (${status}): ${url}`);
  }

  const buffer = await response.arrayBuffer();
  return { bytes: toBase64(buffer), size: buffer.byteLength };
}
