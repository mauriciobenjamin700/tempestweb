// install-prompt.js — soft install prompt controller.  PHASE P0.
//
// Pure JS, no build step. Mirrors the React SDK's useBeforeInstallPrompt:
//   - capture the browser's `beforeinstallprompt` event and stash it (so the
//     native prompt does NOT fire cold);
//   - expose promptInstall() to fire the stashed prompt after a real gesture /
//     in-context moment;
//   - report installable / installed state and notify subscribers.
//
// The window target is injected (defaults to the global) so the whole flow is
// unit-testable under jsdom with a fake EventTarget. See
// tests/client/pwa-install-prompt.test.js.

/**
 * @typedef {Object} BeforeInstallPromptEvent
 * @property {() => void} preventDefault           Suppresses the mini-infobar.
 * @property {() => Promise<void>} prompt          Shows the native install prompt.
 * @property {Promise<{outcome: "accepted"|"dismissed", platform: string}>} userChoice
 *           Resolves with the user's choice after prompt().
 */

/**
 * @typedef {Object} InstallState
 * @property {boolean} canInstall   A deferred prompt is available to fire.
 * @property {boolean} installed    The app reports as installed (appinstalled or standalone).
 */

/**
 * @typedef {Object} InstallPromptController
 * @property {() => InstallState} getState
 *           Snapshot of the current install state.
 * @property {() => Promise<"accepted"|"dismissed"|"unavailable">} promptInstall
 *           Fire the stashed native prompt; resolves with the outcome (or
 *           "unavailable" when no prompt was captured / it was already used).
 * @property {(listener: (state: InstallState) => void) => () => void} subscribe
 *           Register a state listener; returns an unsubscribe function. The
 *           listener is invoked immediately with the current state.
 * @property {() => void} destroy
 *           Remove all event listeners (teardown).
 */

/**
 * Detect whether the app is currently running as an installed PWA.
 *
 * True when launched in a standalone display mode (Chromium/Android/desktop) or
 * via the iOS `navigator.standalone` flag.
 *
 * @param {Window} [win]   Window override (tests). Defaults to the global.
 * @returns {boolean} Whether the app is running installed/standalone.
 */
export function isStandalone(win) {
  const w = win ?? (typeof window !== "undefined" ? window : undefined);
  if (!w) return false;
  const mql =
    typeof w.matchMedia === "function"
      ? w.matchMedia("(display-mode: standalone)")
      : null;
  if (mql && mql.matches) return true;
  const nav = w.navigator;
  // iOS Safari exposes navigator.standalone for home-screen apps.
  return Boolean(nav && nav.standalone === true);
}

/**
 * Create a soft install-prompt controller.
 *
 * It listens for `beforeinstallprompt` (calling preventDefault so the browser's
 * mini-infobar is suppressed) and `appinstalled`. Nothing is shown to the user
 * automatically — the app calls promptInstall() after a meaningful gesture.
 *
 * @param {Object} [options]
 * @param {Window} [options.window]   Window/EventTarget override (tests).
 * @returns {InstallPromptController} The controller.
 */
export function createInstallPrompt(options = {}) {
  const win = options.window ?? (typeof window !== "undefined" ? window : null);

  /** @type {?BeforeInstallPromptEvent} */
  let deferred = null;
  let installed = win ? isStandalone(win) : false;

  /** @type {Set<(state: InstallState) => void>} */
  const listeners = new Set();

  /** @returns {InstallState} */
  function getState() {
    return { canInstall: deferred !== null, installed };
  }

  function notify() {
    const state = getState();
    for (const listener of listeners) listener(state);
  }

  /** @param {BeforeInstallPromptEvent} event */
  function onBeforeInstallPrompt(event) {
    // Prevent the cold mini-infobar; we drive the prompt in-context.
    if (typeof event.preventDefault === "function") event.preventDefault();
    deferred = event;
    notify();
  }

  function onAppInstalled() {
    installed = true;
    deferred = null;
    notify();
  }

  if (win && typeof win.addEventListener === "function") {
    win.addEventListener("beforeinstallprompt", onBeforeInstallPrompt);
    win.addEventListener("appinstalled", onAppInstalled);
  }

  /** @returns {Promise<"accepted"|"dismissed"|"unavailable">} */
  async function promptInstall() {
    if (!deferred || typeof deferred.prompt !== "function") {
      return "unavailable";
    }
    const event = deferred;
    // A deferred prompt can only be used once; clear it before awaiting.
    deferred = null;
    notify();
    await event.prompt();
    try {
      const choice = await event.userChoice;
      if (choice && choice.outcome === "accepted") {
        // appinstalled will also fire, but mark optimistically.
        return "accepted";
      }
      return "dismissed";
    } catch {
      return "dismissed";
    }
  }

  /** @param {(state: InstallState) => void} listener */
  function subscribe(listener) {
    listeners.add(listener);
    listener(getState());
    return () => listeners.delete(listener);
  }

  function destroy() {
    if (win && typeof win.removeEventListener === "function") {
      win.removeEventListener("beforeinstallprompt", onBeforeInstallPrompt);
      win.removeEventListener("appinstalled", onAppInstalled);
    }
    listeners.clear();
    deferred = null;
  }

  return { getState, promptInstall, subscribe, destroy };
}
