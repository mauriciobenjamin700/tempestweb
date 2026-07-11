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
  share: Object.freeze({
    /** Whether the OS share sheet is available. @returns {Promise<boolean>} */
    is_supported: () => call("share.is_supported", {}).then((r) => r.supported),
    /**
     * Open the OS share sheet (falls back gracefully when unsupported).
     * @param {{title?: string, text?: string, url?: string,
     *          files?: Array<Object>}} [opts]
     * @returns {Promise<{outcome: string}>}
     */
    share: (opts = {}) =>
      call("share.share", {
        title: opts.title ?? "",
        text: opts.text ?? "",
        url: opts.url ?? "",
        files: opts.files ?? [],
      }),
  }),
  audio: Object.freeze({
    /**
     * Play a short sound on a channel.
     * @param {string} src  The audio asset URL.
     * @param {{volume?: number, channel?: string}} [opts]
     * @returns {Promise<Object>}  {played, blocked}.
     */
    play: (src, opts = {}) =>
      call("audio.play", {
        src,
        volume: opts.volume ?? 1.0,
        channel: opts.channel ?? "default",
      }),
    /** Stop a channel's sound. @returns {Promise<void>} */
    stop: (channel = "default") => call("audio.stop", { channel }),
  }),
  file: Object.freeze({
    /**
     * Pick a file (opens the native picker).
     * @param {{accept?: string, capture?: ?string}} [opts]
     * @returns {Promise<Object>}  The picked file descriptor.
     */
    pick: (opts = {}) =>
      call("file.pick", { accept: opts.accept ?? "image/*", capture: opts.capture ?? null }),
    /**
     * Share or download a generated file.
     * @param {string} filename  The suggested file name.
     * @param {string} dataBase64  The base64-encoded file bytes.
     * @param {{mimeType?: string}} [opts]
     * @returns {Promise<Object>}  How the file was delivered.
     */
    save: (filename, dataBase64, opts = {}) =>
      call("file.save", {
        filename,
        data_base64: dataBase64,
        mime_type: opts.mimeType ?? "application/octet-stream",
      }),
  }),
  notifications: Object.freeze({
    /** Show a notification. @returns {Promise<void>} */
    notify: (title, opts = {}) =>
      call("notifications.notify", { title, body: opts.body ?? "" }),
    /** Request notification permission. @returns {Promise<string>} */
    request_permission: () =>
      call("notifications.request_permission", {}).then((r) => r.permission),
    /**
     * WebPush support + current permission, WITHOUT prompting — decide whether
     * to show an "enable notifications" button before calling `subscribe`.
     * @returns {Promise<{supported: boolean, permission: string}>}
     */
    push_state: () => call("notifications.push_state", {}),
    /**
     * Subscribe to WebPush; returns the raw browser subscription JSON to POST to
     * your own backend (e.g. via `native.http` / `native.offline`).
     * @param {string} vapid_public_key  The base64url VAPID application server key.
     * @returns {Promise<Object>}  The PushSubscription JSON.
     */
    subscribe: (vapid_public_key) =>
      call("notifications.subscribe", { vapid_public_key }),
    /** Cancel the push subscription. @returns {Promise<boolean>} */
    unsubscribe: () =>
      call("notifications.unsubscribe", {}).then((r) => r.unsubscribed),
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
  install: Object.freeze({
    /**
     * Report the PWA install state.
     * @returns {Promise<{can_install: boolean, installed: boolean}>}
     */
    state: () => call("install.state", {}),
    /**
     * Fire the stashed native install prompt (call after a user gesture).
     * @returns {Promise<"accepted"|"dismissed"|"unavailable">}  The outcome.
     */
    prompt: () => call("install.prompt", {}).then((r) => r.outcome),
  }),
  offline: Object.freeze({
    /**
     * Enqueue a mutation for durable, replay-on-reconnect delivery.
     * @param {string} method  HTTP method ("POST"/"PUT"/"PATCH"/"DELETE").
     * @param {string} url  Target URL.
     * @param {*} [body]  JSON-able request body.
     * @param {{idempotency_key?: string, owner?: string}} [opts]
     * @returns {Promise<Object>}  The enqueued mutation.
     */
    enqueue: (method, url, body = null, opts = {}) =>
      call("offline.enqueue", {
        method,
        url,
        body,
        idempotency_key: opts.idempotency_key ?? null,
        owner: opts.owner ?? null,
      }),
    /** Pending mutations (oldest first). @returns {Promise<Object[]>} */
    pending: (owner = null) =>
      call("offline.pending", { owner }).then((r) => r.mutations),
    /** Pending-mutation count. @returns {Promise<number>} */
    size: (owner = null) => call("offline.size", { owner }).then((r) => r.size),
    /** Replay the queue now. @returns {Promise<{sent:number, remaining:number}>} */
    replay: (owner = null) => call("offline.replay", { owner }),
  }),
});
