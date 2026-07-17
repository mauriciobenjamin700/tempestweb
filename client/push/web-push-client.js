// web-push-client.js — WebPush browser-flow client.  PHASE P3.
//
// Pure JS, no build step. Mirrors the React SDK's WebPushClient/usePushSubscription:
// the CLIENT owns the browser flow (feature detection, permission, pushManager
// subscribe/unsubscribe, reading the current subscription) and hands the raw
// subscription to the SERVER, which owns the endpoint + subscription store.
//
// The framework does not decide your endpoint schema: subscribe()/unsubscribe()
// call injected onSubscribe/onUnsubscribe callbacks with the subscription JSON so
// your app persists/removes it however it likes (POST /webpush/subscribe etc).
//
// All browser globals (registration, Notification, navigator) are injectable so
// the flow is unit-testable under Node. See tests/client/web-push-client.test.js.

/**
 * @typedef {Object} PushClientDeps
 * @property {ServiceWorkerRegistration} [registration]
 *           The active SW registration (default: navigator.serviceWorker.ready).
 * @property {typeof Notification} [notification]
 *           Notification constructor/permission source (default: global Notification).
 * @property {Navigator} [navigator]
 *           Navigator override (default: global navigator).
 */

/**
 * This device's active push endpoint, set on subscribe and cleared on
 * unsubscribe. The outbound mutation sender stamps it as `X-Push-Endpoint` so the
 * server can skip notifying the very device that made a change (no redundant
 * "data changed" push for your own edit).
 * @type {?string}
 */
let _activePushEndpoint = null;

/**
 * The device's active push endpoint, or null when not subscribed.
 * @returns {?string} The endpoint URL.
 */
export function getActivePushEndpoint() {
  return _activePushEndpoint;
}

/**
 * Record (or clear) the device's active push endpoint. Called by
 * WebPushClient.subscribe/unsubscribe; exposed for tests and manual wiring.
 * @param {?string} endpoint   The endpoint URL, or null to clear.
 * @returns {void}
 */
export function setActivePushEndpoint(endpoint) {
  _activePushEndpoint = endpoint || null;
}

/**
 * Decode a base64url VAPID public key into the Uint8Array pushManager expects.
 *
 * @param {string} base64String   The base64url-encoded application server key.
 * @returns {Uint8Array} The decoded key bytes.
 */
export function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = typeof atob === "function"
    ? atob(base64)
    : Buffer.from(base64, "base64").toString("binary");
  const output = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) output[i] = raw.charCodeAt(i);
  return output;
}

/**
 * Whether WebPush is supported in this context.
 *
 * Requires a service worker container, the PushManager API and the Notification
 * API. On iOS, push additionally needs the app to be installed (standalone) —
 * callers should pair this with an installed-state check before prompting.
 *
 * @param {PushClientDeps} [deps]   Overrides (tests).
 * @returns {boolean} Whether push can be used.
 */
export function isPushSupported(deps = {}) {
  const nav = deps.navigator ?? (typeof navigator !== "undefined" ? navigator : null);
  const notif = deps.notification ?? (typeof Notification !== "undefined" ? Notification : null);
  const hasSW = Boolean(nav && "serviceWorker" in nav);
  const hasPush = typeof PushManager !== "undefined" || Boolean(deps.registration?.pushManager);
  return hasSW && hasPush && Boolean(notif);
}

/**
 * The current notification permission ("granted"|"denied"|"default"|"unsupported").
 *
 * @param {PushClientDeps} [deps]   Overrides (tests).
 * @returns {"granted"|"denied"|"default"|"unsupported"} The permission state.
 */
export function getPermission(deps = {}) {
  const notif = deps.notification ?? (typeof Notification !== "undefined" ? Notification : null);
  if (!notif) return "unsupported";
  return notif.permission;
}

/**
 * Resolve the SW registration from deps or navigator.serviceWorker.ready.
 * @param {PushClientDeps} deps
 * @returns {Promise<?ServiceWorkerRegistration>} The registration or null.
 */
