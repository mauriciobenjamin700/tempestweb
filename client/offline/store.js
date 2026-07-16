// store.js — owner-scoped IndexedDB store.  PHASE P2.
//
// Pure JS, no build step. Mirrors the React SDK's createOfflineStore: a typed
// wrapper over a single object store, scoped by an "owner" field so multiple
// domains/users coexist in one database without leaking rows across owners.
//
// The IndexedDB factory is injected (defaults to the global) so the whole store
// is unit-testable under Node with fake-indexeddb. See
// tests/client/offline-store.test.js.
//
// API: put / bulkPut / get / list(owner, {orderBy, reverse, limit}) / update /
// updateMany / delete / clear / count. Persistence via navigator.storage.persist().

/**
 * @typedef {Object} StoreConfig
 * @property {string} databaseName              IndexedDB database name.
 * @property {number} [version]                 DB version (default 1).
 * @property {string} tableName                 Object store (table) name.
 * @property {string} [keyPath]                 Primary key path (default "id").
 * @property {string} [ownerField]              Field used to scope rows (default "owner").
 * @property {string[]} [indexes]               Extra fields to index.
 * @property {IDBFactory} [indexedDB]           Factory override (tests).
 */

/**
 * @typedef {Object} ListOptions
 * @property {string} [orderBy]   Field to sort by (default the keyPath).
 * @property {boolean} [reverse]  Sort descending when true.
 * @property {number} [limit]     Max rows to return.
 */

/**
 * Promisify an IDBRequest.
 * @template T
 * @param {IDBRequest<T>} request   The request.
 * @returns {Promise<T>} Resolves with request.result / rejects with the error.
 */
function promisifyRequest(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

/**
 * Promisify an IDBTransaction's completion.
 * @param {IDBTransaction} tx   The transaction.
 * @returns {Promise<void>} Resolves on complete / rejects on error or abort.
 */
function promisifyTx(tx) {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error || new Error("transaction aborted"));
  });
}

/**
 * An owner-scoped IndexedDB store over a single object store.
 */
export class OfflineStore {
  /**
   * @param {StoreConfig} config   Store configuration.
   */
  constructor(config) {
    if (!config || !config.databaseName || !config.tableName) {
      throw new Error("OfflineStore requires databaseName and tableName");
    }
    /** @type {StoreConfig} */
    this.config = {
      version: 1,
      keyPath: "id",
      ownerField: "owner",
      indexes: [],
      ...config,
    };
    /** @type {?IDBDatabase} */
    this._db = null;
  }

  /**
   * Resolve the IndexedDB factory (injected or global).
   * @returns {IDBFactory} The factory.
   * @throws {Error} When IndexedDB is unavailable.
   */
  _factory() {
    const idb =
      this.config.indexedDB ??
      (typeof indexedDB !== "undefined" ? indexedDB : undefined);
    if (!idb) throw new Error("IndexedDB is not available in this environment");
    return idb;
  }

  /**
   * Open (and upgrade if needed) the database, caching the handle.
   * @returns {Promise<IDBDatabase>} The open database.
   */
  async open() {
    if (this._db) return this._db;
    const { databaseName, version, tableName, keyPath, ownerField, indexes } =
      this.config;
    const request = this._factory().open(databaseName, version);
    request.onupgradeneeded = () => {
      const db = request.result;
      /** @type {IDBObjectStore} */
      let store;
      if (!db.objectStoreNames.contains(tableName)) {
        store = db.createObjectStore(tableName, { keyPath });
      } else {
        store = request.transaction.objectStore(tableName);
      }
      if (!store.indexNames.contains(ownerField)) {
        store.createIndex(ownerField, ownerField, { unique: false });
      }
      for (const idx of indexes || []) {
        if (!store.indexNames.contains(idx)) {
          store.createIndex(idx, idx, { unique: false });
        }
      }
    };
    this._db = await promisifyRequest(request);
    return this._db;
  }

  /**
   * Run a callback inside a transaction on the store.
   * @template T
   * @param {IDBTransactionMode} mode  "readonly" | "readwrite".
   * @param {(store: IDBObjectStore) => Promise<T>|T} fn  The work.
   * @returns {Promise<T>} The callback result after the tx completes.
   */
  async _withStore(mode, fn) {
    const db = await this.open();
    const tx = db.transaction(this.config.tableName, mode);
    const store = tx.objectStore(this.config.tableName);
    const result = await fn(store);
    await promisifyTx(tx);
    return result;
  }

  /**
   * Insert or replace one record.
   * @param {Object} record   The record (must include the keyPath when no auto key).
   * @returns {Promise<IDBValidKey>} The stored key.
   */
  async put(record) {
    return this._withStore("readwrite", (store) =>
      promisifyRequest(store.put(record)),
    );
  }

  /**
   * Insert or replace many records in one transaction.
   * @param {Object[]} records   The records.
   * @returns {Promise<number>} The count written.
   */
  async bulkPut(records) {
    return this._withStore("readwrite", async (store) => {
      for (const record of records) await promisifyRequest(store.put(record));
      return records.length;
    });
  }

