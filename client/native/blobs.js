// native/blobs.js — the client-side blob registry that keeps image bytes on the
// client.  PHASE R6.
//
// WHY THIS EXISTS. Every image capability used to hand Python the bytes: a 4 MB
// photo crosses the bridge as ~5.3 MB of base64. Compressing it then meant
// sending those bytes back down to the browser, compressing, and sending the
// result up again. In Mode A that is a string conversion; in Mode B it is a
// WebSocket round trip, so shrinking a 4 MB photo would push 10.6 MB over the
// network first. That is absurd, and it is the reason this registry exists.
//
// So an image lives here, under a short opaque handle, and Python addresses it by
// name. Capture -> compress -> upload never moves the pixels across the bridge:
// ~40 bytes of handle do the work.
//
// The registry is process-wide and bounded. A handle is released explicitly, or
// evicted when the registry grows past its cap — a photo app that captures for an
// hour must not accumulate every frame it ever took.

/** How many blobs the registry holds before it evicts the oldest. */
export const MAX_BLOBS = 32;

/** The prefix every handle carries, so a stray string is not mistaken for one. */
export const REF_PREFIX = "blob:tw:";

/** @type {Map<string, {blob: Blob, mime: string, size: number}>} */
const registry = new Map();

let counter = 0;

/**
 * Report whether a value looks like a handle this registry issued.
 *
 * @param {*} value  The value to test.
 * @returns {boolean} Whether it carries the handle prefix.
 */
export function isBlobRef(value) {
  return typeof value === "string" && value.startsWith(REF_PREFIX);
}

/**
 * Store a blob and return the handle addressing it.
 *
 * Insertion order is the eviction order: `Map` preserves it, so the oldest
 * handle is the first key. Eviction is silent by design — a handle that fell out
 * reads as a miss, and the caller re-captures, which is recoverable. Raising here
 * would kill a screen because the user took too many photos.
 *
 * @param {Blob} blob  The bytes to keep.
 * @returns {string} The handle.
 */
export function putBlob(blob) {
  counter += 1;
  const ref = `${REF_PREFIX}${counter}`;
  registry.set(ref, {
    blob,
    mime: blob.type || "application/octet-stream",
    size: blob.size,
  });
  while (registry.size > MAX_BLOBS) {
    const oldest = registry.keys().next().value;
    if (oldest === undefined) break;
    registry.delete(oldest);
  }
  return ref;
}

/**
 * Look a handle up.
 *
 * @param {string} ref  The handle.
 * @returns {?Blob} The blob, or null when the handle is unknown or evicted.
 */
export function getBlob(ref) {
  const entry = registry.get(ref);
  return entry ? entry.blob : null;
}

/**
 * Describe what a handle points at, without reading the bytes.
 *
 * @param {string} ref  The handle.
 * @returns {?{mime: string, size: number}} The description, or null.
 */
export function describeBlob(ref) {
  const entry = registry.get(ref);
  return entry ? { mime: entry.mime, size: entry.size } : null;
}

/**
 * Release a handle.
 *
 * @param {string} ref  The handle.
 * @returns {boolean} Whether it was there to release.
 */
export function dropBlob(ref) {
  return registry.delete(ref);
}

/**
 * Drop every handle. For tests, and for an app leaving a capture screen.
 *
 * @returns {number} How many were dropped.
 */
export function clearBlobs() {
  const size = registry.size;
  registry.clear();
  return size;
}

/**
 * How many handles the registry currently holds.
 *
 * @returns {number} The count.
 */
export function countBlobs() {
  return registry.size;
}

/**
 * Resolve whatever an app passed as an image source into a Blob.
 *
 * The three shapes a source can take, in the order they are cheapest:
 *
 *   1. a handle this registry issued — nothing is decoded, nothing crosses;
 *   2. `{data_base64, mime_type}` — what `camera.capture` and `file.pick`
 *      answered before handles existed, kept working;
 *   3. a data URI string.
 *
 * @param {*} source  The source, in any of those shapes.
 * @returns {?Blob} The blob, or null when the source cannot be resolved — an
 *          evicted handle, an empty payload, malformed base64.
 */
export function resolveSource(source) {
  if (isBlobRef(source)) return getBlob(source);
  if (typeof source === "string") return fromDataUri(source);
  if (source && typeof source === "object") {
    if (isBlobRef(source.ref)) return getBlob(source.ref);
    if (typeof source.data_base64 === "string" && source.data_base64) {
      return fromBase64(source.data_base64, source.mime_type || source.mime);
    }
    if (typeof source.data === "string" && source.data) {
      return fromBase64(source.data, source.mime_type || source.mime);
    }
  }
  return null;
}

/**
 * Build a blob from base64 text.
 *
 * @param {string} base64  The encoded bytes, with or without a data-URI prefix.
 * @param {string} [mime]  The MIME type to tag the blob with.
 * @returns {?Blob} The blob, or null when the text does not decode.
 */
export function fromBase64(base64, mime) {
  const payload = base64.includes(",") ? base64.slice(base64.indexOf(",") + 1) : base64;
  try {
    const binary = atob(payload);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    return new Blob([bytes], { type: mime || "application/octet-stream" });
  } catch {
    return null;
  }
}

/**
 * Build a blob from a data URI.
 *
 * @param {string} uri  The data URI.
 * @returns {?Blob} The blob, or null when the string is not one.
 */
function fromDataUri(uri) {
  if (!uri.startsWith("data:")) return null;
  const comma = uri.indexOf(",");
  if (comma < 0) return null;
  const mime = uri.slice(5, uri.indexOf(";") > 0 ? uri.indexOf(";") : comma);
  return fromBase64(uri.slice(comma + 1), mime);
}

/**
 * Read a blob back as base64, for the app that genuinely needs the bytes.
 *
 * This is the escape hatch, not the path: calling it moves the whole image
 * across the bridge, which is what the registry exists to avoid.
 *
 * @param {Blob} blob  The blob to read.
 * @returns {Promise<string>} The base64 text, with no data-URI prefix.
 */
export async function toBase64(blob) {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  let binary = "";
  const CHUNK = 8192;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    binary += String.fromCharCode(...bytes.subarray(i, i + CHUNK));
  }
  return btoa(binary);
}
