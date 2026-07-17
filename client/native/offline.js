// native/offline.js — offline mutation-queue capability (P2).
//
// Wraps the durable OfflineQueue (client/offline/sync.js over the owner-scoped
// OfflineStore in client/offline/store.js) as a native capability so a Python /
// Mode C app can enqueue a mutation that survives being offline and replays in
// FIFO order when connectivity returns. The network sender is the shared http
// glue (native/http.js), so a replayed mutation is a normal `fetch` carrying its
// idempotency key (the server dedups). A single process-wide queue is built
// lazily; replay is also wired to the `online` event and Background Sync.
//
// Pure JS, no build step. The queue is injectable via `deps.offlineQueue` so the
// handlers are unit-testable under Node with a fake store + sender.

import { httpRequest } from "./http.js";
import { getActivePushEndpoint } from "../push/web-push-client.js";
import { createOfflineStore, persistStorage } from "../offline/store.js";
import {
  OfflineQueue,
  registerBackgroundSync,
  replayOnReconnect,
} from "../offline/sync.js";

/** @type {import("../offline/sync.js").OfflineQueue | null} */
let _queue = null;
let _reconnectWired = false;

/**
 * Lazily build (and cache) the process-wide offline queue.
 *
 * The queue persists to IndexedDB (`tempestweb-offline` / `mutations`) and sends
 * via the shared http glue. On first build, durable storage is requested
 * (best-effort) so the queue is not evicted under disk pressure, and replay is
 * wired to the `online` event so a reconnect drains the queue with the tab open.
 *
 * @param {import("./index.js").NativeDeps} [deps]  Injected deps; `deps.offlineQueue`
 *        overrides the whole queue (tests), `deps.indexedDB` the IDB factory.
 * @returns {import("../offline/sync.js").OfflineQueue} The queue.
 */
function queue(deps) {
  if (deps && /** @type {any} */ (deps).offlineQueue) {
    return /** @type {any} */ (deps).offlineQueue;
  }
  if (_queue) return _queue;
  const store = createOfflineStore({
    databaseName: "tempestweb-offline",
    tableName: "mutations",
    keyPath: "id",
    ownerField: "owner",
    indexedDB: deps && /** @type {any} */ (deps).indexedDB,
  });
  persistStorage(deps && /** @type {any} */ (deps).navigator).catch(() => {});
  const send = async (mutation) => {
    /** @type {Record<string, string>} */
    const headers = { "idempotency-key": mutation.idempotencyKey };
    const endpoint = getActivePushEndpoint();
    if (endpoint) headers["x-push-endpoint"] = endpoint;
    const res = await httpRequest(
      { method: mutation.method, url: mutation.url, json: mutation.body ?? null, headers },
      deps,
    );
    return { ok: res.ok, status: res.status };
  };
  _queue = new OfflineQueue({ store, send });
  if (
    !_reconnectWired &&
    typeof globalThis !== "undefined" &&
    typeof globalThis.addEventListener === "function"
  ) {
    replayOnReconnect(_queue);
    _reconnectWired = true;
  }
  return _queue;
}

/**
 * Serialize a queue row into the wire shape the Python `Mutation` validates.
 * @param {import("../offline/sync.js").Mutation} row
 * @returns {Object}
 */
function toWire(row) {
  return {
    id: row.id,
    owner: row.owner,
    idempotency_key: row.idempotencyKey,
    method: row.method,
    url: row.url,
    attempts: row.attempts,
    status: row.status,
  };
}

/**
 * Enqueue a mutation for durable, replay-on-reconnect delivery.
 *
 * After enqueueing, a Background Sync is scheduled so the worker drains the queue
 * when connectivity returns even with the tab closed; this is best-effort and a
 * no-op where unsupported (its rejection is swallowed). The tab-open drain path is
 * the `online` listener wired in `queue()`, and an app can also force a drain with
 * `native.offline.replay()`.
 *
 * @param {{method:string, url:string, body?:*, idempotency_key?:string, owner?:string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<Object>} The enqueued mutation (wire shape).
 */
export async function offlineEnqueue(args, deps) {
  const q = queue(deps);
  const row = await q.enqueue({
    method: args.method,
    url: args.url,
    body: args.body ?? null,
    idempotencyKey: args.idempotency_key ?? undefined,
    owner: args.owner ?? undefined,
  });
  registerBackgroundSync().catch(() => {});
  return toWire(row);
}

/**
 * List the pending mutations for an owner, oldest first.
 * @param {{owner?:string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{mutations: Object[]}>}
 */
export async function offlinePending(args, deps) {
  const rows = await queue(deps).pending(args.owner ?? undefined);
  return { mutations: rows.map(toWire) };
}

/**
 * Count the pending mutations for an owner.
 * @param {{owner?:string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{size: number}>}
 */
export async function offlineSize(args, deps) {
  return { size: await queue(deps).size(args.owner ?? undefined) };
}

/**
 * List the dead-lettered (permanently failed) mutations for an owner.
 * @param {{owner?:string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{mutations: Object[]}>}
 */
export async function offlineFailed(args, deps) {
  const rows = await queue(deps).failed(args.owner ?? undefined);
  return { mutations: rows.map(toWire) };
}

/**
 * List the mutations parked in the conflict lane (server returned 409).
 * @param {{owner?:string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{mutations: Object[]}>}
 */
export async function offlineConflicts(args, deps) {
  const rows = await queue(deps).conflicts(args.owner ?? undefined);
  return { mutations: rows.map(toWire) };
}

/**
 * Replay the pending queue now.
 *
 * Drains in FIFO order: accepted rows are removed, a transient failure stops
 * replay to preserve order (dead-lettered once attempts are exhausted), a
 * permanent 4xx is dead-lettered immediately and a 409 moves to the conflict
 * lane — neither blocks the rest.
 *
 * @param {{owner?:string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{sent:number, remaining:number, failed:number, conflicts:number}>}
 */
export async function offlineReplay(args, deps) {
  return queue(deps).replay(args.owner ?? undefined);
}
