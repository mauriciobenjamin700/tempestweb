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
//
// The connection is opened once and reused. It used to be opened and closed per
// operation — ten calls cost ten `indexedDB.open()` — and reusing it is only
// safe because the connection now yields on `versionchange`: a held connection
// is exactly what blocks another tab's upgrade.

import {
  CapabilityError,
  StoreBlockedError,
  StoreStaleError,
} from "./index.js";
import {
  CODEC_JSON,
  decodeValue,
  encodeValue,
  resolveCodec,
} from "../offline/codec.js";

const DB_NAME = "tempestweb";
const STORE = "kv";

/**
 * The schema version every open requests.
 *
 * Named rather than inlined because it is the trigger for a whole failure mode:
 * the moment this changes, every tab still running the previous build holds a
 * connection at the old version, and the new tab's open sits in `blocked` until
 * they let go. Raising it is a deployment decision, not an edit — see
 * {@link openDb}.
 *
 * @type {number}
 */
const DB_VERSION = 1;

/**
 * How long any open may stay unsettled before the operation gives up, in ms.
 *
 * The deadline covers **every** open, not only one that reported `blocked`,
 * because the tab that gets told it is blocked is not the tab that suffers most.
 * Measured against a real `IDBFactory`: while one tab's upgrade sits blocked, a
 * second tab opening the database at the current version receives **no event at
 * all** — not `blocked`, not `success`, not `error`. It is queued silently
 * behind the pending upgrade. Arming the clock only inside `onblocked` would
 * therefore rescue the tab doing the upgrading and leave every bystander hanging
 * exactly as before, which is the common case, not the rare one.
 *
 * Three seconds is far longer than a healthy open (single-digit milliseconds)
 * and short enough that a screen waiting on `storage` fails instead of hanging.
 *
 * @type {number}
 */
const OPEN_TIMEOUT_MS = 3000;

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
 * Three lifecycle facts shape this, and each was measured against a real
 * `IDBFactory` rather than read off the spec:
 *
 * **`blocked` is not terminal.** It fires when another tab holds the database at
 * an older version, and the request stays pending — `onsuccess` still arrives
 * once that tab lets go. Settling the promise there would report a failure for
 * an open that is about to succeed, so the handler only records that it
 * happened, for the error message.
 *
 * **A bystander gets no event at all.** While one tab's upgrade sits blocked, a
 * second tab opening at the current version receives no `blocked`, no `success`
 * and no `error` — it is queued silently behind the pending upgrade. That is why
 * the deadline covers every open instead of being armed inside `onblocked`:
 * arming it there rescues the tab doing the upgrade and leaves every other tab
 * hanging exactly as before. The bystander is the common case.
 *
 * **A late arrival must not be kept.** When the deadline has already rejected,
 * an `onsuccess` that lands afterwards is closed immediately. Holding it would
 * leave an unreachable connection open at the old version — which is itself
 * what blocks the next upgrade, so abandoning it silently would turn one late
 * open into the cause of the next hang.
 *
 * `onversionchange` is the other half of the fix, and it has to be in the build
 * that is *already deployed* when a bump happens: an upgrade is blocked by
 * yesterday's tabs, not by tomorrow's. Closing on that event is what lets the
 * upgrading tab through, and closing does not abort a transaction already in
 * flight — that write still commits.
 *
 * @param {IDBFactory} idb  The IndexedDB factory (`globalThis.indexedDB`).
 * @param {number} openTimeoutMs  How long the open may stay unsettled.
 * @returns {Promise<IDBDatabase>} The open database.
 * @throws {StoreUnavailableError} When the factory throws synchronously or the
 *         open request errors — this backend is not usable in this profile.
 * @throws {StoreBlockedError} When the open did not settle within
 *         `openTimeoutMs`, because another tab is mid-upgrade.
 * @throws {StoreStaleError} When the stored database is newer than
 *         {@link DB_VERSION} — another tab already upgraded and this build is
 *         behind. Kept apart from `StoreUnavailableError` so it does not degrade
 *         the page to `localStorage` and split the app's data in two.
 */
