// native/notifications.js — Notifications API glue.
//
// notify() posts a local notification (silently dropped if permission is not
// granted); request_permission() prompts and returns the resulting state.

import { CapabilityError } from "./index.js";

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
