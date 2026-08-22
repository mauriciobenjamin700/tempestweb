// focus.js — the rest of the modal contract: focus goes in, stays in, comes back.
//
// A modal overlay (Dialog, BottomSheet, ActionSheet) paints over the app and a
// click on the scrim or Escape dismisses it. Focus was left out: it stayed on
// whatever opened the overlay, so Tab walked the page *behind* the scrim — a
// keyboard user could type into a form they could not see, and a screen-reader
// user was never told the dialog existed.
//
// Three obligations, and this module is all three:
//   * on open, move focus into the overlay (its first focusable, or the overlay
//     itself, which is given `tabindex="-1"` so it can hold focus);
//   * while open, keep Tab / Shift+Tab inside it, wrapping at both ends;
//   * on close, return focus to the element that had it when the overlay opened,
//     so the reader lands back where they were.
//
// Non-modal overlays are left alone: a Menu or Popover has no scrim, a Toast is
// not something to be trapped in, and stealing focus for them would break the
// widget that opened them.
//
// Driven by `sync()` (called from mount's post-layout pass) rather than a
// MutationObserver: the mount already knows when the tree changed, and one
// explicit call per batch is cheaper and easier to reason about than a
// subscription that fires mid-patch, on trees that are momentarily incomplete.

/** Modal overlay types that own the keyboard while they are open. */
const MODAL_TYPES =
  '[data-tw-type="Dialog"],[data-tw-type="BottomSheet"],[data-tw-type="ActionSheet"]';

/** The overlay host `mount` patches the overlay layer into. */
const OVERLAY_HOST_ATTR = "data-tw-overlays";

/**
 * Elements that can take keyboard focus.
 *
 * `[tabindex="-1"]` is deliberately excluded: it is focusable by script (which is
 * how the overlay itself holds focus) but not by Tab, so including it would put
 * the container into its own tab cycle.
 */
const FOCUSABLE = [
  "a[href]",
  "area[href]",
  "button:not([disabled])",
  "input:not([disabled]):not([type=hidden])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "iframe",
  "object",
  "embed",
  '[contenteditable="true"]',
  '[tabindex]:not([tabindex="-1"])',
].join(",");

/**
 * The focusable descendants of `el`, in document order.
 *
 * Skips what is explicitly hidden, and asks `checkVisibility` where the browser
 * offers it, so a stop inside a collapsed section is not focused into silently.
 *
 * Deliberately **not** `offsetParent !== null`, the usual shortcut for "is this
 * laid out": that is null for a `position: fixed` element, which is exactly what
 * an overlay is — the check would call every stop in every modal hidden, and the
 * trap would fall back to focusing the box on real pages, not only under jsdom.
 *
 * @param {HTMLElement} el  The container to search.
 * @returns {HTMLElement[]} The focusable elements, possibly empty.
 */
function focusables(el) {
  return Array.from(el.querySelectorAll(FOCUSABLE)).filter((node) => {
    const candidate = /** @type {HTMLElement} */ (node);
    if (
      candidate.hasAttribute("hidden") ||
      candidate.getAttribute("aria-hidden") === "true"
    ) {
      return false;
    }
    if (typeof candidate.checkVisibility === "function") {
      return candidate.checkVisibility();
    }
    return true;
  });
}

/**
 * The top-most modal overlay currently mounted, or null when there is none.
 *
 * Overlays are z-ordered by document order in the host, so the last one is the
 * one on top — the same rule the dismiss handler uses.
 *
 * @param {HTMLElement} root  The mount root.
 * @returns {?HTMLElement}    The active modal, or null.
 */
function topModal(root) {
  const host = root.querySelector(`[${OVERLAY_HOST_ATTR}]`);
  if (host == null) {
    return null;
  }
  const modals = host.querySelectorAll(MODAL_TYPES);
  return modals.length === 0 ? null : /** @type {HTMLElement} */ (modals[modals.length - 1]);
}

/**
 * Install modal focus management for the overlays under `root`.
 *
 * `sync()` reconciles focus with whatever the last patch batch left mounted: it
 * captures and restores the outside focus, and moves focus into a newly opened
 * modal. The Tab trap is a document-level keydown listener, because focus can be
 * anywhere when the key is pressed.
 *
 * @param {HTMLElement} root  The mount root.
 * @returns {{sync: () => void, dispose: () => void}}
 */
export function installFocusTrap(root) {
  /** The modal that currently owns the keyboard, if any. */
  let active = null;
  /** Where focus was when that modal opened, to hand it back on close. */
  let restoreTo = null;

  const doc = root.ownerDocument;

  /** Reconcile focus with the currently mounted overlays. */
  const sync = () => {
    const modal = topModal(root);
    if (modal === active) {
      return;
    }
    if (modal == null) {
      const target = restoreTo;
      active = null;
      restoreTo = null;
      // Only give focus back if that element is still in the document: the same
      // batch may have removed the button that opened the overlay.
      if (target != null && doc != null && doc.contains(target)) {
        target.focus();
      }
      return;
    }
    if (active == null) {
      const current = doc == null ? null : /** @type {HTMLElement|null} */ (doc.activeElement);
      restoreTo = current != null && current !== doc?.body ? current : null;
    }
    active = modal;
    if (!modal.hasAttribute("tabindex")) {
      modal.setAttribute("tabindex", "-1");
    }
    const inside = focusables(modal);
    (inside[0] ?? modal).focus();
  };

  /**
   * Keep Tab inside the active modal.
   *
   * Wraps at both ends, and pulls focus back in when it had escaped (the browser
   * puts focus on the document body after the element holding it is removed, and
   * Tab from there would walk the page behind the scrim).
   *
   * @param {KeyboardEvent} event  The keydown event.
   * @returns {void}
   */
  const onKeyDown = (event) => {
    if (event.key !== "Tab" || active == null) {
      return;
    }
    const inside = focusables(active);
    if (inside.length === 0) {
      event.preventDefault();
      active.focus();
      return;
    }
    const current = /** @type {HTMLElement|null} */ (doc?.activeElement ?? null);
    const first = inside[0];
    const last = inside[inside.length - 1];
    if (current == null || !active.contains(current)) {
      event.preventDefault();
      (event.shiftKey ? last : first).focus();
      return;
    }
    if (event.shiftKey && current === first) {
      event.preventDefault();
      last.focus();
      return;
    }
    if (!event.shiftKey && current === last) {
      event.preventDefault();
      first.focus();
    }
  };

  if (doc != null) {
    doc.addEventListener("keydown", onKeyDown);
  }

  return {
    sync,
    dispose() {
      if (doc != null) {
        doc.removeEventListener("keydown", onKeyDown);
      }
      active = null;
      restoreTo = null;
    },
  };
}
