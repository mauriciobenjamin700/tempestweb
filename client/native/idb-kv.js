// idb-kv.js — a minimal async key/value store over IndexedDB.
//
// The `storage` capability (client/native/storage.js) uses an injected
// `deps.store` with the async interface { get, put, remove, keys }, falling back
// to localStorage when none is injected. This provides that interface backed by
// IndexedDB — the proper client store (larger quota, async) — so Mode C (and any
// caller that injects it) persists over IndexedDB rather than the ~5 MB
// synchronous localStorage.
//
// A single object store holds string values keyed by name. All operations return
// promises. `createIdbKv` returns null when IndexedDB is unavailable, so the
// caller can fall back to localStorage cleanly.

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
 * @param {IDBFactory} idb  The IndexedDB factory (`globalThis.indexedDB`).
 * @returns {Promise<IDBDatabase>}
 */
function openDb(idb) {
  return new Promise((resolve, reject) => {
    const open = idb.open(DB_NAME, 1);
    open.onupgradeneeded = () => {
      const db = open.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE);
      }
    };
    open.onsuccess = () => resolve(open.result);
    open.onerror = () => reject(open.error);
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
      const tx = db.transaction(STORE, mode);
      const result = await run(tx.objectStore(STORE));
      return result;
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
    /** @param {string} name @param {string} content @returns {Promise<void>} */
    async put(name, content) {
      // Encoding happens BEFORE the transaction opens: awaiting a non-IDB
      // promise inside one lets it auto-commit, and the write is lost.
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
