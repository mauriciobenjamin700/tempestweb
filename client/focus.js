// focus.js — the focus half of the modal contract.
//
// A modal overlay already gets `role=dialog`, `aria-modal=true`, a scrim, and a
// dismiss on Escape or on a click outside. What was missing is where the keyboard
// is: focus stayed on whatever opened the overlay, so Tab walked the page behind
// the scrim — reachable by keyboard, unreachable by pointer, and announced by a
// screen reader as if the modal were not there.
//
// This closes the three remaining obligations:
//
//   1. On open, move focus into the overlay.
//   2. While open, keep Tab and Shift+Tab inside it.
//   3. On close, give focus back to the element that opened it.
//
// Scoped to the modal overlays — Dialog, BottomSheet, ActionSheet. A Menu or
// Popover is anchored and has no scrim, so trapping it would strand the keyboard
// in a transient surface; a Toast is not interactive at all.
//
// State is synced from `mount()` after each patch batch rather than from a
// MutationObserver: patches are the only way an overlay appears, so the explicit
// call is both cheaper and deterministic under the test runner.

/** Overlay types that own the keyboard while they are open. */
const MODAL_TYPES =
  '[data-tw-type="Dialog"],[data-tw-type="BottomSheet"],[data-tw-type="ActionSheet"]';

/**
 * What counts as tabbable. `[tabindex="-1"]` is focusable but not tabbable, so it
 * is excluded here and reached only by the fallback that focuses the overlay box.
 */
const TABBABLE = [
  "a[href]",
  "area[href]",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "button:not([disabled])",
  "iframe",
  "object",
  "embed",
  '[tabindex]:not([tabindex="-1"])',
  '[contenteditable="true"]',
].join(",");

/**
 * The tabbable descendants of an element, in document order.
 *
 * Skips what is explicitly hidden, and asks `checkVisibility` when the browser
 * offers it, so a stop inside a collapsed section is not focused into silently.
 *
 * Deliberately **not** `offsetParent !== null`, the usual shortcut for "is it
 * laid out": that is null for a `position: fixed` element, which is what an
 * overlay is — the check would report every stop in every modal as hidden and
 * the trap would fall back to the box on real pages, not just under jsdom.
 *
 * @param {HTMLElement} el
 * @returns {HTMLElement[]}
 */
function tabbable(el) {
  return Array.from(el.querySelectorAll(TABBABLE)).filter((node) => {
    const box = /** @type {HTMLElement} */ (node);
    if (box.hasAttribute("hidden") || box.getAttribute("aria-hidden") === "true") {
      return false;
    }
    if (typeof box.checkVisibility === "function") {
      return box.checkVisibility();
    }
    return true;
  });
}

/**
 * The top-most modal overlay inside a host, or `null` when there is none.
 *
 * Overlays stack in ascending z-order, so the last match is the one on top and
 * the one that owns the keyboard.
 *
 * @param {HTMLElement|null} host
 * @returns {HTMLElement|null}
 */
function topModal(host) {
  if (host == null) {
    return null;
  }
  const found = host.querySelectorAll(MODAL_TYPES);
  return found.length === 0 ? null : /** @type {HTMLElement} */ (found[found.length - 1]);
}

/**
 * Install modal focus management for an overlay host.
 *
 * @param {() => (HTMLElement|null)} host  Returns the overlay host, or null when
 *     no overlay has ever been rendered (the host is created lazily).
 * @param {Document} [doc]  The document to bind (defaults to the global).
 * @returns {{sync: () => void, dispose: () => void}}
 */
export function installFocusTrap(host, doc) {
  const target = doc ?? (typeof document !== "undefined" ? document : null);
  if (target == null) {
    return { sync() {}, dispose() {} };
  }

  /** @type {HTMLElement|null} The modal currently holding the keyboard. */
  let trapped = null;
  /** @type {HTMLElement|null} Where focus goes when the last modal closes. */
  let restoreTo = null;

  const focusInto = (modal) => {
    const first = tabbable(modal)[0];
    if (first != null) {
      first.focus();
      return;
    }
    // A modal with nothing tabbable in it still has to take the keyboard, or Tab
    // would walk the page behind the scrim.
    if (!modal.hasAttribute("tabindex")) {
      modal.setAttribute("tabindex", "-1");
    }
    modal.focus();
  };

  const sync = () => {
    const modal = topModal(host());
    if (modal === trapped) {
      return;
    }
    if (modal != null) {
      if (trapped === null) {
        const active = /** @type {HTMLElement|null} */ (target.activeElement);
        restoreTo = active != null && active !== target.body ? active : null;
      }
      trapped = modal;
      focusInto(modal);
      return;
    }
    trapped = null;
    const back = restoreTo;
    restoreTo = null;
    if (back != null && typeof back.focus === "function" && back.isConnected) {
      back.focus();
    }
  };

  /**
   * Keep Tab inside the trapped modal.
   *
   * @param {KeyboardEvent} event
   * @returns {void}
   */
  const onKeyDown = (event) => {
    if (event.key !== "Tab" || trapped == null) {
      return;
    }
    const stops = tabbable(trapped);
    if (stops.length === 0) {
      event.preventDefault();
      return;
    }
    const first = stops[0];
    const last = stops[stops.length - 1];
    const active = target.activeElement;
    const inside = active != null && trapped.contains(/** @type {Node} */ (active));
    if (event.shiftKey && (!inside || active === first)) {
      event.preventDefault();
      last.focus();
      return;
    }
    if (!event.shiftKey && (!inside || active === last)) {
      event.preventDefault();
      first.focus();
    }
  };

  target.addEventListener("keydown", onKeyDown);

  return {
    sync,
    dispose() {
      target.removeEventListener("keydown", onKeyDown);
      trapped = null;
      restoreTo = null;
    },
  };
}
