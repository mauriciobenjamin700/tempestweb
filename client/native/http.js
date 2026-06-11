// native/http.js — browser fetch glue for the N0 http capability.
//
// The retry/backoff/poll POLICY lives in Python (tempestweb/native/http.py);
// this module performs exactly one round-trip per call. Each handler returns a
// plain object the Python `HttpResponse` model validates.

import { CapabilityError } from "./index.js";

/**
 * Normalize a `Headers`/object into a lower-cased plain object.
 * @param {Headers|Object|undefined} headers
 * @returns {Object.<string,string>}
 */
function headersToObject(headers) {
  /** @type {Object.<string,string>} */
  const out = {};
  if (!headers) return out;
  if (typeof headers.forEach === "function") {
    headers.forEach((v, k) => {
      out[String(k).toLowerCase()] = String(v);
    });
    return out;
  }
  for (const [k, v] of Object.entries(headers)) out[String(k).toLowerCase()] = String(v);
  return out;
}

/**
 * Parse a fetch Response into the wire shape of `HttpResponse`.
 * @param {Response} res
 * @returns {Promise<Object>}
 */
async function readResponse(res) {
  const text = await res.text();
  let json = null;
  const ctype = res.headers && res.headers.get ? res.headers.get("content-type") : "";
  if (ctype && ctype.includes("application/json") && text) {
    try {
      json = JSON.parse(text);
    } catch {
      json = null;
    }
  }
  return {
    status: res.status,
    ok: res.ok,
    headers: headersToObject(res.headers),
    text,
    json,
  };
}

/**
 * Perform a single HTTP request via `fetch`.
 *
 * @param {{method:string,url:string,json:*,headers:Object}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<Object>} The HttpResponse wire payload.
 * @throws {CapabilityError} `network` when fetch rejects (offline, CORS, ...).
 */
export async function httpRequest(args, deps) {
  if (!deps.fetch) throw new CapabilityError("unavailable", "fetch is not available");
  /** @type {RequestInit} */
  const init = { method: args.method || "GET", headers: { ...(args.headers || {}) } };
  if (args.json !== null && args.json !== undefined) {
    init.body = JSON.stringify(args.json);
    init.headers["content-type"] = init.headers["content-type"] || "application/json";
  }
  let res;
  try {
    res = await deps.fetch(args.url, init);
  } catch (err) {
    throw new CapabilityError("network", err && err.message ? err.message : "fetch failed");
  }
  return readResponse(res);
}

/**
 * Upload a file with progress, via XHR when available (for upload.onprogress),
 * falling back to a single `fetch` POST.
 *
 * @param {{url:string,file:Object,headers:Object}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<Object>} `{ progress:number[], response:HttpResponse }`.
 */
export async function httpUpload(args, deps) {
  const g = /** @type {any} */ (globalThis);
  const XHR = g.XMLHttpRequest;
  const body = JSON.stringify(args.file || {});
  if (!XHR) {
    if (!deps.fetch) throw new CapabilityError("unavailable", "no upload transport");
    const res = await deps.fetch(args.url, {
      method: "POST",
      headers: { "content-type": "application/json", ...(args.headers || {}) },
      body,
    });
    return { progress: [], response: await readResponse(res) };
  }
  /** @type {number[]} */
  const progress = [];
  return new Promise((resolve, reject) => {
    const xhr = new XHR();
    xhr.open("POST", args.url, true);
    for (const [k, v] of Object.entries(args.headers || {})) xhr.setRequestHeader(k, v);
    xhr.setRequestHeader("content-type", "application/json");
    if (xhr.upload) {
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && e.total > 0) progress.push(e.loaded / e.total);
      };
    }
    xhr.onload = () => {
      resolve({
        progress,
        response: {
          status: xhr.status,
          ok: xhr.status >= 200 && xhr.status < 300,
          headers: {},
          text: xhr.responseText || "",
          json: null,
        },
      });
    };
    xhr.onerror = () => reject(new CapabilityError("network", "upload failed"));
    xhr.send(body);
  });
}
