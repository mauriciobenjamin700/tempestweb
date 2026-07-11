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

import {
  browserDeps,
  dispatch,
  subscribeDispatch,
  unsubscribeDispatch,
} from "../native/index.js";
import { createIdbKv } from "../native/idb-kv.js";

// Monotonic local subscription counter (Mode C mints its own sub_id — no Python
// side to do it). Deterministic on purpose: no Date/Math.random.
let _subCounter = 0;

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
 * Subscribe to a streaming capability in-process and forward its events (T-EV).
 *
 * The Mode C mirror of `await native.geolocation.watch(...)`. Mints a local
 * `sub_id`, injects the same IndexedDB store `call()` does, and unwraps each
 * `{ event: <value> }` payload into `onEvent(<value>)`. `{error}` / `{done}`
 * frames are ignored here (the facade surfaces only positive updates).
 *
 * @param {string} capability  The dotted streaming capability (e.g. "geolocation.watch").
 * @param {Object} args        The JSON-able capability arguments.
 * @param {(value: *) => void} onEvent  Called with each unwrapped event value.
 * @returns {() => void}        Unsubscribe: stops delivery.
 */
function stream(capability, args, onEvent) {
  const deps = browserDeps();
  const store = idbStore();
  if (store !== null) {
    deps.store = store;
  }
  const sub_id = "s" + _subCounter++;
  subscribeDispatch(
    { sub_id, capability, args },
    (payload) => {
      if (payload.event !== undefined) onEvent(payload.event);
    },
    deps,
  );
  return () => unsubscribeDispatch(sub_id);
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
    /**
     * Read the first image on the clipboard as base64.
     * @returns {Promise<{data_base64:string, mime_type:string}>}
     */
    read_image: () => call("clipboard.read_image", {}),
    /**
     * Write an image (base64) to the clipboard.
     * @param {string} data_base64  The base64-encoded image bytes.
     * @param {string} mime_type  The image MIME type (e.g. "image/png").
     * @returns {Promise<void>}
     */
    write_image: (data_base64, mime_type) =>
      call("clipboard.write_image", { data_base64, mime_type }),
  }),
  geolocation: Object.freeze({
    /**
     * Read the current position.
     * @param {boolean} [high_accuracy]
     * @returns {Promise<Object>}  {latitude, longitude, accuracy}.
     */
    get_position: (high_accuracy = true) =>
      call("geolocation.get", { high_accuracy }),
    /**
     * Watch the device position, streaming each fix to `onEvent` (T-EV).
     * @param {(value: {latitude:number, longitude:number, accuracy:number,
     *                  altitude:number|null}) => void} onEvent
     * @param {{high_accuracy?: boolean}} [opts]
     * @returns {() => void}  Unsubscribe: stops the position watch.
     */
    watch: (onEvent, opts = {}) =>
      stream("geolocation.watch", { high_accuracy: opts.high_accuracy ?? true }, onEvent),
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
  vibration: Object.freeze({
    /**
     * Vibrate the device with a duration or pattern.
     * @param {number|number[]} pattern  Milliseconds, or an on/off pattern array.
     * @returns {Promise<void>}
     */
    vibrate: (pattern) => call("vibration.vibrate", { pattern }),
  }),
  badge: Object.freeze({
    /**
     * Set the app icon badge (a flag dot when count is null).
     * @param {?number} [count]  The badge count.
     * @returns {Promise<void>}
     */
    set: (count = null) => call("badge.set", { count }),
    /** Clear the app icon badge. @returns {Promise<void>} */
    clear: () => call("badge.clear", {}),
  }),
  wakelock: Object.freeze({
    /** Request a screen wake lock. @returns {Promise<string>}  The lock id. */
    request: () => call("wakelock.request", {}).then((r) => r.id),
    /** Release a wake lock by id. @returns {Promise<void>} */
    release: (id) => call("wakelock.release", { id }),
  }),
  fullscreen: Object.freeze({
    /** Enter fullscreen. @returns {Promise<boolean>}  Whether it is now active. */
    enter: () => call("fullscreen.enter", {}).then((r) => r.active),
    /** Exit fullscreen. @returns {Promise<boolean>}  Whether it is still active. */
    exit: () => call("fullscreen.exit", {}).then((r) => r.active),
    /** Whether an element is currently fullscreen. @returns {Promise<boolean>} */
    state: () => call("fullscreen.state", {}).then((r) => r.active),
  }),
  visibility: Object.freeze({
    /** The current page visibility state. @returns {Promise<string>} */
    state: () => call("visibility.state", {}).then((r) => r.state),
    /**
     * Watch page visibility, streaming each change to `onEvent` (T-EV).
     * @param {(value: {state:string, hidden:boolean}) => void} onEvent
     * @returns {() => void}  Unsubscribe: removes the visibility listener.
     */
    watch: (onEvent) => stream("visibility.watch", {}, onEvent),
  }),
  orientation: Object.freeze({
    /**
     * Lock the screen orientation.
     * @param {string} kind  The orientation lock (e.g. "portrait", "landscape").
     * @returns {Promise<boolean>}  Whether the lock succeeded.
     */
    lock: (kind) => call("orientation.lock", { kind }).then((r) => r.locked),
    /** Release the orientation lock. @returns {Promise<void>} */
    unlock: () => call("orientation.unlock", {}),
    /**
     * The current orientation type and angle.
     * @returns {Promise<{type:string, angle:number}>}
     */
    state: () => call("orientation.state", {}),
    /**
     * Watch the screen orientation, streaming each change to `onEvent` (T-EV).
     * @param {(value: {type:string, angle:number}) => void} onEvent
     * @returns {() => void}  Unsubscribe: removes the orientation listener.
     */
    watch: (onEvent) => stream("orientation.watch", {}, onEvent),
  }),
  quota: Object.freeze({
    /**
     * Estimate storage usage and quota (bytes).
     * @returns {Promise<{usage:number, quota:number}>}
     */
    estimate: () => call("quota.estimate", {}),
    /** Request durable (persistent) storage. @returns {Promise<boolean>} */
    persist: () => call("quota.persist", {}).then((r) => r.persisted),
    /** Whether storage is already persistent. @returns {Promise<boolean>} */
    persisted: () => call("quota.persisted", {}).then((r) => r.persisted),
  }),
  network: Object.freeze({
    /**
     * Report connectivity + best-effort connection details.
     * @returns {Promise<{online:boolean, effective_type:string,
     *                    downlink:number, rtt:number, save_data:boolean}>}
     */
    state: () => call("network.state", {}),
    /**
     * Watch connectivity, streaming the current snapshot per change (T-EV).
     * @param {(value: {online:boolean, effective_type:string, downlink:number,
     *                  rtt:number, save_data:boolean}) => void} onEvent
     * @returns {() => void}  Unsubscribe: stops the connectivity watch.
     */
    watch: (onEvent) => stream("network.watch", {}, onEvent),
  }),
  battery: Object.freeze({
    /**
     * Watch the device battery, streaming each state change to `onEvent` (T-EV).
     * @param {(value: {level:number, charging:boolean, charging_time:number,
     *                  discharging_time:number}) => void} onEvent
     * @returns {() => void}  Unsubscribe: stops the battery watch.
     */
    watch: (onEvent) => stream("battery.watch", {}, onEvent),
  }),
  idle: Object.freeze({
    /**
     * Watch the user's idle state, streaming each transition (T-EV).
     * @param {(value: {user:string, screen:string}) => void} onEvent
     * @param {{threshold_seconds?: number}} [opts]
     * @returns {() => void}  Unsubscribe: stops the idle detector.
     */
    watch: (onEvent, opts = {}) =>
      stream("idle.watch", { threshold_seconds: opts.threshold_seconds ?? 60 }, onEvent),
  }),
  sensors: Object.freeze({
    /**
     * Stream device orientation (compass/tilt) readings (T-EV).
     * @param {(value: {alpha:number, beta:number, gamma:number,
     *                  absolute:boolean}) => void} onEvent
     * @returns {() => void}  Unsubscribe: removes the orientation listener.
     */
    orientation: (onEvent) => stream("sensors.orientation", {}, onEvent),
    /**
     * Stream device motion (accelerometer/gyroscope) readings (T-EV).
     * @param {(value: {acceleration:Object, rotation_rate:Object,
     *                  interval:number}) => void} onEvent
     * @returns {() => void}  Unsubscribe: removes the motion listener.
     */
    motion: (onEvent) => stream("sensors.motion", {}, onEvent),
  }),
  speech: Object.freeze({
    /**
     * Speak a phrase via the platform synthesizer (fire-and-forget).
     * @param {string} text  The text to speak.
     * @param {{lang?:string, rate?:number, pitch?:number, volume?:number}} [opts]
     * @returns {Promise<void>}
     */
    speak: (text, opts = {}) =>
      call("speech.speak", {
        text,
        lang: opts.lang ?? "",
        rate: opts.rate ?? 1.0,
        pitch: opts.pitch ?? 1.0,
        volume: opts.volume ?? 1.0,
      }),
    /** Cancel queued/ongoing speech. @returns {Promise<void>} */
    cancel: () => call("speech.cancel", {}),
    /**
     * List the available synthesis voices.
     * @returns {Promise<Array<{name:string, lang:string, default:boolean}>>}
     */
    voices: () => call("speech.voices", {}).then((r) => r.voices),
    /**
     * Listen for recognition results, streaming each transcript (T-EV).
     * @param {(value: {transcript:string, is_final:boolean,
     *                  confidence:number}) => void} onEvent
     * @param {{lang?: string, interim?: boolean}} [opts]
     * @returns {() => void}  Unsubscribe: stops the recognizer.
     */
    listen: (onEvent, opts = {}) =>
      stream("speech.listen", { lang: opts.lang ?? "", interim: opts.interim ?? true }, onEvent),
  }),
  recorder: Object.freeze({
    /**
     * Start a recording (microphone audio, or the screen).
     * @param {string} [source]  "microphone" (default) or "screen".
     * @param {{mime_type?:string}} [opts]
     * @returns {Promise<string>}  The recording id.
     */
    start: (source = "microphone", opts = {}) =>
      call("recorder.start", { source, mime_type: opts.mime_type ?? "" }).then((r) => r.id),
    /**
     * Stop a recording by id and read back its bytes.
     * @param {string} id  The recording id.
     * @returns {Promise<{data_base64:string, mime_type:string, size:number}>}
     */
    stop: (id) => call("recorder.stop", { id }),
  }),
  filesystem: Object.freeze({
    /**
     * Open one or more files via the native picker.
     * @param {{accept?:Object, multiple?:boolean}} [opts]
     * @returns {Promise<Array<{id:string, name:string, mime_type:string,
     *                          data_base64:string}>>}
     */
    open_file: (opts = {}) =>
      call("filesystem.open_file", {
        accept: opts.accept ?? {},
        multiple: opts.multiple ?? false,
      }).then((r) => r.files),
    /**
     * Write base64 bytes back to a previously opened file handle.
     * @param {string} id  The file handle id.
     * @param {string} data_base64  The base64-encoded bytes.
     * @returns {Promise<{written:boolean}>}
     */
    write_file: (id, data_base64) => call("filesystem.write_file", { id, data_base64 }),
    /**
     * Save bytes to a new file via the native save dialog.
     * @param {string} filename  The suggested file name.
     * @param {string} data_base64  The base64-encoded bytes.
     * @param {{mime_type?:string}} [opts]
     * @returns {Promise<{id:string, name:string}>}
     */
    save_file: (filename, data_base64, opts = {}) =>
      call("filesystem.save_file", {
        filename,
        data_base64,
        mime_type: opts.mime_type ?? "application/octet-stream",
      }),
  }),
  bgsync: Object.freeze({
    /**
     * Register a one-off background-sync tag.
     * @param {string} tag  The sync tag.
     * @returns {Promise<boolean>}  Whether registration succeeded.
     */
    register: (tag) => call("bgsync.register", { tag }).then((r) => r.registered),
    /**
     * Register a periodic background-sync tag.
     * @param {string} tag  The sync tag.
     * @param {number} min_interval_ms  The minimum interval in milliseconds.
     * @returns {Promise<boolean>}  Whether registration succeeded.
     */
    register_periodic: (tag, min_interval_ms) =>
      call("bgsync.register_periodic", { tag, min_interval_ms }).then((r) => r.registered),
  }),
  tabs: Object.freeze({
    /**
     * Post a message to all tabs on a named BroadcastChannel.
     * @param {string} channel  The channel name.
     * @param {*} message  The JSON-able message.
     * @returns {Promise<void>}
     */
    broadcast: (channel, message) => call("tabs.broadcast", { channel, message }),
    /**
     * Acquire a named Web Lock, held until `unlock` releases it.
     * @param {string} name  The lock name.
     * @param {{mode?:string}} [opts]
     * @returns {Promise<boolean>}  Whether the lock was acquired.
     */
    lock: (name, opts = {}) =>
      call("tabs.lock", { name, mode: opts.mode ?? "exclusive" }).then((r) => r.acquired),
    /**
     * Release a previously acquired named Web Lock (idempotent).
     * @param {string} name  The lock name.
     * @returns {Promise<void>}
     */
    unlock: (name) => call("tabs.unlock", { name }),
    /**
     * Receive messages posted to a named BroadcastChannel, streaming each (T-EV).
     * @param {string} channel  The channel name.
     * @param {(value: {message: *}) => void} onEvent
     * @returns {() => void}  Unsubscribe: closes the channel.
     */
    receive: (channel, onEvent) => stream("tabs.receive", { channel }, onEvent),
  }),
  webauthn: Object.freeze({
    /**
     * Create a WebAuthn credential (registration).
     * @param {Object} options  The PublicKeyCredentialCreationOptions (base64url).
     * @returns {Promise<Object>}  The serialized credential.
     */
    create: (options) => call("webauthn.create", { options }).then((r) => r.credential),
    /**
     * Get a WebAuthn assertion (authentication).
     * @param {Object} options  The PublicKeyCredentialRequestOptions (base64url).
     * @returns {Promise<Object>}  The serialized credential.
     */
    get: (options) => call("webauthn.get", { options }).then((r) => r.credential),
    /**
     * Read a one-time code delivered over SMS via the Web OTP API.
     * @returns {Promise<string>}  The received code.
     */
    get_otp: () => call("webauthn.get_otp", {}).then((r) => r.code),
  }),
  bluetooth: Object.freeze({
    /** Whether the Web Bluetooth API is available. @returns {Promise<boolean>} */
    is_supported: () => call("bluetooth.is_supported", {}).then((r) => r.supported),
    /**
     * Request a device and connect its GATT server.
     * @param {{filters?:Array<Object>, optional_services?:Array<string>}} [opts]
     * @returns {Promise<{id:number, name:string}>}
     */
    request: (opts = {}) =>
      call("bluetooth.request", {
        filters: opts.filters ?? [],
        optional_services: opts.optional_services ?? [],
      }),
    /**
     * Read a GATT characteristic value as base64.
     * @param {number} id  The device id from `request`.
     * @param {string} service  The service UUID.
     * @param {string} characteristic  The characteristic UUID.
     * @returns {Promise<string>}  The base64-encoded value.
     */
    read: (id, service, characteristic) =>
      call("bluetooth.read", { id, service, characteristic }).then((r) => r.data_base64),
    /**
     * Write base64 bytes to a GATT characteristic.
     * @param {number} id  The device id from `request`.
     * @param {string} service  The service UUID.
     * @param {string} characteristic  The characteristic UUID.
     * @param {string} data_base64  The base64-encoded bytes.
     * @returns {Promise<void>}
     */
    write: (id, service, characteristic, data_base64) =>
      call("bluetooth.write", { id, service, characteristic, data_base64 }),
  }),
  contacts: Object.freeze({
    /** Whether the Contact Picker API is available. @returns {Promise<boolean>} */
    is_supported: () => call("contacts.is_supported", {}).then((r) => r.supported),
    /**
     * Open the OS contact picker.
     * @param {Array<string>} properties  The properties to request (e.g. ["name"]).
     * @param {{multiple?:boolean}} [opts]
     * @returns {Promise<Array<Object>>}  The selected contacts.
     */
    select: (properties, opts = {}) =>
      call("contacts.select", { properties, multiple: opts.multiple ?? false }).then(
        (r) => r.contacts,
      ),
  }),
  eyedropper: Object.freeze({
    /**
     * Open the eyedropper and return the picked sRGB hex color.
     * @returns {Promise<string>}  The sRGB hex string (e.g. "#ff0000").
     */
    open: () => call("eyedropper.open", {}).then((r) => r.srgb_hex),
  }),
  gamepad: Object.freeze({
    /**
     * Snapshot the connected gamepads' button and axis state.
     * @returns {Promise<Array<Object>>}
     */
    state: () => call("gamepad.state", {}).then((r) => r.gamepads),
    /**
     * Watch gamepad connections, streaming a snapshot per (dis)connect (T-EV).
     * @param {(value: {gamepads: Array<Object>}) => void} onEvent
     * @returns {() => void}  Unsubscribe: removes the gamepad listeners.
     */
    watch: (onEvent) => stream("gamepad.watch", {}, onEvent),
  }),
  hid: Object.freeze({
    /** Whether the WebHID API is available. @returns {Promise<boolean>} */
    is_supported: () => call("hid.is_supported", {}).then((r) => r.supported),
    /**
     * Request HID device access.
     * @param {{filters?:Array<Object>}} [opts]
     * @returns {Promise<Array<Object>>}  The granted devices.
     */
    request: (opts = {}) =>
      call("hid.request", { filters: opts.filters ?? [] }).then((r) => r.devices),
  }),
  midi: Object.freeze({
    /** Whether the Web MIDI API is available. @returns {Promise<boolean>} */
    is_supported: () => call("midi.is_supported", {}).then((r) => r.supported),
    /**
     * Request MIDI access and list the ports.
     * @param {{sysex?:boolean}} [opts]
     * @returns {Promise<{inputs:Array<Object>, outputs:Array<Object>}>}
     */
    request_access: (opts = {}) =>
      call("midi.request_access", { sysex: opts.sysex ?? false }),
    /**
     * Send a raw MIDI message to an output port.
     * @param {string} output_id  The output port id.
     * @param {Array<number>} data  The raw MIDI bytes.
     * @returns {Promise<void>}
     */
    send: (output_id, data) => call("midi.send", { output_id, data }),
    /**
     * Stream incoming MIDI messages from every input port (T-EV).
     * @param {(value: {input_id:string, data:Array<number>,
     *                  timestamp:number}) => void} onEvent
     * @returns {() => void}  Unsubscribe: detaches the MIDI input handlers.
     */
    messages: (onEvent) => stream("midi.messages", {}, onEvent),
  }),
  nfc: Object.freeze({
    /** Whether the Web NFC API is available. @returns {Promise<boolean>} */
    is_supported: () => call("nfc.is_supported", {}).then((r) => r.supported),
    /**
     * Write an NDEF message to a nearby NFC tag.
     * @param {Array<Object>} records  The NDEF records to write.
     * @returns {Promise<void>}
     */
    write: (records) => call("nfc.write", { records }),
    /**
     * Stream NDEF messages as tags are read (event channel).
     * @param {(message: Object) => void} onEvent  Called per tag read.
     * @returns {() => void}  Unsubscribe to stop scanning.
     */
    scan: (onEvent) => stream("nfc.scan", {}, onEvent),
  }),
  payment: Object.freeze({
    /** Whether the Payment Request API is available. @returns {Promise<boolean>} */
    is_supported: () => call("payment.is_supported", {}).then((r) => r.supported),
    /**
     * Open the payment sheet.
     * @param {Array<Object>} methods  The supported payment methods.
     * @param {Object} details  The payment details (total, items).
     * @param {Object} [opts]  The payment options.
     * @returns {Promise<Object>}  The completed payment response.
     */
    request: (methods, details, opts = {}) =>
      call("payment.request", { methods, details, options: opts }).then((r) => r.response),
  }),
  pip: Object.freeze({
    /**
     * Enter Picture-in-Picture for a video.
     * @param {{selector?:string}} [opts]
     * @returns {Promise<boolean>}  Whether PiP is now active.
     */
    request: (opts = {}) =>
      call("pip.request", { selector: opts.selector ?? "video" }).then((r) => r.active),
    /** Exit Picture-in-Picture. @returns {Promise<boolean>}  Whether PiP is active. */
    exit: () => call("pip.exit", {}).then((r) => r.active),
  }),
  pointerlock: Object.freeze({
    /**
     * Request pointer lock on an element.
     * @param {{selector?:string}} [opts]
     * @returns {Promise<void>}
     */
    request: (opts = {}) => call("pointerlock.request", { selector: opts.selector ?? null }),
    /** Exit pointer lock. @returns {Promise<void>} */
    exit: () => call("pointerlock.exit", {}),
  }),
  serial: Object.freeze({
    /** Whether the Web Serial API is available. @returns {Promise<boolean>} */
    is_supported: () => call("serial.is_supported", {}).then((r) => r.supported),
    /**
     * Request a serial port.
     * @param {{filters?:Array<Object>}} [opts]
     * @returns {Promise<number>}  The port id.
     */
    request: (opts = {}) =>
      call("serial.request", { filters: opts.filters ?? [] }).then((r) => r.id),
  }),
  usb: Object.freeze({
    /** Whether the WebUSB API is available. @returns {Promise<boolean>} */
    is_supported: () => call("usb.is_supported", {}).then((r) => r.supported),
    /**
     * Request a USB device.
     * @param {{filters?:Array<Object>}} [opts]
     * @returns {Promise<{id:number, vendor_id:number, product_id:number,
     *                    product_name:string}>}
     */
    request: (opts = {}) => call("usb.request", { filters: opts.filters ?? [] }),
  }),
  webaudio: Object.freeze({
    /**
     * Play a short synthesized tone (fire-and-forget).
     * @param {number} frequency  The tone frequency in Hz.
     * @param {{duration_ms?:number, type?:string, volume?:number}} [opts]
     * @returns {Promise<void>}
     */
    tone: (frequency, opts = {}) =>
      call("webaudio.tone", {
        frequency,
        duration_ms: opts.duration_ms ?? 200,
        type: opts.type ?? "sine",
        volume: opts.volume ?? 1.0,
      }),
  }),
});
