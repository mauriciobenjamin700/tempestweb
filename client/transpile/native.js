// native.js — Mode C native-capability facade (in-process, no Python, no bridge).
//
// In Modes A/B a Python `await native.http.request(...)` crosses the NativeBridge
// seam (FFI or WebSocket) into client/native/*.js. Mode C has no Python: the
// transpiled app calls this facade directly, which routes to the SAME browser
// glue via the shared `dispatch` registry (client/native/index.js). Zero Web-API
// reimplementation — only the seam changes.
//
// The method names mirror the Python API (`native.storage.list_keys`,
// `native.geolocation.get_position`) so transpiled calls map one-to-one. Each
// returns a Promise of the capability's value and throws a NativeError on failure
// (mirroring the Python awaitable that raises).
//
// See docs/native-modo-c.md and docs/contract.md.

import { browserDeps, dispatch } from "../native/index.js";
import { createIdbKv } from "../native/idb-kv.js";

// The `storage` capability persists over IndexedDB when available (injected as
// `deps.store`), falling back to localStorage otherwise. Built once, lazily.
let _store;
/** @returns {?import("../native/idb-kv.js").KeyValueStore} */
function idbStore() {
  if (_store === undefined) {
    _store = createIdbKv();
  }
  return _store;
}

/**
 * An error thrown when a native capability fails (mirrors Python's NativeError).
 */
export class NativeError extends Error {
  /**
   * @param {string} code  The machine-readable error code (e.g. "not_found").
   * @param {string} [message]  A human-readable detail.
   */
  constructor(code, message) {
    super(message ? `${code}: ${message}` : code);
    this.name = "NativeError";
    this.code = code;
  }
}

/**
 * Dispatch a capability in-process and unwrap its result.
 *
 * @param {string} capability  The dotted capability name (e.g. "http.request").
 * @param {Object} args        The JSON-able capability arguments.
 * @returns {Promise<*>}        The capability's value.
 * @throws {NativeError}        When the capability reports `ok: false`.
 */
async function call(capability, args) {
  // Inject the IndexedDB KV store so `storage.*` persists over IndexedDB; the
  // other capabilities ignore it. Falls back to localStorage when IDB is absent.
  const deps = browserDeps();
  const store = idbStore();
  if (store !== null) {
    deps.store = store;
  }
  const result = await dispatch({ capability, args }, deps);
  if (!result.ok) {
    throw new NativeError(result.error, result.message);
  }
  return result.value;
}

/**
 * The native capability namespace — the Mode C mirror of `tempestweb.native`.
 * @type {Object}
 */
export const native = Object.freeze({
  http: Object.freeze({
    /**
     * Perform an HTTP request.
     * @param {string} method  The HTTP method.
     * @param {string} url  The request URL.
     * @param {{json?: *, headers?: Object<string,string>}} [opts]  Body + headers.
     * @returns {Promise<Object>}  The parsed HttpResponse ({status, json, ...}).
     */
    request: (method, url, opts = {}) =>
      call("http.request", {
        method,
        url,
        json: opts.json ?? null,
        headers: opts.headers ?? {},
      }),
    /**
     * Upload a file payload.
     * @param {string} url  The upload URL.
     * @param {Object} file  The file payload.
     * @param {{headers?: Object<string,string>}} [opts]
     * @returns {Promise<Object>}
     */
    upload: (url, file, opts = {}) =>
      call("http.upload", { url, file, headers: opts.headers ?? {} }),
  }),
  storage: Object.freeze({
    /** Persist a value under a key (over IndexedDB). @returns {Promise<void>} */
    put: (name, content) => call("storage.put", { name, content }),
    /** Read a value by key. @returns {Promise<string>} */
    get: (name) => call("storage.get", { name }).then((r) => r.content),
    /** Remove a value by key. @returns {Promise<void>} */
    remove: (name) => call("storage.remove", { name }),
    /** List every stored key. @returns {Promise<string[]>} */
    list_keys: () => call("storage.list", {}).then((r) => r.keys),
  }),
  clipboard: Object.freeze({
    /** Read the clipboard text. @returns {Promise<string>} */
    read: () => call("clipboard.read", {}).then((r) => r.text),
    /** Write text to the clipboard. @returns {Promise<void>} */
    write: (text) => call("clipboard.write", { text }),
  }),
  geolocation: Object.freeze({
    /**
     * Read the current position.
     * @param {boolean} [high_accuracy]
     * @returns {Promise<Object>}  {latitude, longitude, accuracy}.
     */
    get_position: (high_accuracy = true) =>
      call("geolocation.get", { high_accuracy }),
  }),
  cookies: Object.freeze({
    /** Read a cookie by name. @returns {Promise<?string>} */
    get: (name) => call("cookies.get", { name }).then((r) => r.value),
    /** Set a cookie. @returns {Promise<void>} */
    set: (name, value, opts = {}) =>
      call("cookies.set", {
        name,
        value,
        max_age: opts.max_age ?? null,
        path: opts.path ?? "/",
        same_site: opts.same_site ?? "Lax",
        secure: opts.secure ?? false,
      }),
    /** Remove a cookie. @returns {Promise<void>} */
    remove: (name, opts = {}) =>
      call("cookies.remove", { name, path: opts.path ?? "/" }),
    /** Read every cookie as a name→value map. @returns {Promise<Object>} */
    all: () => call("cookies.all", {}),
  }),
});
