// update-prompt.js — "new version available" banner.  PHASE P1.
//
// Pure JS, no build step. When registerServiceWorker (register.js) reports a
// waiting worker via onUpdate, the shell shows a small, unobtrusive banner; the
// user confirms and skipWaiting() activates the new worker and reloads the page
// once (on controllerchange). This lives in the shell — not the app view — so it
// works the same in every mode without the app cooperating, and needs no change
// to the core App.
//
// The document + skipWaiting are injected (defaults to the global) so the whole
// flow is unit-testable under jsdom. The shell passes register.js's own
// skipWaiting in; the built-in fallback below keeps this module self-contained
// (no cross-file import path, since register.js sits at the artifact root while
// this module lives under client/pwa/). See tests/client/pwa-update-prompt.test.js.

/** The id the banner element carries (so it is inserted at most once). */
export const UPDATE_BANNER_ID = "tw-update-banner";

/**
 * Activate a waiting worker and reload once it takes control (fallback).
 *
 * Mirrors register.js's `skipWaiting`; used when the caller does not inject one.
 * Posts SKIP_WAITING to the waiting worker and reloads exactly once on the
 * `controllerchange` event (avoiding a reload loop).
 *
 * @param {ServiceWorkerRegistration} registration  The registration to update.
 * @returns {void}
 */
function fallbackSkipWaiting(registration) {
  const waiting = registration && registration.waiting;
  if (!waiting) return;
  const container =
    typeof navigator !== "undefined" ? navigator.serviceWorker : null;
  let reloaded = false;
  if (container && typeof container.addEventListener === "function") {
    container.addEventListener("controllerchange", () => {
      if (reloaded) return;
      reloaded = true;
      if (typeof location !== "undefined") location.reload();
    });
  }
  waiting.postMessage({ type: "SKIP_WAITING" });
}

/**
 * Build the update banner element (not attached to the DOM).
 *
 * @param {Document} doc                 The document to create nodes in.
 * @param {Object} [opts]
 * @param {string} [opts.message]        The banner text.
 * @param {string} [opts.buttonLabel]    The confirm button label.
 * @param {() => void} [opts.onApply]    Called when the button is clicked.
 * @returns {HTMLElement} The banner element.
 */
export function createUpdateBanner(doc, opts = {}) {
  const message = opts.message ?? "A new version is available.";
  const buttonLabel = opts.buttonLabel ?? "Reload";

  const banner = doc.createElement("div");
  banner.id = UPDATE_BANNER_ID;
  banner.setAttribute("role", "status");
  banner.style.cssText = [
    "position:fixed",
    "left:50%",
    "bottom:16px",
    "transform:translateX(-50%)",
    "display:flex",
    "gap:12px",
    "align-items:center",
    "max-width:calc(100vw - 32px)",
    "padding:10px 16px",
    "border-radius:10px",
    "background:#1f1f22",
    "color:#fff",
    "font:14px/1.4 system-ui,sans-serif",
    "box-shadow:0 4px 16px rgba(0,0,0,0.3)",
    "z-index:2147483647",
  ].join(";");

  const label = doc.createElement("span");
  label.textContent = message;

  const button = doc.createElement("button");
  button.type = "button";
  button.textContent = buttonLabel;
  button.style.cssText = [
    "border:0",
    "border-radius:8px",
    "padding:6px 14px",
    "background:#6750a4",
    "color:#fff",
    "font:inherit",
    "font-weight:600",
    "cursor:pointer",
  ].join(";");
  button.addEventListener("click", () => {
    if (typeof opts.onApply === "function") opts.onApply();
  });

  banner.appendChild(label);
  banner.appendChild(button);
  return banner;
}

/**
 * Show the "update available" banner for a waiting service worker.
 *
 * Idempotent: a banner already present (same id) is not duplicated. Clicking the
 * button activates the waiting worker (skipWaiting), which reloads the page once
 * when the new worker takes control.
 *
 * @param {ServiceWorkerRegistration} registration  The registration with a
 *        waiting worker (from registerServiceWorker's onUpdate).
 * @param {Object} [opts]
 * @param {Document} [opts.document]     Document override (tests).
 * @param {(reg: ServiceWorkerRegistration) => void} [opts.skipWaiting]
 *        Override the activate/reload routine (tests).
 * @param {string} [opts.message]        The banner text.
 * @param {string} [opts.buttonLabel]    The confirm button label.
 * @returns {?HTMLElement} The banner element, or null when no document exists.
 */
export function showUpdatePrompt(registration, opts = {}) {
  const doc =
    opts.document ?? (typeof document !== "undefined" ? document : null);
  if (!doc || !doc.body) return null;
  const existing = doc.getElementById(UPDATE_BANNER_ID);
  if (existing) return existing;

  const apply = opts.skipWaiting ?? fallbackSkipWaiting;
  const banner = createUpdateBanner(doc, {
    message: opts.message,
    buttonLabel: opts.buttonLabel,
    onApply: () => apply(registration),
  });
  doc.body.appendChild(banner);
  return banner;
}
