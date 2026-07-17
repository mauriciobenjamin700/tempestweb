// post-install-redirect.js — overlay shown right after the app is installed.  P0.
//
// Pure JS, no build step. Adopted from the famachapp-pwa PostInstallRedirect:
// when the browser fires `appinstalled`, the tab that triggered the install is
// still an ordinary browser tab — the user should switch to the freshly installed
// standalone app. This shows a full-screen overlay nudging them there, and its
// button best-effort closes the install tab (browsers may block window.close();
// the overlay then just stays with the instruction).
//
// Opt-in (the app calls mountPostInstallRedirect) rather than auto-mounted, since
// not every app wants a full-screen takeover. Document/window are injected so the
// flow is unit-testable under jsdom. See tests/client/pwa-post-install-redirect.test.js.

import { isStandalone } from "./install-prompt.js";

/** The id the overlay element carries (so it is inserted at most once). */
export const POST_INSTALL_OVERLAY_ID = "tw-post-install-overlay";

/**
 * Build the post-install overlay element (not attached to the DOM).
 *
 * @param {Document} doc              The document to create nodes in.
 * @param {Object} [opts]
 * @param {string} [opts.message]     The overlay text.
 * @param {string} [opts.buttonLabel] The confirm button label.
 * @param {() => void} [opts.onOpen]  Called when the button is clicked.
 * @returns {HTMLElement} The overlay element.
 */
export function createPostInstallOverlay(doc, opts = {}) {
  const message =
    opts.message ?? "App installed — open it from your home screen.";
  const buttonLabel = opts.buttonLabel ?? "Open the app";

  const overlay = doc.createElement("div");
  overlay.id = POST_INSTALL_OVERLAY_ID;
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.style.cssText = [
    "position:fixed",
    "inset:0",
    "display:flex",
    "flex-direction:column",
    "gap:16px",
    "align-items:center",
    "justify-content:center",
    "padding:32px",
    "text-align:center",
    "background:#111",
    "color:#fff",
    "font:16px/1.5 system-ui,sans-serif",
    "z-index:2147483647",
  ].join(";");

  const label = doc.createElement("p");
  label.textContent = message;
  label.style.cssText = "max-width:28rem;margin:0";

  const button = doc.createElement("button");
  button.type = "button";
  button.textContent = buttonLabel;
  button.style.cssText = [
    "border:0",
    "border-radius:8px",
    "padding:10px 20px",
    "background:#6750a4",
    "color:#fff",
    "font:inherit",
    "font-weight:600",
    "cursor:pointer",
  ].join(";");
  button.addEventListener("click", () => {
    if (typeof opts.onOpen === "function") opts.onOpen();
  });

  overlay.appendChild(label);
  overlay.appendChild(button);
  return overlay;
}

/**
 * Show a post-install overlay when the app is installed.
 *
 * Listens for `appinstalled` and shows the overlay once (idempotent per
 * document). The button best-effort closes the install tab. A no-op when already
 * running standalone (there's nothing to redirect to). Returns a teardown that
 * removes the overlay and its listener.
 *
 * @param {Object} [opts]
 * @param {Document} [opts.document]   Document override (tests).
 * @param {Window} [opts.window]       Window override (tests).
 * @param {string} [opts.message]      The overlay text.
 * @param {string} [opts.buttonLabel]  The confirm button label.
 * @returns {() => void} A teardown that removes the overlay and its listener.
 */
export function mountPostInstallRedirect(opts = {}) {
  const doc =
    opts.document ?? (typeof document !== "undefined" ? document : null);
  if (!doc || !doc.body) return () => {};
  const win =
    opts.window ?? (typeof window !== "undefined" ? window : globalThis);

  const show = () => {
    if (isStandalone(win)) return;
    if (doc.getElementById(POST_INSTALL_OVERLAY_ID)) return;
    const overlay = createPostInstallOverlay(doc, {
      message: opts.message,
      buttonLabel: opts.buttonLabel,
      onOpen: () => {
        try {
          if (typeof win.close === "function") win.close();
        } catch {
          // Browsers may block window.close(); the overlay stays with the hint.
        }
      },
    });
    doc.body.appendChild(overlay);
  };

  const onInstalled = () => show();
  if (win && typeof win.addEventListener === "function") {
    win.addEventListener("appinstalled", onInstalled);
  }

  return () => {
    if (win && typeof win.removeEventListener === "function") {
      win.removeEventListener("appinstalled", onInstalled);
    }
    const existing = doc.getElementById(POST_INSTALL_OVERLAY_ID);
    if (existing) existing.remove();
  };
}