function openDb(idb, openTimeoutMs) {
  return new Promise((resolve, reject) => {
    /** @type {IDBOpenDBRequest} */
    let open;
    try {
      open = idb.open(DB_NAME, DB_VERSION);
    } catch (err) {
      reject(new StoreUnavailableError(describe(err)));
      return;
    }
    let abandoned = false;
    let sawBlocked = false;
    /** @type {*} */
    const timer = setTimeout(() => {
      abandoned = true;
      reject(
        new StoreBlockedError(
          sawBlocked
            ? "another tab held an older database version open"
            : "the open never settled; another tab is mid-upgrade",
        ),
      );
    }, openTimeoutMs);
    if (timer && typeof timer.unref === "function") timer.unref();

    const settle = (fn, value) => {
      clearTimeout(timer);
      if (!abandoned) fn(value);
    };
    open.onblocked = () => {
      sawBlocked = true;
    };
    open.onupgradeneeded = () => {
      const db = open.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE);
      }
    };
    open.onsuccess = () => {
      const db = open.result;
      db.onversionchange = () => db.close();
      if (abandoned) {
        db.close();
        return;
      }
      settle(resolve, db);
    };
    open.onerror = () => {
      const error = open.error;
      settle(
        reject,
        error && error.name === "VersionError"
          ? new StoreStaleError(describe(error))
          : new StoreUnavailableError(describe(error)),
      );
    };
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
      reject(
        failure || new Error(describe(tx.error) || "the transaction aborted"),
      );
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
 * @property {() => void} close  Release the held connection.
 */

/**
 * Create an IndexedDB-backed key/value store, or null when IndexedDB is absent.
 *
 * @param {IDBFactory} [idb]  The IndexedDB factory (defaults to the global one).
 * @param {Object} [options]
 * @param {number} [options.openTimeoutMs]  How long an open may stay unsettled
 *        before the operation gives up. Defaults to {@link OPEN_TIMEOUT_MS};
 *        injectable so a test can prove the deadline without waiting for it.
 * @returns {?KeyValueStore}  The store, or null when IndexedDB is unavailable.
 */
export function createIdbKv(
  idb = /** @type {any} */ (globalThis).indexedDB,
  { openTimeoutMs = OPEN_TIMEOUT_MS } = {},
) {
  if (!idb) {
    return null;
  }
  /**
   * The live connection, or null when there is none to reuse.
   * @type {?IDBDatabase}
   */
  let cached = null;
  /**
   * The open in flight, or null. Collapses concurrent callers onto one open.
   * @type {?Promise<IDBDatabase>}
   */
  let opening = null;

  /**
   * Drop `db` from the cache, if it is still the one cached.
   *
   * Guarded on identity because a stale handler — a `versionchange` for a
   * connection that was already replaced — must not evict the live one.
   *
   * @param {IDBDatabase} db  The connection to forget.
   * @returns {void}
   */
  const forget = (db) => {
    if (cached === db) cached = null;
  };

  /**
   * Return the live connection, opening one if needed.
   *
   * Reusing the connection is the point: the store used to open and close the
   * database on every single call, so ten operations cost ten opens. It is also
   * what makes the lifecycle handlers load-bearing rather than theoretical — a
   * held connection blocks another tab's upgrade until `versionchange` closes
   * it, which is why that half shipped first.
   *
   * Three things this must not get wrong:
   *
   * * **Concurrent callers share one open.** Without the in-flight promise,
   *   five parallel `put`s would each start their own, which is the cost the
   *   caching was meant to remove.
   * * **A failed open is not cached.** The promise is cleared on rejection, so
   *   a profile that recovers (or a `blocked` that clears) is retried rather
   *   than being answered from a poisoned cache forever.
   * * **A closed connection is dropped.** `versionchange` closes and forgets,
   *   so the next call opens fresh; `close` covers the connection the browser
   *   terminates on its own.
   *
   * @returns {Promise<IDBDatabase>} The connection to run a transaction on.
   */
  const connection = () => {
    if (cached) return Promise.resolve(cached);
    if (!opening) {
      opening = openDb(idb, openTimeoutMs).then(
        (db) => {
          db.onversionchange = () => {
            forget(db);
            db.close();
          };
          db.onclose = () => forget(db);
          cached = db;
          opening = null;
          return db;
        },
        (err) => {
          opening = null;
          throw err;
        },
      );
    }
    return opening;
  };

  /**
   * Run one transaction on the shared connection, reopening if it went away.
   *
   * The retry exists for one narrow race: a caller that took the cached
   * connection microseconds before another tab's upgrade closed it gets
   * `InvalidStateError` from `transaction()`. Reopening once turns that into a
   * normal call instead of an error the app has to understand. It is deliberately
   * not a general retry — a quota failure, an abort or a `blocked` open is the
   * caller's answer and propagates on the first try.
   *
   * @param {IDBTransactionMode} mode  `"readonly"` or `"readwrite"`.
   * @param {(store: IDBObjectStore) => Promise<*>} run  Issues the requests.
   * @returns {Promise<*>} What `run` resolved to, once the transaction committed.
   */
  const withStore = async (mode, run) => {
    for (let attempt = 0; ; attempt += 1) {
      const db = await connection();
      try {
        return await runTx(db, mode, run);
      } catch (err) {
        if (!err || err.name !== "InvalidStateError") {
          throw asCapabilityError(err);
        }
        forget(db);
        if (attempt > 0) throw asCapabilityError(err);
      }
    }
  };
  return {
    /** @param {string} name @returns {Promise<?string>} */
    async get(name) {
      const value = await withStore("readonly", (store) =>
        promisify(store.get(name)),
      );
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
      await withStore("readwrite", (store) =>
        promisify(store.put(stored, name)),
      );
    },
    /** @param {string} name @returns {Promise<void>} */
    async remove(name) {
      await withStore("readwrite", (store) => promisify(store.delete(name)));
    },
    /**
     * Release the connection this store is holding.
     *
     * Required, not a convenience: the store keeps one connection open, and an
     * open connection is what blocks another tab's upgrade. Dropping the store
     * object without closing would leave that connection alive and unreachable —
     * nothing left to close it, and `versionchange` firing on a handler whose
     * store nobody consults. A later call reopens lazily, so closing early is
     * never wrong, only wasteful.
     *
     * @returns {void}
     */
    close() {
      const db = cached;
      cached = null;
      opening = null;
      if (db) db.close();
    },
    /** @returns {Promise<string[]>} */
    async keys() {
      const keys = await withStore("readonly", (store) =>
        promisify(store.getAllKeys()),
      );
      return (keys || []).map(String);
    },
  };
}
