// native/device.js — coarse hardware facts, for an app that adapts quality.
//
// Only hardware lives here. Connection type is `network.state` and storage usage
// is `quota.estimate` — duplicating either would give one fact two names in the
// wire contract, and the two names would drift.
//
// Every field is optional because every source is. `navigator.deviceMemory` and
// `performance.memory` are Chromium-only; `hardwareConcurrency` is the one with
// real reach. Missing means missing: the handler answers null rather than
// throwing, because "I do not know what this machine is" is a normal answer on
// Safari and an app adapting quality has a default to fall back to.

/** Bytes in a megabyte, for the heap figures. */
const MB = 1048576;

/**
 * Read a positive finite number, or null.
 *
 * Guards against the three ways a browser can hand back something unusable: an
 * absent property, a non-number, and a zero that means "not measured" rather
 * than "measured as zero".
 *
 * @param {*} value  The raw property value.
 * @returns {?number} The number, or null.
 */
function positive(value) {
  return typeof value === "number" && Number.isFinite(value) && value > 0
    ? value
    : null;
}

/**
 * Describe the machine, as far as this browser is willing to say.
 *
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps  `deps.navigator` and
 *        `deps.performance` are injectable so a test can present a browser that
 *        exposes none of this.
 * @returns {Promise<{memory_gb: ?number, cores: ?number, heap_used_mb: ?number, heap_limit_mb: ?number}>}
 *          Every field null on a browser that exposes nothing — never a throw.
 */
export async function deviceProfile(_args, deps) {
  const nav = (deps && deps.navigator) || /** @type {any} */ (globalThis).navigator;
  const perf =
    (deps && /** @type {any} */ (deps).performance) ||
    /** @type {any} */ (globalThis).performance;
  const memory = perf && perf.memory;

  return {
    memory_gb: positive(nav && nav.deviceMemory),
    cores: positive(nav && nav.hardwareConcurrency),
    heap_used_mb: heapMb(memory && memory.usedJSHeapSize),
    heap_limit_mb: heapMb(memory && memory.jsHeapSizeLimit),
  };
}

/**
 * Convert a heap figure in bytes to megabytes, rounded to one decimal.
 *
 * @param {*} bytes  The raw figure.
 * @returns {?number} Megabytes, or null when the figure is unusable.
 */
function heapMb(bytes) {
  const value = positive(bytes);
  return value === null ? null : Math.round((value / MB) * 10) / 10;
}
