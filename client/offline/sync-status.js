// sync-status.js — observable sync state + a controller that drives it.  P2.
//
// A framework-free surface over the offline layer's two halves: the write-side
// OfflineQueue (push) and the read-side pull engine (pull.js). The status store
// is a tiny observable (get/set/subscribe) an app can render — in tempestweb the
// Python view() reads it through the `native.sync` capability, mirroring how
// native.network exposes connectivity. The controller runs a single-flight
// "sync now" (replay the queue, then pull), reflects online/offline, and can
// flush on boot + on reconnect.
//
// Adopted from the famachapp-pwa / tempest-react-sdk sync store + useSync wiring,
// ported to pure JS with dependency injection so it is unit-testable under Node.

/**
 * @typedef {Object} SyncState
 * @property {"idle"|"syncing"|"error"} phase   The current sync phase.
 * @property {boolean} online                   Last known connectivity.
 * @property {number} pending                   Pending (unpushed) mutation count.
 * @property {?number} lastSyncedAt             Epoch ms of the last successful sync.
 * @property {?Object} lastSummary             Last run summary (sent/remaining/failed/conflicts/applied).
 * @property {?string} error                    Last error message, or null.
 */

/**
 * Create an observable sync-status store.
 *
 * @param {Partial<SyncState>} [initial]   Initial state overrides.
 * @returns {{
 *   get: () => SyncState,
 *   set: (patch: Partial<SyncState>) => void,
 *   subscribe: (fn: (s: SyncState) => void) => (() => void),
 * }}
 */
export function createSyncStatus(initial = {}) {
  /** @type {SyncState} */
  let state = {
    phase: "idle",
    online: true,
    pending: 0,
    lastSyncedAt: null,
    lastSummary: null,
    error: null,
    ...initial,
  };
  /** @type {Set<(s: SyncState) => void>} */
  const subs = new Set();

  return {
    get: () => state,
    set(patch) {
      state = { ...state, ...patch };
      for (const fn of subs) fn(state);
    },
    subscribe(fn) {
      subs.add(fn);
      fn(state);
      return () => subs.delete(fn);
    },
  };
}

/**
 * Build a controller that drives a sync-status store from the offline layer.
 *
 * @param {Object} options
 * @param {import("./sync.js").OfflineQueue} [options.queue]   The push queue.
 * @param {{ pull: () => Promise<{applied:number}> }} [options.pull]  The pull runner.
 * @param {ReturnType<typeof createSyncStatus>} [options.status]   Store (created if omitted).
 * @param {() => number} [options.now]   Clock (default Date.now), injectable for tests.
 * @returns {{
 *   status: ReturnType<typeof createSyncStatus>,
 *   syncNow: () => Promise<?Object>,
 *   refreshPending: () => Promise<void>,
 *   start: (deps?: Object) => (() => void),
 * }}
 */
export function createSyncController(options = {}) {
  const queue = options.queue ?? null;
  const pull = options.pull ?? null;
  const status = options.status ?? createSyncStatus();
  const now = options.now ?? (() => Date.now());

  /**
   * Run one sync: replay the queue, then pull remote changes.
   *
   * Single-flight (a call while `phase === "syncing"` returns the last summary
   * without re-running). On failure it records the error in the store and returns
   * null rather than throwing, so a UI trigger never crashes.
   *
   * @returns {Promise<?Object>} The run summary, or null on error.
   */
  async function syncNow() {
    if (status.get().phase === "syncing") return status.get().lastSummary;
    status.set({ phase: "syncing", error: null });
    try {
      const replayed = queue
        ? await queue.replay()
        : { sent: 0, remaining: 0, failed: 0, conflicts: 0 };
      const pulled = pull ? await pull.pull() : { applied: 0 };
      const summary = {
        sent: replayed.sent ?? 0,
        remaining: replayed.remaining ?? 0,
        failed: replayed.failed ?? 0,
        conflicts: replayed.conflicts ?? 0,
        applied: pulled.applied ?? 0,
      };
      status.set({
        phase: "idle",
        lastSyncedAt: now(),
        lastSummary: summary,
        pending: summary.remaining,
        error: null,
      });
      return summary;
    } catch (err) {
      status.set({
        phase: "error",
        error: err && err.message ? err.message : String(err),
      });
      return null;
    }
  }

  /**
   * Refresh the pending count from the queue into the store.
   * @returns {Promise<void>}
   */
  async function refreshPending() {
    if (queue) status.set({ pending: await queue.size() });
  }

  /**
   * Reflect connectivity, flush on boot, and flush again on every reconnect.
   *
   * @param {Object} [deps]
   * @param {EventTarget} [deps.target]     Event source (default global window).
   * @param {() => boolean} [deps.isOnline] Connectivity probe (default navigator.onLine).
   * @returns {() => void} A teardown that removes the listeners.
   */
  function start(deps = {}) {
    const target =
      deps.target ?? (typeof window !== "undefined" ? window : null);
    const isOnline =
      deps.isOnline ??
      (() => (typeof navigator !== "undefined" ? navigator.onLine !== false : true));

    status.set({ online: isOnline() });
    const onOnline = () => {
      status.set({ online: true });
      void syncNow();
    };
    const onOffline = () => status.set({ online: false });

    if (target && typeof target.addEventListener === "function") {
      target.addEventListener("online", onOnline);
      target.addEventListener("offline", onOffline);
    }
    void syncNow();

    return () => {
      if (target && typeof target.removeEventListener === "function") {
        target.removeEventListener("online", onOnline);
        target.removeEventListener("offline", onOffline);
      }
    };
  }

  return { status, syncNow, refreshPending, start };
}
