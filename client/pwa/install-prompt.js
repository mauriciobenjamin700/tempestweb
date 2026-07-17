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
 * @property {"native"|"ios"|"manual"} method   How the user can install here.
 */

/** Default decline cooldown: don't re-nag for 7 days. */
export const INSTALL_DECLINE_COOLDOWN_MS = 7 * 24 * 60 * 60 * 1000;

/** localStorage key for the last install-prompt decline timestamp. */
export const INSTALL_DECLINE_KEY = "tw-install-declined-at";

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
 * Detect an iOS browser (iPhone/iPad/iPod), including iPadOS masquerading as Mac.
 *
 * iOS has no `beforeinstallprompt` — installing is a manual Share → "Add to Home
 * Screen" — so the UI must show a tutorial instead of a native prompt button.
 *
 * @param {Window} [win]   Window override (tests). Defaults to the global.
 * @returns {boolean} Whether this is an iOS browser.
 */
export function isIOS(win) {
  const w = win ?? (typeof window !== "undefined" ? window : undefined);
  const nav = w && w.navigator;
  if (!nav) return false;
  const ua = String(nav.userAgent || nav.vendor || "");
  if (/iPad|iPhone|iPod/.test(ua)) return true;
  // iPadOS 13+ reports a Mac UA but exposes touch — treat as iOS.
  return /Macintosh/.test(ua) && typeof nav.maxTouchPoints === "number" && nav.maxTouchPoints > 1;
}

/**
 * Classify how the user can install the app here.
 *
 * ``"native"`` when a deferred `beforeinstallprompt` is available (Chromium),
 * ``"ios"`` on iOS (manual Share → Add to Home), else ``"manual"`` (e.g. Firefox
 * desktop) — the UI picks a native button vs. a platform tutorial accordingly.
 *
 * @param {boolean} hasDeferredPrompt   Whether a prompt was captured.
 * @param {Window} [win]                Window override (tests).
 * @returns {"native"|"ios"|"manual"} The install method.
 */
export function installMethod(hasDeferredPrompt, win) {
  if (hasDeferredPrompt) return "native";
  if (isIOS(win)) return "ios";
  return "manual";
}

/**
 * Resolve a Storage for the decline cooldown (injected or global localStorage).
 * @param {Storage} [storage]
 * @returns {?Storage}
 */
function _declineStorage(storage) {
  return storage ?? (typeof localStorage !== "undefined" ? localStorage : null);
}

/**
 * Record that the user just declined the install prompt (starts the cooldown).
 *
 * @param {Object} [opts]
 * @param {Storage} [opts.storage]   Storage override (default localStorage).
 * @param {number} [opts.now]        Epoch ms (default Date.now), injectable for tests.
 * @returns {void}
 */
export function recordInstallDecline(opts = {}) {
  const storage = _declineStorage(opts.storage);
  if (!storage) return;
  const now = opts.now ?? Date.now();
  try {
    storage.setItem(INSTALL_DECLINE_KEY, String(now));
  } catch {
    // Best-effort: a blocked write just means we may re-ask sooner.
  }
}

/**
 * Whether an install prompt may be shown, honoring the decline cooldown.
 *
 * @param {Object} [opts]
 * @param {Storage} [opts.storage]      Storage override (default localStorage).
 * @param {number} [opts.now]           Epoch ms (default Date.now).
 * @param {number} [opts.cooldownMs]    Cooldown window (default 7 days).
 * @returns {boolean} True when outside the cooldown (or nothing recorded).
 */
export function canPromptInstall(opts = {}) {
  const storage = _declineStorage(opts.storage);
  if (!storage) return true;
  let raw = null;
  try {
    raw = storage.getItem(INSTALL_DECLINE_KEY);
  } catch {
    return true;
  }
  if (!raw) return true;
  const declinedAt = Number(raw);
  if (!Number.isFinite(declinedAt)) return true;
  const now = opts.now ?? Date.now();
  const cooldownMs = opts.cooldownMs ?? INSTALL_DECLINE_COOLDOWN_MS;
  return now - declinedAt >= cooldownMs;
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
    return {
      canInstall: deferred !== null,
      installed,
      method: installMethod(deferred !== null, win ?? undefined),
    };
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
