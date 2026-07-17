// native/install.js — PWA install-prompt capability.
//
// Wraps the soft install controller (client/pwa/install-prompt.js) in a single
// process-wide instance so Python can ask whether the app is installable and
// fire the stashed `beforeinstallprompt` after a real gesture. The controller is
// created on first import so its listeners attach as early as the native bundle
// loads (suppressing the browser mini-infobar when it catches the event).

import { createInstallPrompt } from "../pwa/install-prompt.js";

/** @type {ReturnType<typeof createInstallPrompt> | null} */
let _controller = null;

/**
 * Lazily create (and cache) the install-prompt controller.
 * @param {import("./index.js").NativeDeps} [deps]
 * @returns {ReturnType<typeof createInstallPrompt>}
 */
function controller(deps) {
  if (_controller) return _controller;
  const win = (deps && /** @type {any} */ (deps).window) || globalThis;
  _controller = createInstallPrompt({ window: win });
  return _controller;
}

// Attach listeners as early as this module loads.
if (typeof globalThis !== "undefined" && globalThis.addEventListener) {
  controller();
}

/**
 * Report the current install state.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{can_install:boolean, installed:boolean, method:string}>}
 */
export async function installState(_args, deps) {
  const state = controller(deps).getState();
  return {
    can_install: Boolean(state.canInstall),
    installed: Boolean(state.installed),
    method: state.method,
  };
}

/**
 * Fire the stashed native install prompt.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{outcome:"accepted"|"dismissed"|"unavailable"}>}
 */
export async function installPrompt(_args, deps) {
  const outcome = await controller(deps).promptInstall();
  return { outcome };
}
