// sync.js — offline mutation queue + Background Sync replay.  PHASE P2.
//
// Pure JS, no build step. Mutations made while offline are appended to a durable
// queue (the owner-scoped OfflineStore from store.js) carrying an idempotency key
// (from native.http, N0). When connectivity returns the queue is replayed in FIFO
// order; the server dedups by idempotency key (last-write-wins v1) so replays
// never double-apply. Where Background Sync exists the worker can trigger replay
// with the tab closed; where it does not (Safari) the page replays on reconnect.
//
// The OfflineStore, the network sender and the SyncManager are all injected, so
// the queue/replay logic is fully unit-testable under Node. See
// tests/client/offline-sync.test.js.

/**
 * @typedef {Object} Mutation
 * @property {string} id                Queue row primary key (uuid-ish).
 * @property {string} owner             Owner scope (user/domain).
 * @property {string} idempotencyKey    Stable key the server dedups on.
 * @property {string} method            HTTP method ("POST"|"PUT"|"PATCH"|"DELETE").
 * @property {string} url               Target URL.
 * @property {*} [body]                 JSON-able request body.
 * @property {number} seq               Monotonic sequence for FIFO ordering.
 * @property {number} attempts          Replay attempts so far.
 * @property {string} status            "pending" | "done" | "failed".
 */

/**
 * @typedef {Object} SendResult
 * @property {boolean} ok       Whether the mutation was accepted.
 * @property {number} [status]  HTTP status (when known).
 */

const QUEUE_TAG = "tw-offline-replay";

/**
 * Generate a reasonably-unique id without external deps.
 * @returns {string} A unique id.
 */
function uid() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * A durable offline mutation queue with replay-on-reconnect.
 */
export class OfflineQueue {
  /**
   * @param {Object} options
   * @param {import("./store.js").OfflineStore} options.store
   *        The backing owner-scoped store (its tableName holds the queue rows).
   * @param {(m: Mutation) => Promise<SendResult>} options.send
   *        Network sender; resolves {ok} (throws/rejects on transport failure).
   * @param {string} [options.owner]   Default owner scope (default "default").
   */
  constructor(options) {
    if (!options || !options.store || typeof options.send !== "function") {
      throw new Error("OfflineQueue requires a store and a send function");
    }
    /** @type {import("./store.js").OfflineStore} */
    this.store = options.store;
    /** @type {(m: Mutation) => Promise<SendResult>} */
    this.send = options.send;
    /** @type {string} */
    this.owner = options.owner ?? "default";
    /** @type {number} */
    this._seq = 0;
    /** @type {boolean} */
    this._replaying = false;
  }

  /**
   * Append a mutation to the durable queue.
   *
   * An idempotency key is generated when absent so the server can dedup replays.
   *
   * @param {Object} mutation
   * @param {string} mutation.method               HTTP method.
   * @param {string} mutation.url                  Target URL.
   * @param {*} [mutation.body]                    JSON-able body.
   * @param {string} [mutation.idempotencyKey]     Override the generated key.
   * @param {string} [mutation.owner]              Override the queue owner.
   * @returns {Promise<Mutation>} The enqueued row.
   */
  async enqueue(mutation) {
    this._seq += 1;
    /** @type {Mutation} */
    const row = {
      id: uid(),
      owner: mutation.owner ?? this.owner,
      idempotencyKey: mutation.idempotencyKey ?? uid(),
      method: mutation.method,
      url: mutation.url,
      body: mutation.body,
      seq: Date.now() * 1000 + this._seq,
      attempts: 0,
      status: "pending",
    };
    await this.store.put(row);
    return row;
  }

  /**
   * List pending mutations for the owner in FIFO order.
   * @param {string} [owner]   Owner scope (default the queue owner).
   * @returns {Promise<Mutation[]>} Pending rows, oldest first.
   */
  async pending(owner) {
    const rows = await this.store.list(owner ?? this.owner, { orderBy: "seq" });
    return rows.filter((r) => r.status === "pending");
  }

  /**
   * Replay every pending mutation in FIFO order.
   *
   * Each accepted mutation is removed from the queue. A mutation whose send
   * resolves {ok:false} or throws is left pending (attempts incremented) and
   * replay stops at the first failure so order is preserved on the next attempt.
   * Idempotency keys mean a re-sent mutation never double-applies server-side.
   *
   * @param {string} [owner]   Owner scope (default the queue owner).
   * @returns {Promise<{sent: number, remaining: number}>} Replay outcome.
   */
  async replay(owner) {
    if (this._replaying) return { sent: 0, remaining: (await this.pending(owner)).length };
    this._replaying = true;
    let sent = 0;
    try {
      const queue = await this.pending(owner);
      for (const row of queue) {
        let result;
        try {
          result = await this.send(row);
        } catch {
          result = { ok: false };
        }
        if (result && result.ok) {
          await this.store.delete(row.id);
          sent += 1;
        } else {
          await this.store.update(row.id, { attempts: row.attempts + 1 });
          break; // preserve FIFO; retry the rest later
        }
      }
    } finally {
      this._replaying = false;
    }
    const remaining = (await this.pending(owner)).length;
    return { sent, remaining };
  }

  /**
   * Number of pending mutations for the owner.
   * @param {string} [owner]   Owner scope (default the queue owner).
   * @returns {Promise<number>} The pending count.
   */
  async size(owner) {
    return (await this.pending(owner)).length;
  }
}

/**
 * Register a Background Sync to replay the queue with the tab closed.
 *
 * Degrades gracefully: returns false (the caller should replay on reconnect with
 * the tab open) when the SyncManager is unavailable, e.g. Safari.
 *
 * @param {ServiceWorkerRegistration} [registration]   The active SW registration.
 * @param {string} [tag]                                 The sync tag.
 * @returns {Promise<boolean>} Whether a Background Sync was registered.
 */
export async function registerBackgroundSync(registration, tag = QUEUE_TAG) {
  const reg =
    registration ??
    (typeof navigator !== "undefined" && navigator.serviceWorker
      ? await navigator.serviceWorker.ready
      : null);
  if (!reg || !reg.sync || typeof reg.sync.register !== "function") {
    return false;
  }
  try {
    await reg.sync.register(tag);
    return true;
  } catch {
    return false;
  }
}

/**
 * Wire replay to connectivity: replay now if online, and on every "online" event.
 *
 * Mirrors the reconnect path for browsers without Background Sync. Returns a
 * teardown function that removes the listener.
 *
 * @param {OfflineQueue} queue            The queue to replay.
 * @param {Object} [deps]
 * @param {EventTarget} [deps.target]     Event source (default global window).
 * @param {() => boolean} [deps.isOnline] Connectivity probe (default navigator.onLine).
 * @returns {() => void} A teardown function.
 */
export function replayOnReconnect(queue, deps = {}) {
  const target =
    deps.target ?? (typeof window !== "undefined" ? window : null);
  const isOnline =
    deps.isOnline ??
    (() => (typeof navigator !== "undefined" ? navigator.onLine !== false : true));

  const handler = () => {
    if (isOnline()) queue.replay();
  };

  if (isOnline()) queue.replay();
  if (target && typeof target.addEventListener === "function") {
    target.addEventListener("online", handler);
  }
  return () => {
    if (target && typeof target.removeEventListener === "function") {
      target.removeEventListener("online", handler);
    }
  };
}

export { QUEUE_TAG };
