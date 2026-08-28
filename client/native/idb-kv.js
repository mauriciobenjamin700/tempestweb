// idb-kv.js — a minimal async key/value store over IndexedDB.
//
// The `storage` capability (client/native/storage.js) uses an injected
// `deps.store` with the async interface { get, put, remove, keys }, falling back
// to localStorage when none is injected. This provides that interface backed by
// IndexedDB — the proper client store (larger quota, async) — so every mode
// persists over IndexedDB rather than the ~5 MB synchronous localStorage.
//
// A single object store holds string values keyed by name. All operations return
// promises. `createIdbKv` returns null when IndexedDB is unavailable, so the
// caller can fall back to localStorage cleanly; when IndexedDB exists but the
// database will not open, operations reject with StoreUnavailableError and the
// caller degrades the same way.

import { CapabilityError } from "./index.js";
import { CODEC_JSON, decodeValue, encodeValue, resolveCodec } from "../offline/codec.js";

const DB_NAME = "tempestweb";
const STORE = "kv";

/**
 * The codec new writes use. Reads never consult it — an envelope carries its own
 * codec name, so a value written under one setting stays readable under another.
 *
 * @type {string}
 */
let _codec = CODEC_JSON;

/**
 * Raised when IndexedDB exists but its database will not open.
 *
 * Having `globalThis.indexedDB` is not having a store. Chrome answers
 * `SecurityError` on an origin whose storage the user blocked; a Firefox private
 * window answers `InvalidStateError`. Both leave the factory in place and every
 * open failing, so callers must treat this as "no backend" rather than as a
 * failed write: `client/native/storage.js` replays the operation on localStorage.
 */
export class StoreUnavailableError extends Error {
  /**
   * @param {string} [message]  Detail from the underlying failure.
   */
  constructor(message) {
    super(message || "IndexedDB will not open");
    this.name = "StoreUnavailableError";
    this.code = "unavailable";
  }
}

/**
 * Choose the codec new writes use.
 *
 * @param {string} codec  A name from {@link CODECS}. One this runtime cannot run
 *        (`deflate` on Safari below 16.4) resolves to `json` rather than
 *        throwing, so a store that cannot compress is still a working store.
 * @returns {string} The codec that will actually be used.
 */
export function setKvCodec(codec) {
  _codec = resolveCodec(codec);
  return _codec;
}

/**
 * Report the codec new writes are using.
 *
 * @returns {string} The active codec name.
 */
export function getKvCodec() {
  return _codec;
}

/**
 * Describe a DOMException or Error in one line, for an error message.
 *
 * @param {*} err  Anything thrown, including null.
 * @returns {string} `"Name: message"`, whichever half exists, or `""`.
 */
function describe(err) {
  if (!err) return "";
  const name = err.name ? String(err.name) : "";
  const message = err.message ? String(err.message) : "";
  if (name && message) return `${name}: ${message}`;
  return name || message;
}

/**
 * Translate an IndexedDB failure into the capability's error vocabulary.
 *
 * `QuotaExceededError` is the one the public API documents — `storage.put` in
 * `tempestweb/native/storage.py` raises `NativeError("quota_exceeded")` — so it
 * must not reach the router as a plain throw: the router codes anything that is
 * not a `CapabilityError` as the opaque `"error"`. Everything else, including
 * {@link StoreUnavailableError}, passes through so the caller can still tell an
 * absent backend from a failed write.
 *
 * @param {*} err  The rejection from a transaction.
 * @returns {*} A `CapabilityError` for a mapped failure, or `err` unchanged.
 */
function asCapabilityError(err) {
  if (err && err.name === "QuotaExceededError") {
    return new CapabilityError("quota_exceeded", describe(err));
  }
  return err;
}

/**
 * Wrap an IndexedDB request in a promise.
 * @param {IDBRequest} request
 * @returns {Promise<*>}
 */
