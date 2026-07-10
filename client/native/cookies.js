// native/cookies.js — the browser side of the `cookies` capability.
//
// Reads and writes `document.cookie`. Mirrors tempestweb/native/cookies.py; the
// same handlers serve all three modes (A via FFI, B via the native_call round
// trip, C via the in-process facade). Non-HttpOnly cookies only — HttpOnly
// cookies are invisible to `document.cookie` by design.
//
// See ../../docs/contract.md and tempestweb/native/cookies.py.

import { CapabilityError } from "./index.js";

/**
 * Parse `document.cookie` into a name → value map (values percent-decoded).
 * @param {string} raw  The `document.cookie` string.
 * @returns {Object<string, string>}  The parsed cookie jar.
 */
function parseCookies(raw) {
  /** @type {Object<string, string>} */
  const jar = {};
  for (const part of (raw || "").split(";")) {
    const eq = part.indexOf("=");
    if (eq < 0) {
      continue;
    }
    const name = part.slice(0, eq).trim();
    if (name) {
      jar[name] = decodeURIComponent(part.slice(eq + 1).trim());
    }
  }
  return jar;
}

/**
 * Resolve the document that owns the cookie jar, or throw when unavailable.
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Document}
 */
function requireDocument(deps) {
  const doc = deps.document;
  if (!doc) {
    throw new CapabilityError("unsupported", "document.cookie is unavailable");
  }
  return doc;
}

/**
 * Read a single cookie by name.
 *
 * Returns a wrapper object (`{ value }`) rather than a bare string so the value
 * survives the dispatch layer's object normalization and an absent cookie
 * (`null`) is distinguishable from an empty one (`""`).
 *
 * @param {{name: string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{value: ?string}>}  `{value}`, with `null` when absent.
 */
export async function cookiesGet(args, deps) {
  const jar = parseCookies(requireDocument(deps).cookie);
  const has = Object.prototype.hasOwnProperty.call(jar, args.name);
  return { value: has ? jar[args.name] : null };
}

/**
 * Read every readable cookie as a name → value map.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<Object<string, string>>}
 */
export async function cookiesAll(_args, deps) {
  return parseCookies(requireDocument(deps).cookie);
}

/**
 * Set a cookie.
 * @param {{name: string, value: string, max_age?: ?number, path?: string,
 *          same_site?: string, secure?: boolean}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<null>}
 */
export async function cookiesSet(args, deps) {
  const doc = requireDocument(deps);
  const parts = [`${args.name}=${encodeURIComponent(args.value ?? "")}`];
  parts.push(`Path=${args.path || "/"}`);
  if (args.max_age !== null && args.max_age !== undefined) {
    parts.push(`Max-Age=${args.max_age}`);
  }
  parts.push(`SameSite=${args.same_site || "Lax"}`);
  if (args.secure) {
    parts.push("Secure");
  }
  doc.cookie = parts.join("; ");
  return null;
}

/**
 * Remove a cookie by expiring it.
 * @param {{name: string, path?: string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<null>}
 */
export async function cookiesRemove(args, deps) {
  const doc = requireDocument(deps);
  doc.cookie = `${args.name}=; Path=${args.path || "/"}; Max-Age=0`;
  return null;
}
