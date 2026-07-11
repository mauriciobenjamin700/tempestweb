// native/tabs.js — cross-tab coordination: BroadcastChannel + Web Locks.
//
// `broadcast` is a one-shot post over a named BroadcastChannel. `lock`/`unlock`
// model a held Web Lock: the Web Locks API only holds a lock for the lifetime of
// a callback promise, so we grant the lock, resolve the caller with
// `{acquired:true}` the moment it is held, and keep the callback's promise pending
// until `unlock` fires the stored release resolver. We hold those resolvers in a
// module-level registry keyed by lock name.

import { CapabilityError } from "./index.js";

/**
 * Release resolvers for held locks, keyed by lock name.
 * @type {Map<string, () => void>}
 */
const _releasers = new Map();

/**
 * Post a message to all tabs listening on a named BroadcastChannel.
 * @param {{channel:string, message:*}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<Object>}
 * @throws {CapabilityError} unavailable when BroadcastChannel is missing.
 */
export async function tabsBroadcast(args, deps) {
  const BroadcastChannelCtor =
    deps.BroadcastChannel || /** @type {any} */ (globalThis).BroadcastChannel;
  if (!BroadcastChannelCtor) {
    throw new CapabilityError("unavailable", "BroadcastChannel is not available");
  }
  const bc = new BroadcastChannelCtor(args.channel);
  bc.postMessage(args.message);
  bc.close();
  return {};
}

/**
 * Acquire a named Web Lock, holding it until {@link tabsUnlock} releases it.
 * @param {{name:string, mode?:string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{acquired:boolean}>}
 * @throws {CapabilityError} unavailable when the Web Locks API is missing.
 */
export async function tabsLock(args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  if (!nav || !nav.locks || typeof nav.locks.request !== "function") {
    throw new CapabilityError("unavailable", "the Web Locks API is not available");
  }
  const mode = args.mode || "exclusive";
  return await new Promise((resolveAcquired) => {
    nav.locks.request(
      args.name,
      { mode },
      () =>
        new Promise((release) => {
          _releasers.set(args.name, release);
          resolveAcquired({ acquired: true });
        }),
    );
  });
}

/**
 * Release a previously acquired named Web Lock (idempotent).
 * @param {{name:string}} args
 * @param {import("./index.js").NativeDeps} _deps
 * @returns {Promise<Object>}
 */
export async function tabsUnlock(args, _deps) {
  const release = _releasers.get(args.name);
  if (release) {
    release();
    _releasers.delete(args.name);
  }
  return {};
}
