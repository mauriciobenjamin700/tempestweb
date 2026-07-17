// connectivity-banner.js — offline/online status banner.  PHASE P2.
//
// Pure JS, no build step. A shell-level banner (like update-prompt.js) shown
// while the browser is offline and removed when connectivity returns, so the
// user always knows their actions are being queued (offline queue) rather than
// lost. It lives in the shell — not the app view — so it works the same in every
// mode without the app cooperating, reflecting the core's ConnectivityEvent on
// the JS side via the connectivity watch in ../native/network.js.
//
// The document/window/navigator and the connectivity watch are injected
// (defaulting to the globals) so the whole flow is unit-testable under jsdom.
// See tests/client/pwa-connectivity-banner.test.js.

import { networkWatch } from "../native/network.js";

/** The id the banner element carries (so it is inserted at most once). */
export const CONNECTIVITY_BANNER_ID = "tw-connectivity-banner";

/**
 * Build the offline banner element (not attached to the DOM).
 *
 * @param {Document} doc              The document to create nodes in.
 * @param {Object} [opts]
 * @param {string} [opts.message]     The banner text.
 * @returns {HTMLElement} The banner element.
 */
export function createConnectivityBanner(doc, opts = {}) {
  const message =
    opts.message ??
    "You're offline — changes are saved and will sync when you reconnect.";

  const banner = doc.createElement("div");
  banner.id = CONNECTIVITY_BANNER_ID;
  banner.setAttribute("role", "status");
  banner.setAttribute("aria-live", "polite");
  banner.style.cssText = [
    "position:fixed",
    "left:50%",
    "top:16px",
    "transform:translateX(-50%)",
    "display:flex",
    "gap:8px",
    "align-items:center",
    "max-width:calc(100vw - 32px)",
    "padding:8px 16px",
    "border-radius:10px",
    "background:#7a3e00",
    "color:#fff",
    "font:14px/1.4 system-ui,sans-serif",
    "box-shadow:0 4px 16px rgba(0,0,0,0.3)",
    "z-index:2147483647",
  ].join(";");

  const dot = doc.createElement("span");
  dot.setAttribute("aria-hidden", "true");
  dot.style.cssText = [
    "width:8px",
    "height:8px",
    "border-radius:50%",
    "background:#ffb020",
    "flex:0 0 auto",
  ].join(";");

  const label = doc.createElement("span");
  label.textContent = message;

  banner.appendChild(dot);
  banner.appendChild(label);
  return banner;
}

/**
 * Read the current online state from a navigator (defaults to online).
 * @param {?Navigator} nav
 * @returns {boolean} True when online.
 */
function isOnline(nav) {
  return nav ? nav.onLine !== false : true;
}

/**
 * Mount the connectivity banner and keep it in sync with the network state.
 *
 * Shows the banner while offline and removes it when connectivity returns,
 * reflecting the initial state immediately and then every online/offline
 * transition via ../native/network.js's connectivity watch. Idempotent per
 * document: the banner id guards against duplicates.
 *
 * @param {Object} [opts]
 * @param {Document} [opts.document]   Document override (tests).
 * @param {Window} [opts.window]       Window override (tests).
 * @param {Navigator} [opts.navigator] Navigator override (tests).
 * @param {string} [opts.message]      The offline banner text.
 * @param {(args: Object, emit: (p: Object) => void, deps: Object) => (() => void)} [opts.watch]
 *        Connectivity watch override (default: networkWatch).
 * @returns {() => void} A teardown that removes the banner and its listeners.
 */
export function mountConnectivityBanner(opts = {}) {
  const doc =
    opts.document ?? (typeof document !== "undefined" ? document : null);
  if (!doc || !doc.body) return () => {};
  const win =
    opts.window ?? (typeof window !== "undefined" ? window : globalThis);
  const nav =
    opts.navigator ?? (typeof navigator !== "undefined" ? navigator : null);
  const watch = opts.watch ?? networkWatch;
  const message = opts.message;

  /** @type {?HTMLElement} */
  let banner = doc.getElementById(CONNECTIVITY_BANNER_ID);

  const render = (online) => {
    if (!online && !banner) {
      banner = createConnectivityBanner(doc, { message });
      doc.body.appendChild(banner);
    } else if (online && banner) {
      banner.remove();
      banner = null;
    }
  };

  render(isOnline(nav));
  const teardown = watch(
    {},
    (payload) => render(payload.event.online !== false),
    { window: win, navigator: nav },
  );

  return () => {
    teardown();
    if (banner) {
      banner.remove();
      banner = null;
    }
  };
}
