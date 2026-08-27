// native/storage.js — owner-scoped storage glue for the N3 storage capability.
//
// Prefers the owner-scoped IndexedDB store from T9/P2 (client/offline/store.js),
// injected as `deps.store` with an async `{ get, put, remove, keys }` interface.
// Falls back to synchronous `localStorage` where IndexedDB is unavailable, so the
// capability still works in plain pages and under jsdom.

import { CapabilityError } from "./index.js";
import { CODEC_JSON, isCodecSupported } from "../offline/codec.js";
import { setKvCodec } from "./idb-kv.js";

/**
 * @typedef {Object} KeyValueStore
 * @property {(name:string) => Promise<string|null>} get
 * @property {(name:string, content:string) => Promise<void>} put
 * @property {(name:string) => Promise<void>} remove
 * @property {() => Promise<string[]>} keys
 */

/**
 * Resolve a uniform async store: the injected IndexedDB store, or a localStorage
 * adapter, throwing when neither is present.
 * @param {import("./index.js").NativeDeps} deps
 * @returns {KeyValueStore}
 */
function resolveStore(deps) {
  if (deps.store) return /** @type {KeyValueStore} */ (deps.store);
  const ls = deps.localStorage || /** @type {any} */ (globalThis).localStorage;
  if (!ls) throw new CapabilityError("unavailable", "no storage backend");
  return {
    get: async (name) => ls.getItem(name),
    put: async (name, content) => {
      try {
        ls.setItem(name, content);
      } catch (err) {
        throw new CapabilityError("quota_exceeded", err && err.message);
      }
    },
    remove: async (name) => ls.removeItem(name),
    keys: async () => {
      /** @type {string[]} */
      const out = [];
      for (let i = 0; i < ls.length; i += 1) {
        const k = ls.key(i);
        if (k !== null) out.push(k);
      }
      return out;
    },
  };
}

/**
 * Write a value under a key.
 * @param {{name:string,content:string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<Object>}
 */
export async function storagePut(args, deps) {
  await resolveStore(deps).put(args.name, args.content);
  return {};
}

/**
 * Read a value by key.
 * @param {{name:string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{content:string}>}
 * @throws {CapabilityError} not_found when the key is absent.
 */
export async function storageGet(args, deps) {
  const value = await resolveStore(deps).get(args.name);
  if (value === null || value === undefined) {
    throw new CapabilityError("not_found", args.name);
  }
  return { content: String(value) };
}

/**
 * Remove a value by key.
 * @param {{name:string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<Object>}
 * @throws {CapabilityError} not_found when the key is absent.
 */
export async function storageRemove(args, deps) {
  const store = resolveStore(deps);
  const value = await store.get(args.name);
  if (value === null || value === undefined) {
    throw new CapabilityError("not_found", args.name);
  }
  await store.remove(args.name);
  return {};
}

/**
 * List all keys. Returns an empty array when storage is empty (never throws
 * not_found — a collection lookup).
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{keys:string[]}>}
 */
export async function storageList(_args, deps) {
  const keys = await resolveStore(deps).keys();
  return { keys: Array.isArray(keys) ? keys : [] };
}

/**
 * Choose the codec new writes use, and report what will actually run.
 *
 * The compression measurement that decided this is in `client/offline/codec.js`:
 * IndexedDB already compresses, so a codec here saves 45-65% of what is left,
 * not the 87% the raw ratio suggests, and it costs a weak device ~76 ms to write
 * a megabyte. Hence opt-in.
 *
 * Two things are deliberate. First, an unsupported codec resolves to `json`
 * instead of throwing — a store that cannot compress is still a working store,
 * and `active` reports what happened. Second, this only affects the IndexedDB
 * backend: the `localStorage` fallback holds strings and cannot hold bytes, so
 * it reports `active: "json"` whatever was asked.
 *
 * @param {{codec?: string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{requested: string, active: string, supported: boolean}>}
 */
export async function storageConfigure(args, deps) {
  const requested = (args && args.codec) || CODEC_JSON;
  const supported = isCodecSupported(requested);
  const apply = (deps && /** @type {any} */ (deps).setKvCodec) || setKvCodec;
  const active = apply(requested);
  return { requested, active, supported };
}