function promisify(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

/**
 * Open (creating if needed) the tempestweb key/value database.
 *
 * @param {IDBFactory} idb  The IndexedDB factory (`globalThis.indexedDB`).
 * @returns {Promise<IDBDatabase>} The open database.
 * @throws {StoreUnavailableError} When the factory throws synchronously or the
 *         open request errors — this backend is not usable in this profile.
 */
function openDb(idb) {
  return new Promise((resolve, reject) => {
    /** @type {IDBOpenDBRequest} */
    let open;
    try {
      open = idb.open(DB_NAME, 1);
    } catch (err) {
      reject(new StoreUnavailableError(describe(err)));
      return;
    }
    open.onupgradeneeded = () => {
      const db = open.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE);
      }
    };
    open.onsuccess = () => resolve(open.result);
    open.onerror = () => reject(new StoreUnavailableError(describe(open.error)));
  });
}

/**
 * Run one transaction and settle on the transaction, not on the request.
 *
 * A request's `onsuccess` fires while the transaction is still open, so
 * resolving there reports success for a write the browser may yet throw away —
 * quota reached at commit time, an `abort()`, a commit that fails. Settling on
 * `oncomplete` / `onabort` is the only report that matches what is on disk. A
 * request that errored still wins over a completed transaction, so a handled
 * error is never silently a success.
 *
 * @param {IDBDatabase} db  An open database.
 * @param {IDBTransactionMode} mode  `"readonly"` or `"readwrite"`.
 * @param {(store: IDBObjectStore) => Promise<*>} run  Issues the requests.
 * @returns {Promise<*>} What `run` resolved to, once the transaction committed.
 */
function runTx(db, mode, run) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, mode);
    /** @type {*} */
    let result;
    /** @type {*} */
    let failure = null;
    tx.oncomplete = () => (failure ? reject(failure) : resolve(result));
    tx.onabort = () =>
      reject(failure || new Error(describe(tx.error) || "the transaction aborted"));
    Promise.resolve(run(tx.objectStore(STORE))).then(
      (value) => {
        result = value;
      },
      (err) => {
        failure = err || new Error("the transaction failed");
      },
    );
  });
}

/**
 * @typedef {Object} KeyValueStore
 * @property {(name: string) => Promise<?string>} get
 * @property {(name: string, content: string) => Promise<void>} put
 * @property {(name: string) => Promise<void>} remove
 * @property {() => Promise<string[]>} keys
 */

/**
 * Create an IndexedDB-backed key/value store, or null when IndexedDB is absent.
 *
 * @param {IDBFactory} [idb]  The IndexedDB factory (defaults to the global one).
 * @returns {?KeyValueStore}  The store, or null when IndexedDB is unavailable.
 */
export function createIdbKv(idb = /** @type {any} */ (globalThis).indexedDB) {
  if (!idb) {
    return null;
  }
  const withStore = async (mode, run) => {
    const db = await openDb(idb);
    try {
      return await runTx(db, mode, run);
    } catch (err) {
      throw asCapabilityError(err);
    } finally {
      db.close();
    }
  };
  return {
    /** @param {string} name @returns {Promise<?string>} */
    async get(name) {
      const value = await withStore("readonly", (store) => promisify(store.get(name)));
      return decodeValue(value);
    },
    /**
     * Write a value, encoding it before the transaction opens.
     *
     * The order matters: awaiting a non-IndexedDB promise (the codec's) inside
     * an open transaction lets the browser auto-commit it, and the write is lost.
     *
     * @param {string} name
     * @param {string} content
     * @returns {Promise<void>}
     */
    async put(name, content) {
      const stored = await encodeValue(content, _codec);
      await withStore("readwrite", (store) => promisify(store.put(stored, name)));
    },
    /** @param {string} name @returns {Promise<void>} */
    async remove(name) {
      await withStore("readwrite", (store) => promisify(store.delete(name)));
    },
    /** @returns {Promise<string[]>} */
    async keys() {
      const keys = await withStore("readonly", (store) => promisify(store.getAllKeys()));
      return (keys || []).map(String);
    },
  };
}
