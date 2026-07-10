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

const DB_NAME = "tempestweb";
const STORE = "kv";

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
      return value === undefined ? null : value;
    },
    /** @param {string} name @param {string} content @returns {Promise<void>} */
    async put(name, content) {
      await withStore("readwrite", (store) => promisify(store.put(content, name)));
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