async function resolveRegistration(deps) {
  if (deps.registration) return deps.registration;
  const nav = deps.navigator ?? (typeof navigator !== "undefined" ? navigator : null);
  if (nav && nav.serviceWorker && nav.serviceWorker.ready) {
    return nav.serviceWorker.ready;
  }
  return null;
}

/**
 * A WebPush client that owns the browser-side subscription flow.
 */
export class WebPushClient {
  /**
   * @param {Object} options
   * @param {string} options.vapidPublicKey                 Base64url VAPID public key.
   * @param {(sub: Object) => Promise<void>|void} [options.onSubscribe]
   *        Persist the subscription server-side (e.g. POST /webpush/subscribe).
   * @param {(sub: Object) => Promise<void>|void} [options.onUnsubscribe]
   *        Remove the subscription server-side (e.g. DELETE /webpush/my).
   * @param {PushClientDeps} [options.deps]                 Browser overrides (tests).
   */
  constructor(options) {
    if (!options || !options.vapidPublicKey) {
      throw new Error("WebPushClient requires a vapidPublicKey");
    }
    /** @type {string} */
    this.vapidPublicKey = options.vapidPublicKey;
    /** @type {(sub: Object) => Promise<void>|void} */
    this.onSubscribe = options.onSubscribe ?? (() => {});
    /** @type {(sub: Object) => Promise<void>|void} */
    this.onUnsubscribe = options.onUnsubscribe ?? (() => {});
    /** @type {PushClientDeps} */
    this.deps = options.deps ?? {};
  }

  /**
   * Whether push is supported in this context.
   * @returns {boolean}
   */
  isSupported() {
    return isPushSupported(this.deps);
  }

  /**
   * Request notification permission (idempotent if already decided).
   * @returns {Promise<"granted"|"denied"|"default"|"unsupported">} The result.
   */
  async requestPermission() {
    const notif =
      this.deps.notification ??
      (typeof Notification !== "undefined" ? Notification : null);
    if (!notif) return "unsupported";
    if (notif.permission === "granted" || notif.permission === "denied") {
      return notif.permission;
    }
    return notif.requestPermission();
  }

  /**
   * Whether a push subscription currently exists.
   * @returns {Promise<boolean>}
   */
  async isSubscribed() {
    const reg = await resolveRegistration(this.deps);
    if (!reg || !reg.pushManager) return false;
    const sub = await reg.pushManager.getSubscription();
    return Boolean(sub);
  }

  /**
   * Subscribe to push: ensure permission, create the subscription and hand it to
   * the server via onSubscribe.
   *
   * @returns {Promise<Object>} The subscription JSON handed to the server.
   * @throws {Error} When unsupported, permission denied, or no registration.
   */
  async subscribe() {
    if (!this.isSupported()) throw new Error("push is not supported");
    const permission = await this.requestPermission();
    if (permission !== "granted") {
      throw new Error(`notification permission ${permission}`);
    }
    const reg = await resolveRegistration(this.deps);
    if (!reg || !reg.pushManager) throw new Error("no service worker registration");

    let sub = await reg.pushManager.getSubscription();
    if (!sub) {
      sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(this.vapidPublicKey),
      });
    }
    const json = typeof sub.toJSON === "function" ? sub.toJSON() : sub;
    setActivePushEndpoint(json.endpoint ?? sub.endpoint ?? null);
    await this.onSubscribe(json);
    return json;
  }

  /**
   * Unsubscribe: cancel the browser subscription and tell the server.
   *
   * @returns {Promise<boolean>} Whether a subscription was cancelled.
   */
  async unsubscribe() {
    const reg = await resolveRegistration(this.deps);
    if (!reg || !reg.pushManager) return false;
    const sub = await reg.pushManager.getSubscription();
    if (!sub) return false;
    const json = typeof sub.toJSON === "function" ? sub.toJSON() : sub;
    const ok = await sub.unsubscribe();
    if (ok) {
      setActivePushEndpoint(null);
      await this.onUnsubscribe(json);
    }
    return ok;
  }
}
