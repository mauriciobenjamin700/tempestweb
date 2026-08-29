// native/storage.js — storage glue for the N3 storage capability.
//
// Prefers the async IndexedDB key/value store injected as `deps.store`
// (client/native/idb-kv.js, wired in by browserDeps()), with the interface
// { get, put, remove, keys }. Falls back to synchronous `localStorage` when no
// store is injected — and when one is injected but IndexedDB refuses to open —
// so the capability still works in plain pages, under jsdom, and in a profile
// whose storage the user blocked.
//
// The keyspace is scoped by OWNER, set with `storage.configure({owner})`. The
// scoping is derived HERE rather than inside idb-kv.js, because this is the only
// point both backends pass through: pushing it down would leave the localStorage
// fallback unscoped, and that is the degraded profile nobody watches.
//
// The default owner is the empty string, and it writes the key RAW — byte for
// byte what this file wrote before scoping existed. That is what makes the
// change free for data already on disk: nothing is rewritten, nothing is
// migrated, and no database version has to move.

import { CapabilityError } from "./index.js";
import { CODEC_JSON, isCodecSupported } from "../offline/codec.js";
import { setKvCodec, StoreUnavailableError } from "./idb-kv.js";

/**
 * The owner every key is currently scoped to. Empty means "no scoping".
 *
 * Module state, like the codec beside it. In Mode B that means it belongs to the
 * tab, so it survives a socket reconnect but NOT a page reload — the app has to
 * configure it during boot, before the first storage call.
 *
 * @type {string}
 */
let _owner = "";

/**
 * The byte that separates an owner from a key name.
 *
 * NUL is chosen because it sorts below every printable character, so one owner
 * occupies a contiguous key range, and because a real key name is vanishingly
 * unlikely to contain it. A legacy name that does contain one is readable by
 * exact `get`/`remove` but will not appear under the default owner's listing —
 * pinned by test rather than guarded, since guarding costs a check on every
 * write for a case that has never occurred.
 *
 * @type {string}
 */
const SEP = "\u0000";

/**
 * Derive the stored key for a name under the configured owner.
 *
 * @param {string} owner  The owner, or `""` for the unscoped default.
 * @param {string} name  The key the app asked for.
 * @returns {string} The key as the backend sees it.
 */
function scopedKey(owner, name) {
  return owner ? owner + SEP + name : name;
}

/**
 * Select the names belonging to `owner` from a backend listing, unprefixed.
 *
 * Returning the app's own names — not the stored keys — is what keeps callers
 * that filter the listing working unchanged. `tempestweb/query/persistence.py`
 * is one: it walks `list_keys()` looking for its own prefix, and would match
 * nothing if the owner prefix were still attached.
 *
 * The default owner deliberately takes every key that carries no separator,
 * rather than every key: without that, `configure()` back to the default would
 * list another owner's data.
 *
 * @param {string} owner  The owner, or `""` for the unscoped default.
 * @param {string[]} keys  Every key the backend holds.
 * @returns {string[]} The names this owner stored.
 */
function ownedNames(owner, keys) {
  if (!owner) return keys.filter((key) => !key.includes(SEP));
  const prefix = owner + SEP;
  return keys
    .filter((key) => key.startsWith(prefix))
    .map((key) => key.slice(prefix.length));
}

/**
 * @typedef {Object} KeyValueStore
 * @property {(name:string) => Promise<string|null>} get
 * @property {(name:string, content:string) => Promise<void>} put
 * @property {(name:string) => Promise<void>} remove
 * @property {() => Promise<string[]>} keys
 */

/**
 * Build the localStorage-backed adapter — the fallback backend.
 *
 * @param {import("./index.js").NativeDeps} deps
 * @returns {KeyValueStore} A uniform async store over `localStorage`.
 * @throws {CapabilityError} unavailable when there is no localStorage either.
 */
