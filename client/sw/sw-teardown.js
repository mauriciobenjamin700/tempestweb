// sw-teardown.js — the worker a build emits when the service worker is turned off.
//
// Pure JS, no build step, no imports, classic-worker-safe and `node --check`-clean,
// exactly like sw.js.
//
// Turning `[pwa] service_worker` off cannot simply stop emitting `sw.js`: every
// browser that already registered the caching worker keeps it — and keeps serving
// the app shell from a precache the deploy has moved past. A registered worker
// does revalidate its own script, so the reliable way to retire one is to ship a
// worker at the same URL whose whole job is to delete every cache it finds and
// unregister itself. It runs once per client that still had the old worker, then
// disappears.
//
// Nothing registers this file: `register.js` is not emitted when the worker is
// off, and the shell's registration block is not written into index.html.

/* global self, caches, clients */

/**
 * Delete every cache this origin holds.
 *
 * The old worker's precache is keyed by a build hash, so the name cannot be
 * predicted from here — and by the time this runs there may be several
 * generations of them. Everything goes: the origin is opting out of precaching
 * altogether, so a leftover entry is only a stale asset waiting to be served.
 *
 * @returns {Promise<void>}
 */
async function dropAllCaches() {
  if (typeof caches === "undefined") return;
  const names = await caches.keys();
  await Promise.all(names.map((name) => caches.delete(name)));
}

/**
 * Take control, drop every cache, unregister, then reload each controlled page.
 *
 * The reload matters: a page loaded through the old worker is already showing
 * precached assets. Unregistering does not refresh what is on screen, so without
 * it the user keeps the stale shell until they navigate away on their own.
 *
 * @returns {Promise<void>}
 */
async function teardown() {
  await self.clients.claim();
  await dropAllCaches();
  await self.registration.unregister();
  const controlled = await self.clients.matchAll({ type: "window" });
  for (const client of controlled) {
    if (typeof client.navigate === "function") client.navigate(client.url);
  }
}

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(teardown());
});
