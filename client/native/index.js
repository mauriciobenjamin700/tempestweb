// native/index.js — the browser side of the tempestweb native capability seam.
//
// Python (Mode A in-process via Pyodide FFI, or Mode B over WS/SSE) sends a
// `native_call` envelope; this router runs the matching Web API and resolves a
// `native_result`. The SAME glue serves both modes — only how the envelope
// reaches it differs (FFIBridge vs ProxyBridge on the Python side). See
// ../../docs/contract.md and ../../tempestweb/native/dispatch.py.
//
// Pure JS, no build step. The Web APIs are reached through an injectable `deps`
// object (default: the live browser globals) so the router is unit-testable under
// jsdom with mocked fetch / navigator / Notification / Audio.

import { httpRequest, httpUpload } from "./http.js";
import { audioPlay, audioStop } from "./audio.js";
import { shareIsSupported, shareShare } from "./share.js";
import { geolocationGet } from "./geolocation.js";
import { clipboardRead, clipboardWrite } from "./clipboard.js";
import { storageGet, storageList, storagePut, storageRemove } from "./storage.js";
import { cookiesAll, cookiesGet, cookiesRemove, cookiesSet } from "./cookies.js";
import { cameraCapture } from "./camera.js";
import { onnxLoad, onnxRun } from "./onnx.js";
import { fileSave, filePick } from "./file.js";
import { installState, installPrompt } from "./install.js";
import {
  offlineEnqueue,
  offlinePending,
  offlineReplay,
  offlineSize,
} from "./offline.js";
import {
  notificationsNotify,
  notificationsRequestPermission,
  notificationsSubscribe,
  notificationsUnsubscribe,
} from "./notifications.js";

/**
 * @typedef {Object} NativeCall
 * @property {"native_call"} kind
 * @property {string} call_id     Correlation id echoed back in the result.
 * @property {string} capability  Dotted capability name, e.g. "geolocation.get".
 * @property {Object} args        JSON-able arguments for the capability.
 */

/**
 * @typedef {Object} NativeResult
 * @property {string} call_id     The matching call's id.
 * @property {boolean} ok         Whether the capability succeeded.
 * @property {Object} [value]     The typed result payload when ok.
 * @property {string} [error]     A machine-readable error code when not ok.
 * @property {string} [message]   Optional human-readable detail when not ok.
 */

/**
 * @typedef {Object} NativeDeps
 * Browser capabilities, injected so the router is testable under jsdom.
 * @property {typeof fetch} [fetch]
 * @property {Navigator} [navigator]
 * @property {typeof Notification} [Notification]
 * @property {typeof Audio} [Audio]
 * @property {Storage} [localStorage]
 * @property {Document} [document]
 * @property {Object} [store]   Owner-scoped IndexedDB store (T9/P2), optional.
 */

/**
 * The capability registry: dotted name -> async handler `(args, deps) -> value`.
 * A handler returns the result `value` on success or throws on failure; the
 * router turns a throw into a `{ ok: false, error }` result.
 * @type {Record<string, (args: Object, deps: NativeDeps) => Promise<Object>>}
 */
export const HANDLERS = {
  "http.request": httpRequest,
  "http.upload": httpUpload,
  "audio.play": audioPlay,
  "audio.stop": audioStop,
  "share.is_supported": shareIsSupported,
  "share.share": shareShare,
  "geolocation.get": geolocationGet,
  "clipboard.read": clipboardRead,
  "clipboard.write": clipboardWrite,
  "storage.put": storagePut,
  "storage.get": storageGet,
  "storage.list": storageList,
  "storage.remove": storageRemove,
  "cookies.get": cookiesGet,
  "cookies.set": cookiesSet,
  "cookies.remove": cookiesRemove,
  "cookies.all": cookiesAll,
  "camera.capture": cameraCapture,
  "onnx.load": onnxLoad,
  "onnx.run": onnxRun,
  "file.save": fileSave,
  "file.pick": filePick,
  "install.state": installState,
  "install.prompt": installPrompt,
  "offline.enqueue": offlineEnqueue,
  "offline.pending": offlinePending,
  "offline.replay": offlineReplay,
  "offline.size": offlineSize,
  "notifications.notify": notificationsNotify,
  "notifications.request_permission": notificationsRequestPermission,
  "notifications.subscribe": notificationsSubscribe,
  "notifications.unsubscribe": notificationsUnsubscribe,
};

/**
 * Resolve the live browser globals as the default dependency set.
 * @returns {NativeDeps}
 */
export function browserDeps() {
  const g = /** @type {any} */ (globalThis);
  return {
    fetch: g.fetch ? g.fetch.bind(g) : undefined,
    navigator: g.navigator,
    Notification: g.Notification,
    Audio: g.Audio,
    localStorage: g.localStorage,
    document: g.document,
  };
}

/** @deprecated internal alias retained for the dispatch default. */
const defaultDeps = browserDeps;

/**
 * A typed error a capability handler can throw to set the result error code.
 */
export class CapabilityError extends Error {
  /**
   * @param {string} code     Machine-readable error code (e.g. "permission_denied").
   * @param {string} [message] Human-readable detail.
   */
  constructor(code, message = "") {
    super(message || code);
    /** @type {string} */
    this.code = code;
  }
}

/**
 * Run one `native_call` and produce its `native_result`.
 *
 * Never throws: any handler failure (unknown capability, thrown error, rejected
 * promise) becomes a `{ ok: false, error }` result so the Python side always
 * resolves its pending future.
 *
 * @param {NativeCall} envelope The native_call envelope from Python.
 * @param {NativeDeps} [deps]   Injected Web APIs (defaults to live globals).
 * @returns {Promise<NativeResult>} The native_result envelope.
 */
export async function dispatch(envelope, deps = defaultDeps()) {
  const callId = envelope.call_id;
  const handler = HANDLERS[envelope.capability];
  if (!handler) {
    return {
      call_id: callId,
      ok: false,
      error: "unknown_capability",
      message: envelope.capability,
    };
  }
  try {
    const value = await handler(envelope.args || {}, deps);
    return { call_id: callId, ok: true, value: value || {} };
  } catch (err) {
    const code = err instanceof CapabilityError ? err.code : "error";
    const message = err && err.message ? String(err.message) : "";
    return { call_id: callId, ok: false, error: code, message };
  }
}

/**
 * Install the in-process dispatch entry point used by the Mode A FFIBridge.
 *
 * Pyodide proxies `window.__tempestweb_native__(envelope)` to the Python
 * FFIBridge; this exposes it. In Mode B the transport calls {@link dispatch}
 * directly on each incoming `native_call` frame and posts the result back.
 *
 * @param {Object} [target]   The object to attach to (defaults to globalThis).
 * @param {NativeDeps} [deps] Injected Web APIs (defaults to live globals).
 */
export function installNativeBridge(target = globalThis, deps = undefined) {
  target.__tempestweb_native__ = (envelope) => dispatch(envelope, deps);
}
