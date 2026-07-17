// pull.js — read-side delta-sync (pull).  PHASE P2 (read path).
//
// Complements the write-side OfflineQueue (sync.js): the queue pushes local
// mutations up; this pulls remote changes down so an offline client learns about
// edits made elsewhere. A durable watermark records the newest server clock seen;
// each pull reads pages changed since that watermark following a cursor, applies
// every remote row, and advances the watermark only after a full successful
// drain (so an interrupted pull re-reads from the last committed point rather
// than skipping rows). The page fetch and the row apply are injected, so this is
// backend- and framework-agnostic and fully unit-testable under Node.
//
// The canonical merge — last-write-wins, honoring tombstones and not clobbering
// a locally-pending newer edit — is provided by mergeRemoteInto() over the
// owner-scoped OfflineStore, but callers can supply any applyRemote.

/**
 * @typedef {Object} PullPage
 * @property {Object[]} rows        Remote rows changed since `since` (this page).
 * @property {?string} [nextCursor] Cursor for the next page, or null/absent when done.
 * @property {?string} [serverTime] Server clock to persist as the new watermark.
 */

/**
 * @typedef {Object} Watermark
 * @property {() => (Promise<?string>|?string)} get   Read the stored watermark.
 * @property {(value: string) => (Promise<void>|void)} set   Persist a new watermark.
 */

/**
 * A localStorage-backed watermark accessor.
 *
 * Degrades to an in-memory value when localStorage is unavailable (SSR / private
 * mode), so a pull still runs — it just won't persist the cursor across reloads.
 *
 * @param {string} key        The storage key.
 * @param {Storage} [storage] Storage override (defaults to global localStorage).
 * @returns {Watermark} The accessor.
 */
export function createWatermark(key, storage) {
  const store =
    storage ?? (typeof localStorage !== "undefined" ? localStorage : null);
  let memory = null;
  return {
    get() {
      if (!store) return memory;
      try {
        return store.getItem(key);
      } catch {
        return memory;
      }
    },
    set(value) {
      memory = value;
      if (!store) return;
      try {
        store.setItem(key, value);
      } catch {
      }
    },
  };
}

/**
 * Build a delta-sync pull runner.
 *
 * @param {Object} options
 * @param {(since: ?string, cursor: ?string) => Promise<PullPage>} options.pullPage
 *        Fetch one page of remote changes since `since`, from `cursor`.
 * @param {(row: Object) => Promise<void>|void} options.applyRemote
 *        Apply one remote row locally (see mergeRemoteInto for the default merge).
 * @param {Watermark} options.watermark
 *        The durable watermark accessor.
 * @returns {{ pull: () => Promise<{applied:number, pages:number, alreadyRunning?:boolean}> }}
 */
export function createPull(options) {
  if (
    !options ||
    typeof options.pullPage !== "function" ||
    typeof options.applyRemote !== "function" ||
    !options.watermark
  ) {
    throw new Error("createPull requires pullPage, applyRemote and watermark");
  }
  const { pullPage, applyRemote, watermark } = options;
  let _pulling = false;

  return {
    /**
     * Pull every page of changes since the watermark, applying each row in order.
     *
     * Single-flight: a concurrent call while a pull is in flight returns
     * immediately with `alreadyRunning: true` instead of double-pulling. The
     * watermark advances to the latest `serverTime` seen only after the whole
     * drain completes.
     *
     * @returns {Promise<{applied:number, pages:number, alreadyRunning?:boolean}>}
     */
    async pull() {
      if (_pulling) return { applied: 0, pages: 0, alreadyRunning: true };
      _pulling = true;
      let applied = 0;
      let pages = 0;
      let latestServerTime = null;
      try {
        const since = await watermark.get();
        let cursor = null;
        do {
          const page = await pullPage(since, cursor);
          for (const row of page.rows || []) {
            await applyRemote(row);
            applied += 1;
          }
          pages += 1;
          if (page.serverTime) latestServerTime = page.serverTime;
          cursor = page.nextCursor ?? null;
        } while (cursor);
        if (latestServerTime != null) await watermark.set(latestServerTime);
      } finally {
        _pulling = false;
      }
      return { applied, pages };
    },
  };
}

/**
 * Build an applyRemote that merges a remote row into an owner-scoped OfflineStore.
 *
 * Last-write-wins, with two refinements: a tombstone deletes the local row, and
 * a server row does NOT overwrite a local row that is still pending upload and is
 * strictly newer by its `updatedAt` (so an offline edit awaiting push survives a
 * pull until it is flushed). Everything else is upserted.
 *
 * @param {import("./store.js").OfflineStore} store   The backing store.
 * @param {Object} [opts]
 * @param {(row: Object) => boolean} [opts.isTombstone]  Default: `row.deleted === true`.
 * @param {(row: Object) => IDBValidKey} [opts.keyOf]    Default: `row.id`.
 * @param {(row: Object) => (number|string|undefined)} [opts.updatedAtOf]
 *        Default: `row.updated_at`.
 * @param {(key: IDBValidKey) => (Promise<boolean>|boolean)} [opts.isPendingLocally]
 *        Whether a local edit for `key` is still awaiting upload. Default: always
 *        false. Wire it to the OfflineQueue to protect unpushed local edits.
 * @returns {(row: Object) => Promise<void>} The applyRemote function.
 */
export function mergeRemoteInto(store, opts = {}) {
  const isTombstone = opts.isTombstone ?? ((r) => r.deleted === true);
  const keyOf = opts.keyOf ?? ((r) => r.id);
  const updatedAtOf = opts.updatedAtOf ?? ((r) => r.updated_at);
  const isPendingLocally = opts.isPendingLocally ?? (() => false);

  return async (row) => {
    const key = keyOf(row);
    if (isTombstone(row)) {
      await store.delete(key);
      return;
    }
    const local = await store.get(key);
    if (local && (await isPendingLocally(key))) {
      const localAt = updatedAtOf(local);
      const remoteAt = updatedAtOf(row);
      if (localAt != null && remoteAt != null && localAt > remoteAt) return;
    }
    await store.put(row);
  };
}
