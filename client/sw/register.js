// register.js — main-thread service worker registration + update lifecycle. P1.
//
// Pure JS, no build step. Mirrors the React SDK's registerServiceWorker /
// skipWaiting / unregisterAllServiceWorkers:
//   - register the worker and watch for a new version in `waiting`
//   - surface onUpdate so the UI can show "new version, reload"
//   - on confirm, post SKIP_WAITING and reload once the new worker takes control
//
// The navigator.serviceWorker container is injected (defaults to the global) so
// the update flow is unit-testable with a mock container under jsdom. See
// tests/client/pwa-register.test.js.

/**
 * @typedef {Object} RegisterOptions
 * @property {string} [url]                          SW script URL. Default "/sw.js".
 * @property {string} [scope]                        Registration scope.
 * @property {(reg: ServiceWorkerRegistration) => void} [onUpdate]
 *           Called when a new worker is installed and waiting.
 * @property {(reg: ServiceWorkerRegistration) => void} [onReady]
 *           Called once the worker is active and controlling.
 * @property {(err: Error) => void} [onError]        Called on registration failure.
 * @property {ServiceWorkerContainer} [container]    Override navigator.serviceWorker (tests).
 */

/**
 * Resolve the service worker container to use.
 * @param {RegisterOptions} options
 * @returns {?ServiceWorkerContainer} The container, or null when unsupported.
 */
function resolveContainer(options) {
  if (options.container) return options.container;
  if (typeof navigator !== "undefined" && "serviceWorker" in navigator) {
    return navigator.serviceWorker;
  }
  return null;
}

/**
 * Whether service workers are supported in the current context.
 * @param {ServiceWorkerContainer} [container]  Optional override (tests).
 * @returns {boolean}
 */
export function isServiceWorkerSupported(container) {
  if (container) return true;
  return typeof navigator !== "undefined" && "serviceWorker" in navigator;
}

/**
 * Register the service worker and wire the update lifecycle.
 *
 * When a new worker reaches the `installed` state while one already controls the
 * page, `onUpdate` fires (a real update is waiting). Calling skipWaiting on that
 * registration activates it and reloads the page once.
 *
 * @param {RegisterOptions} [options]
 * @returns {Promise<?ServiceWorkerRegistration>} The registration, or null when
 *          unsupported / on failure (after onError).
 */
export async function registerServiceWorker(options = {}) {
  const container = resolveContainer(options);
  if (!container) {
    return null;
  }
  const url = options.url ?? "/sw.js";
  try {
    const registration = await container.register(
      url,
      options.scope ? { scope: options.scope } : undefined,
    );

    // A worker already waiting at registration time is an available update.
    if (registration.waiting && container.controller) {
      options.onUpdate?.(registration);
    }

    registration.addEventListener?.("updatefound", () => {
      const installing = registration.installing;
      if (!installing) return;
      installing.addEventListener("statechange", () => {
        if (installing.state === "installed") {
          if (container.controller) {
            // An update is ready and waiting behind the active worker.
            options.onUpdate?.(registration);
          } else {
            // First install — nothing was controlling before.
            options.onReady?.(registration);
          }
        }
      });
    });

    return registration;
  } catch (err) {
    options.onError?.(/** @type {Error} */ (err));
    return null;
  }
}

/**
 * Activate a waiting worker and reload the page when it takes control.
 *
 * Posts SKIP_WAITING to the waiting worker; the page reloads exactly once when
 * `controllerchange` fires, avoiding the reload loop of naive implementations.
 *
 * @param {ServiceWorkerRegistration} registration  The registration to update.
 * @param {Object} [deps]                            Injected for tests.
 * @param {ServiceWorkerContainer} [deps.container]  navigator.serviceWorker override.
 * @param {() => void} [deps.reload]                 location.reload override.
 * @returns {void}
 */
export function skipWaiting(registration, deps = {}) {
  const container =
    deps.container ??
    (typeof navigator !== "undefined" ? navigator.serviceWorker : null);
  const reload =
    deps.reload ??
    (() => {
      if (typeof location !== "undefined") location.reload();
    });

  const waiting = registration && registration.waiting;
  if (!waiting) return;

  let reloaded = false;
  container?.addEventListener?.("controllerchange", () => {
    if (reloaded) return;
    reloaded = true;
    reload();
  });
  waiting.postMessage({ type: "SKIP_WAITING" });
}

/**
 * Unregister every service worker for this origin (dev/reset helper).
 *
 * @param {ServiceWorkerContainer} [container]  Override (tests).
 * @returns {Promise<number>} The number of registrations removed.
 */
export async function unregisterAllServiceWorkers(container) {
  const c =
    container ??
    (typeof navigator !== "undefined" && "serviceWorker" in navigator
      ? navigator.serviceWorker
      : null);
  if (!c || typeof c.getRegistrations !== "function") return 0;
  const registrations = await c.getRegistrations();
  let count = 0;
  for (const registration of registrations) {
    const ok = await registration.unregister();
    if (ok) count += 1;
  }
  return count;
}
