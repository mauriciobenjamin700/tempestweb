// native/quota.js — StorageManager (quota + persistence) glue.
//
// `navigator.storage.estimate()` reports approximate usage/quota; `persist()`
// asks the browser to make origin storage durable (survives eviction pressure);
// `persisted()` reports whether it already is — without prompting.

import { CapabilityError } from "./index.js";

/**
 * Estimate current storage usage and quota (bytes).
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{usage:number, quota:number}>}
 * @throws {CapabilityError} unavailable when the StorageManager API is missing.
 */
export async function quotaEstimate(_args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  if (!nav || !nav.storage || typeof nav.storage.estimate !== "function") {
    throw new CapabilityError("unavailable", "the StorageManager API is not available");
  }
  const est = await nav.storage.estimate();
  return { usage: est.usage || 0, quota: est.quota || 0 };
}

/**
 * Request durable (persistent) storage for this origin.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{persisted:boolean}>}
 * @throws {CapabilityError} unavailable when the StorageManager API is missing.
 */
export async function quotaPersist(_args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  if (!nav || !nav.storage || typeof nav.storage.persist !== "function") {
    throw new CapabilityError("unavailable", "the StorageManager API is not available");
  }
  return { persisted: await nav.storage.persist() };
}

/**
 * Report whether origin storage is already persistent.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{persisted:boolean}>}
 * @throws {CapabilityError} unavailable when the StorageManager API is missing.
 */
export async function quotaPersisted(_args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  if (!nav || !nav.storage || typeof nav.storage.persisted !== "function") {
    throw new CapabilityError("unavailable", "the StorageManager API is not available");
  }
  return { persisted: await nav.storage.persisted() };
}
