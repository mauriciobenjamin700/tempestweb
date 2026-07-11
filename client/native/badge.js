// native/badge.js — App Badging API glue.
//
// `navigator.setAppBadge(count)` sets the app icon badge; calling it with no
// argument shows a flag-style dot. `clearAppBadge()` removes it. Available on
// installed PWAs on supported platforms.

import { CapabilityError } from "./index.js";

/**
 * Set the app badge to a count (or a flag dot when count is null/undefined).
 * @param {{count?: ?number}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<Object>}
 * @throws {CapabilityError} unavailable when the App Badging API is missing.
 */
export async function badgeSet(args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  if (!nav || typeof nav.setAppBadge !== "function") {
    throw new CapabilityError("unavailable", "the App Badging API is not available");
  }
  const count = args.count;
  if (count === null || count === undefined) {
    await nav.setAppBadge();
  } else {
    await nav.setAppBadge(count);
  }
  return {};
}

/**
 * Clear the app badge.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<Object>}
 * @throws {CapabilityError} unavailable when the App Badging API is missing.
 */
export async function badgeClear(_args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  if (!nav || typeof nav.clearAppBadge !== "function") {
    throw new CapabilityError("unavailable", "the App Badging API is not available");
  }
  await nav.clearAppBadge();
  return {};
}
