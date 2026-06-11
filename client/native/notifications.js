// native/notifications.js — Notifications API glue.
//
// notify() posts a local notification (silently dropped if permission is not
// granted); request_permission() prompts and returns the resulting state.
// subscribe()/unsubscribe() (P3) run the browser-side WebPush flow via the
// WebPushClient and hand the raw subscription back to Python (server-side persist
// is the app's job — the framework does not own the endpoint schema).

import { CapabilityError } from "./index.js";
import { WebPushClient } from "../push/web-push-client.js";

/**
 * Map the native router's deps to the WebPushClient deps shape.
 * @param {import("./index.js").NativeDeps} deps
 * @returns {import("../push/web-push-client.js").PushClientDeps}
 */
function pushDeps(deps) {
  /** @type {import("../push/web-push-client.js").PushClientDeps} */
  const out = {};
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  if (nav) out.navigator = nav;
  const notif = deps.Notification || /** @type {any} */ (globalThis).Notification;
  if (notif) out.notification = notif;
  // Optional injected registration (tests / non-default SW container).
  if (/** @type {any} */ (deps).registration) {
    out.registration = /** @type {any} */ (deps).registration;
  }
  return out;
}

/**
 * Post a local notification.
 * @param {{title:string,body:string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<Object>}
 * @throws {CapabilityError} unavailable when the API is missing.
 */
export async function notificationsNotify(args, deps) {
  const Ctor = deps.Notification || /** @type {any} */ (globalThis).Notification;
  if (!Ctor) throw new CapabilityError("unavailable", "Notification is not available");
  if (Ctor.permission === "granted") {
    // Constructed for its side effect: showing the notification.
    new Ctor(args.title || "", { body: args.body || "" });
  }
  return {};
}

/**
 * Request notification permission, awaiting the user's choice.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{permission:"default"|"granted"|"denied"}>}
 * @throws {CapabilityError} unavailable when the API is missing.
 */
export async function notificationsRequestPermission(_args, deps) {
  const Ctor = deps.Notification || /** @type {any} */ (globalThis).Notification;
  if (!Ctor || typeof Ctor.requestPermission !== "function") {
    throw new CapabilityError("unavailable", "Notification is not available");
  }
  const permission = await Ctor.requestPermission();
  return { permission: permission || "default" };
}

/**
 * Subscribe to WebPush and return the raw subscription JSON.  P3.
 *
 * Runs the browser-side flow (permission + pushManager.subscribe) via the
 * WebPushClient. The subscription crosses back to Python, which persists it
 * server-side — so no onSubscribe callback is wired here.
 *
 * @param {{vapid_public_key:string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<Object>} The subscription JSON ({endpoint, keys, ...}).
 * @throws {CapabilityError} unavailable / permission_denied / no_registration.
 */
export async function notificationsSubscribe(args, deps) {
  const key = args && args.vapid_public_key;
  if (!key) throw new CapabilityError("invalid_argument", "vapid_public_key is required");
  const client = new WebPushClient({ vapidPublicKey: key, deps: pushDeps(deps) });
  if (!client.isSupported()) {
    throw new CapabilityError("unavailable", "push is not supported");
  }
  try {
    return await client.subscribe();
  } catch (err) {
    const message = err && err.message ? String(err.message) : "subscribe failed";
    const code = /permission/.test(message)
      ? "permission_denied"
      : /registration/.test(message)
        ? "no_registration"
        : "error";
    throw new CapabilityError(code, message);
  }
}

/**
 * Cancel the current WebPush subscription, if any.  P3.
 *
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{unsubscribed:boolean}>} Whether a subscription was cancelled.
 */
export async function notificationsUnsubscribe(_args, deps) {
  // vapidPublicKey is required by the WebPushClient constructor but unused by
  // unsubscribe(); a placeholder keeps the construction valid.
  const client = new WebPushClient({ vapidPublicKey: "x", deps: pushDeps(deps) });
  const unsubscribed = await client.unsubscribe();
  return { unsubscribed };
}