function localStorageStore(deps) {
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
 * Run one storage operation on the live backend, degrading if IndexedDB refuses.
 *
 * `deps.store` is preferred, but holding a store object is not having a store: a
 * profile can carry `globalThis.indexedDB` and fail every open — Chrome answers
 * `SecurityError` on an origin whose storage the user blocked, a Firefox private
 * window answers `InvalidStateError`. Reporting that as a failed write would cost
 * those profiles the whole capability, which used to work there over
 * `localStorage`, so it is treated as no backend instead: `deps.forgetStore()`
 * drops the cached store, so later calls skip IndexedDB without retrying the
 * open, and the operation is replayed on `localStorage`.
 *
 * Only {@link StoreUnavailableError} degrades. A real write failure (quota,
 * an aborted transaction) is the caller's answer and propagates untouched —
 * silently rewriting an over-quota IndexedDB value into `localStorage` would
 * split the app's data across two backends.
 *
 * @param {import("./index.js").NativeDeps} deps
 * @param {(store: KeyValueStore) => Promise<*>} run  The operation to run.
 * @returns {Promise<*>} What `run` resolved to, on whichever backend served it.
 */
async function onBackend(deps, run) {
  const store = /** @type {?KeyValueStore} */ (deps.store);
  if (store) {
    try {
      return await run(store);
    } catch (err) {
      if (!(err instanceof StoreUnavailableError)) throw err;
      if (typeof deps.forgetStore === "function") deps.forgetStore();
    }
  }
  return run(localStorageStore(deps));
}

/**
 * Write a value under a key.
 * @param {{name:string,content:string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<Object>}
 * @throws {CapabilityError} quota_exceeded when the backend is full.
 */
export async function storagePut(args, deps) {
  const key = scopedKey(_owner, args.name);
  await onBackend(deps, (store) => store.put(key, args.content));
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
  const value = await onBackend(deps, (store) =>
    store.get(scopedKey(_owner, args.name)),
  );
  if (value === null || value === undefined) {
    throw new CapabilityError("not_found", args.name);
  }
  return { content: String(value) };
}

/**
 * Remove a value by key.
 *
 * The lookup and the delete share one backend resolution, so a store that
 * degrades mid-operation replays both halves rather than reading from IndexedDB
 * and deleting from `localStorage`.
 *
 * @param {{name:string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<Object>}
 * @throws {CapabilityError} not_found when the key is absent.
 */
export async function storageRemove(args, deps) {
  const key = scopedKey(_owner, args.name);
  const removed = await onBackend(deps, async (store) => {
    const value = await store.get(key);
    if (value === null || value === undefined) return false;
    await store.remove(key);
    return true;
  });
  if (!removed) {
    throw new CapabilityError("not_found", args.name);
  }
  return {};
}

/**
 * List the configured owner's keys, unprefixed.
 *
 * Returns an empty array when the owner stored nothing (never throws not_found —
 * a collection lookup). Another owner's keys are not in the answer, which is the
 * half of #195 that a caller notices: `tempestweb/query/persistence.py` restores
 * its cache by walking this listing, so before scoping, one user's boot filled
 * the cache with another user's API responses.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{keys:string[]}>}
 */
export async function storageList(_args, deps) {
  const keys = await onBackend(deps, (store) => store.keys());
  return { keys: ownedNames(_owner, Array.isArray(keys) ? keys : []) };
}

/**
 * Choose the codec new writes use, and report what will actually run.
 *
 * The compression measurement that decided this is in `client/offline/codec.js`:
 * IndexedDB already compresses, so a codec here saves 45-65% of what is left,
 * not the 87% the raw ratio suggests, and it costs a weak device ~76 ms to write
 * a megabyte. Hence opt-in.
 *
 * Three things are deliberate. First, an unsupported codec resolves to `json`
 * instead of throwing — a store that cannot compress is still a working store,
 * and `active` reports what happened. Second, the codec only reaches the
 * IndexedDB backend: `localStorage` holds strings and cannot hold bytes, so with
 * no store `active` comes back `json` whatever was asked, and the codec is not
 * armed. Answering `deflate` there and then storing the string raw is exactly
 * the silent lie this capability already paid for once. Third, `supported` still
 * answers about the runtime, not about the backend, so a caller can tell "this
 * browser cannot deflate" from "this profile has nowhere to deflate into".
 *
 * A store that exists but will not open is not visible here — nothing has tried
 * to open it yet. The first operation degrades it away (see {@link onBackend}),
 * and every later call reports `json`.
 *
 * @param {{codec?: string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{requested: string, active: string, supported: boolean}>}
 */
export async function storageConfigure(args, deps) {
  const requested = (args && args.codec) || CODEC_JSON;
  const supported = isCodecSupported(requested);
  const apply = (deps && /** @type {any} */ (deps).setKvCodec) || setKvCodec;
  const active = deps && deps.store ? apply(requested) : CODEC_JSON;
  _owner = String((args && args.owner) || "");
  return { requested, active, supported, owner: _owner };
}

/**
 * Reset the module's owner. Test seam, not part of the capability surface.
 *
 * @returns {void}
 */
export function resetStorageOwner() {
  _owner = "";
}
