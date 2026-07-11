// native/bgsync.js — Background Sync + Periodic Background Sync glue.
//
// Both APIs hang off the active service worker registration: `sync.register(tag)`
// schedules a one-off replay the next time connectivity returns; `periodicSync`
// schedules recurring wake-ups (subject to browser heuristics + a granted
// permission). Neither is universally supported, so absence degrades to
// `unavailable` rather than throwing an opaque error.

import { CapabilityError } from "./index.js";

/**
 * Register a one-off background-sync tag on the service worker.
 * @param {{tag:string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{registered:boolean}>}
 * @throws {CapabilityError} unavailable when the Background Sync API is missing.
 */
export async function bgsyncRegister(args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  if (!nav || !nav.serviceWorker) {
    throw new CapabilityError("unavailable", "service workers are not available");
  }
  const reg = await nav.serviceWorker.ready;
  if (!reg || !reg.sync || typeof reg.sync.register !== "function") {
    throw new CapabilityError("unavailable", "the Background Sync API is not available");
  }
  await reg.sync.register(args.tag);
  return { registered: true };
}

/**
 * Register a periodic background-sync tag on the service worker.
 * @param {{tag:string, min_interval_ms?:number}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{registered:boolean}>}
 * @throws {CapabilityError} unavailable when Periodic Background Sync is missing.
 */
export async function bgsyncRegisterPeriodic(args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  if (!nav || !nav.serviceWorker) {
    throw new CapabilityError("unavailable", "service workers are not available");
  }
  const reg = await nav.serviceWorker.ready;
  if (!reg || !reg.periodicSync || typeof reg.periodicSync.register !== "function") {
    throw new CapabilityError("unavailable", "Periodic Background Sync is not available");
  }
  await reg.periodicSync.register(args.tag, { minInterval: args.min_interval_ms });
  return { registered: true };
}