  /**
   * Fetch one record by primary key.
   * @param {IDBValidKey} key   The primary key.
   * @returns {Promise<?Object>} The record, or null when absent.
   */
  async get(key) {
    const value = await this._withStore("readonly", (store) =>
      promisifyRequest(store.get(key)),
    );
    return value ?? null;
  }

  /**
   * List all records for an owner, optionally sorted and limited.
   *
   * Returns [] when the owner has no rows (never throws for an empty result).
   *
   * @param {string} owner          The owner value to scope by.
   * @param {ListOptions} [options] Sort/limit options.
   * @returns {Promise<Object[]>} The matching records.
   */
  async list(owner, options = {}) {
    const ownerField = this.config.ownerField;
    const rows = await this._withStore("readonly", (store) => {
      const index = store.index(ownerField);
      return promisifyRequest(index.getAll(owner));
    });
    const orderBy = options.orderBy ?? this.config.keyPath;
    const sorted = [...rows].sort((a, b) => {
      const av = a[orderBy];
      const bv = b[orderBy];
      if (av < bv) return -1;
      if (av > bv) return 1;
      return 0;
    });
    if (options.reverse) sorted.reverse();
    if (typeof options.limit === "number") return sorted.slice(0, options.limit);
    return sorted;
  }

  /**
   * List every record across all owners, unsorted.
   *
   * Used by the service-worker queue drainer, which must replay mutations for
   * every owner present (not just one). Returns [] when the store is empty.
   *
   * @returns {Promise<Object[]>} All records in the store.
   */
  async listAll() {
    return this._withStore("readonly", (store) =>
      promisifyRequest(store.getAll()),
    );
  }

  /**
   * Merge a partial patch into an existing record (no-op when absent).
   * @param {IDBValidKey} key      The primary key.
   * @param {Object} patch         Fields to merge.
   * @returns {Promise<?Object>} The updated record, or null when absent.
   */
  async update(key, patch) {
    return this._withStore("readwrite", async (store) => {
      const existing = await promisifyRequest(store.get(key));
      if (!existing) return null;
      const merged = { ...existing, ...patch };
      await promisifyRequest(store.put(merged));
      return merged;
    });
  }

  /**
   * Merge a patch into every record matching an owner.
   * @param {string} owner   The owner to scope by.
   * @param {Object} patch   Fields to merge into each match.
   * @returns {Promise<number>} The count updated.
   */
  async updateMany(owner, patch) {
    return this._withStore("readwrite", async (store) => {
      const index = store.index(this.config.ownerField);
      const rows = await promisifyRequest(index.getAll(owner));
      for (const row of rows) await promisifyRequest(store.put({ ...row, ...patch }));
      return rows.length;
    });
  }

  /**
   * Delete one record by primary key.
   * @param {IDBValidKey} key   The primary key.
   * @returns {Promise<void>}
   */
  async delete(key) {
    await this._withStore("readwrite", (store) =>
      promisifyRequest(store.delete(key)),
    );
  }

  /**
   * Delete every record for an owner.
   * @param {string} owner   The owner to scope by.
   * @returns {Promise<number>} The count removed.
   */
  async clear(owner) {
    return this._withStore("readwrite", async (store) => {
      const index = store.index(this.config.ownerField);
      const keys = await promisifyRequest(index.getAllKeys(owner));
      for (const key of keys) await promisifyRequest(store.delete(key));
      return keys.length;
    });
  }

  /**
   * Count records, optionally scoped to an owner.
   * @param {string} [owner]   When given, count only that owner's rows.
   * @returns {Promise<number>} The count.
   */
  async count(owner) {
    return this._withStore("readonly", (store) => {
      if (owner === undefined) return promisifyRequest(store.count());
      const index = store.index(this.config.ownerField);
      return promisifyRequest(index.count(owner));
    });
  }

  /**
   * Close the database handle (releases the connection).
   * @returns {void}
   */
  close() {
    if (this._db) {
      this._db.close();
      this._db = null;
    }
  }
}

/**
 * Convenience factory mirroring the React SDK's createOfflineStore.
 * @param {StoreConfig} config   Store configuration.
 * @returns {OfflineStore} A new store instance.
 */
export function createOfflineStore(config) {
  return new OfflineStore(config);
}

/**
 * Request durable storage so the database is not evicted under disk pressure.
 *
 * Degrades gracefully: returns false when the Storage API is unavailable rather
 * than throwing, so callers can treat eviction as a cache-miss, not a fatal loss.
 *
 * @param {Navigator} [nav]   Navigator override (tests). Defaults to global.
 * @returns {Promise<boolean>} Whether storage is now persisted.
 */
export async function persistStorage(nav) {
  const n = nav ?? (typeof navigator !== "undefined" ? navigator : undefined);
  if (!n || !n.storage || typeof n.storage.persist !== "function") {
    return false;
  }
  try {
    if (typeof n.storage.persisted === "function" && (await n.storage.persisted())) {
      return true;
    }
    return await n.storage.persist();
  } catch {
    return false;
  }
}
