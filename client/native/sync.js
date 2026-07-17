// native/sync.js — configurable read+write sync capability (P2).
//
// Exposes the offline read-sync stack (client/offline/{pull,sync-status,
// sw-bridge}.js) to Python as a native capability, so a `view()` can drive and
// observe sync the same way it reads connectivity via native.network. An app
// first `configure`s a named source (an endpoint + a local table); then `now`
// runs a single-flight sync (replay the shared write queue, then pull remote
// changes), `status` reads the observable state and `watch` streams it.
//
// The endpoint follows a convention (adopted from the tempest-react-sdk sync
// engine): GET <url>?since=<watermark>&cursor=<cursor> returns
// { rows, next_cursor, server_time }. Rows merge last-write-wins over the
// owner-scoped OfflineStore (tombstones delete; a locally-pending newer edit is
// kept). Apps needing other shapes use the JS libs directly.
//
// Configuring a source also wires the service-worker bridge once, so an
// OFFLINE_PULL posted by the worker after a background drain reconciles every
// configured source with the token the page holds.

import { CapabilityError } from "./index.js";
import { httpRequest } from "./http.js";
import { getOfflineQueue } from "./offline.js";
import { createOfflineStore } from "../offline/store.js";
import { createPull, createWatermark, mergeRemoteInto } from "../offline/pull.js";
import { createSyncController } from "../offline/sync-status.js";
import { installSyncBridge, SW_MESSAGES } from "../offline/sw-bridge.js";

/** @type {Map<string, ReturnType<typeof createSyncController>>} */
const _sources = new Map();
let _bridgeWired = false;

/**
 * Build a sync controller for a configured source.
 *
 * @param {string} name   The source name (used for the default watermark key).
 * @param {Object} cfg    Source config (url, database, table, key_path, ...).
 * @param {import("./index.js").NativeDeps} [deps]   Injected deps.
 * @returns {ReturnType<typeof createSyncController>} The controller.
 */
function buildSource(name, cfg, deps) {
  const store = createOfflineStore({
    databaseName: cfg.database,
    tableName: cfg.table,
    keyPath: cfg.key_path || "id",
    ownerField: cfg.owner_field || "owner",
    indexedDB: deps && /** @type {any} */ (deps).indexedDB,
  });
  const watermark = createWatermark(cfg.watermark_key || `${name}:watermark`);
  const pull = createPull({
    pullPage: async (since, cursor) => {
      const params = [];
      if (since) params.push(`since=${encodeURIComponent(since)}`);
      if (cursor) params.push(`cursor=${encodeURIComponent(cursor)}`);
      const sep = cfg.url.includes("?") ? "&" : "?";
      const url = params.length ? `${cfg.url}${sep}${params.join("&")}` : cfg.url;
      const res = await httpRequest({ method: "GET", url, json: null, headers: {} }, deps);
      const body = (res && res.json_body) || {};
      return {
        rows: body.rows || [],
        nextCursor: body.next_cursor ?? null,
        serverTime: body.server_time ?? null,
      };
    },
    applyRemote: mergeRemoteInto(store),
    watermark,
  });
  return createSyncController({ queue: getOfflineQueue(deps), pull });
}

/**
 * Wire the service-worker bridge once so background drains trigger a pull.
 *
 * OFFLINE_PULL / REPLAY_OFFLINE_QUEUE run every source's syncNow;
 * OFFLINE_QUEUE_DRAINED just refreshes the pending counts. A no-op teardown when
 * service workers are unavailable, so this is safe to call outside a browser.
 * @returns {void}
 */
function ensureBridge() {
  if (_bridgeWired) return;
  _bridgeWired = true;
  const syncAll = () => {
    for (const controller of _sources.values()) void controller.syncNow();
  };
  installSyncBridge({
    [SW_MESSAGES.PULL]: syncAll,
    [SW_MESSAGES.REPLAY]: syncAll,
    [SW_MESSAGES.DRAINED]: () => {
      for (const controller of _sources.values()) void controller.refreshPending();
    },
  });
}

/**
 * Serialize the observable sync state into the snake_case wire shape Python
 * validates (the store uses camelCase internally).
 * @param {Object} state
 * @returns {Object}
 */
function toWireState(state) {
  return {
    phase: state.phase,
    online: state.online,
    pending: state.pending,
    last_synced_at: state.lastSyncedAt,
    last_summary: state.lastSummary,
    error: state.error,
  };
}

/**
 * Resolve a configured controller by name.
 * @param {string} name
 * @returns {ReturnType<typeof createSyncController>}
 * @throws {CapabilityError} unavailable when the source was not configured.
 */
function getController(name) {
  const controller = _sources.get(name);
  if (!controller) {
    throw new CapabilityError("unavailable", `sync source "${name}" is not configured`);
  }
  return controller;
}

/**
 * Configure (or replace) a named sync source.
 * @param {{name:string, url:string, database:string, table:string, key_path?:string, owner_field?:string, watermark_key?:string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{configured:boolean, name:string}>}
 */
export async function syncConfigure(args, deps) {
  const controller =
    (deps && /** @type {any} */ (deps).syncController) ||
    buildSource(args.name, args, deps);
  _sources.set(args.name, controller);
  ensureBridge();
  return { configured: true, name: args.name };
}

/**
 * Run one sync for a source now (replay the queue, then pull).
 * @param {{name:string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<Object>} The run summary.
 */
export async function syncNow(args, deps) {
  const summary = await getController(args.name).syncNow();
  return summary || { sent: 0, remaining: 0, failed: 0, conflicts: 0, applied: 0 };
}

/**
 * Read a source's current sync state.
 * @param {{name:string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<Object>} The sync state.
 */
export async function syncStatus(args, deps) {
  return toWireState(getController(args.name).status.get());
}

/**
 * Stream a source's sync state on every change (T-EV). Emits the current state
 * immediately, then on each transition.
 * @param {{name:string}} args
 * @param {(payload:Object) => void} emit
 * @param {import("./index.js").NativeDeps} deps
 * @returns {() => void} Teardown that removes the subscription.
 */
export function syncWatch(args, emit, deps) {
  return getController(args.name).status.subscribe((state) =>
    emit({ event: toWireState(state) }),
  );
}
