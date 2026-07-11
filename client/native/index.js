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
import {
  clipboardRead,
  clipboardReadImage,
  clipboardWrite,
  clipboardWriteImage,
} from "./clipboard.js";
import { vibrationVibrate } from "./vibration.js";
import { badgeClear, badgeSet } from "./badge.js";
import { wakelockRelease, wakelockRequest } from "./wakelock.js";
import { fullscreenEnter, fullscreenExit, fullscreenState } from "./fullscreen.js";
import { visibilityState } from "./visibility.js";
import { orientationLock, orientationState, orientationUnlock } from "./orientation.js";
import { quotaEstimate, quotaPersist, quotaPersisted } from "./quota.js";
import { networkState } from "./network.js";
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
  notificationsPushState,
  notificationsRequestPermission,
  notificationsSubscribe,
  notificationsUnsubscribe,
} from "./notifications.js";
import { speechCancel, speechSpeak, speechVoices } from "./speech.js";
import { recorderStart, recorderStop } from "./recorder.js";
import {
  filesystemOpenFile,
  filesystemSaveFile,
  filesystemWriteFile,
} from "./filesystem.js";
import { bgsyncRegister, bgsyncRegisterPeriodic } from "./bgsync.js";
import { tabsBroadcast, tabsLock, tabsUnlock } from "./tabs.js";
import { webauthnCreate, webauthnGet, webauthnGetOtp } from "./webauthn.js";
import {
  bluetoothIsSupported,
  bluetoothRead,
  bluetoothRequest,
  bluetoothWrite,
} from "./bluetooth.js";
import { contactsIsSupported, contactsSelect } from "./contacts.js";
import { eyedropperOpen } from "./eyedropper.js";
import { gamepadState } from "./gamepad.js";
import { hidIsSupported, hidRequest } from "./hid.js";
import { midiIsSupported, midiRequestAccess, midiSend } from "./midi.js";
import { nfcIsSupported, nfcWrite } from "./nfc.js";
import { paymentIsSupported, paymentRequest } from "./payment.js";
import { pipExit, pipRequest } from "./pip.js";
import { pointerlockExit, pointerlockRequest } from "./pointerlock.js";
import { serialIsSupported, serialRequest } from "./serial.js";
import { usbIsSupported, usbRequest } from "./usb.js";
import { webaudioTone } from "./webaudio.js";

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
 * @property {Screen} [screen]  Screen object (orientation), injected for testing.
 * @property {Window} [window]  Window object (File System Access pickers).
 * @property {Object} [speechSynthesis]  Speech synthesis controller.
 * @property {Function} [SpeechSynthesisUtterance]  Utterance constructor.
 * @property {Function} [MediaRecorder]  MediaRecorder constructor.
 * @property {Function} [BroadcastChannel]  BroadcastChannel constructor.
 * @property {Function} [AudioContext]  AudioContext constructor (Web Audio tone).
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
  "clipboard.read_image": clipboardReadImage,
  "clipboard.write": clipboardWrite,
  "clipboard.write_image": clipboardWriteImage,
  "vibration.vibrate": vibrationVibrate,
  "badge.set": badgeSet,
  "badge.clear": badgeClear,
  "wakelock.request": wakelockRequest,
  "wakelock.release": wakelockRelease,
  "fullscreen.enter": fullscreenEnter,
  "fullscreen.exit": fullscreenExit,
  "fullscreen.state": fullscreenState,
  "visibility.state": visibilityState,
  "orientation.lock": orientationLock,
  "orientation.unlock": orientationUnlock,
  "orientation.state": orientationState,
  "quota.estimate": quotaEstimate,
  "quota.persist": quotaPersist,
  "quota.persisted": quotaPersisted,
  "network.state": networkState,
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
  "notifications.push_state": notificationsPushState,
  "notifications.request_permission": notificationsRequestPermission,
  "notifications.subscribe": notificationsSubscribe,
  "notifications.unsubscribe": notificationsUnsubscribe,
  "speech.speak": speechSpeak,
  "speech.cancel": speechCancel,
  "speech.voices": speechVoices,
  "recorder.start": recorderStart,
  "recorder.stop": recorderStop,
  "filesystem.open_file": filesystemOpenFile,
  "filesystem.write_file": filesystemWriteFile,
  "filesystem.save_file": filesystemSaveFile,
  "bgsync.register": bgsyncRegister,
  "bgsync.register_periodic": bgsyncRegisterPeriodic,
  "tabs.broadcast": tabsBroadcast,
  "tabs.lock": tabsLock,
  "tabs.unlock": tabsUnlock,
  "webauthn.create": webauthnCreate,
  "webauthn.get": webauthnGet,
  "webauthn.get_otp": webauthnGetOtp,
  "bluetooth.is_supported": bluetoothIsSupported,
  "bluetooth.request": bluetoothRequest,
  "bluetooth.read": bluetoothRead,
  "bluetooth.write": bluetoothWrite,
  "contacts.is_supported": contactsIsSupported,
  "contacts.select": contactsSelect,
  "eyedropper.open": eyedropperOpen,
  "gamepad.state": gamepadState,
  "hid.is_supported": hidIsSupported,
  "hid.request": hidRequest,
  "midi.is_supported": midiIsSupported,
  "midi.request_access": midiRequestAccess,
  "midi.send": midiSend,
  "nfc.is_supported": nfcIsSupported,
  "nfc.write": nfcWrite,
  "payment.is_supported": paymentIsSupported,
  "payment.request": paymentRequest,
  "pip.request": pipRequest,
  "pip.exit": pipExit,
  "pointerlock.request": pointerlockRequest,
  "pointerlock.exit": pointerlockExit,
  "serial.is_supported": serialIsSupported,
  "serial.request": serialRequest,
  "usb.is_supported": usbIsSupported,
  "usb.request": usbRequest,
  "webaudio.tone": webaudioTone,
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
    screen: g.screen,
    window: g.window || g,
    speechSynthesis: g.speechSynthesis,
    SpeechSynthesisUtterance: g.SpeechSynthesisUtterance,
    MediaRecorder: g.MediaRecorder,
    BroadcastChannel: g.BroadcastChannel,
    AudioContext: g.AudioContext || g.webkitAudioContext,
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
