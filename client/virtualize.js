// virtualize.js — scroll-driven windowing for virtualized lists.  PHASE E.2.
//
// The core materializes only a list's visible window (window_size items); the
// runtime slides that window when it receives a `scroll` wire event. This module
// is the client half: it maps scroll position to the visible window, reserves the
// off-window scroll space so the scrollbar spans the whole item_count, and reports
// the window to Python — keeping the DOM bounded to ~window_size nodes.
//
// Off-window space is reserved with `::before` / `::after` pseudo-elements on the
// viewport (heights driven by an injected stylesheet), NOT child elements, so the
// window items keep their patch-path indices (0..window_size-1). `::before` pushes
// the window down to its true offset; `::after` stands in for the rows below.
//
// Lazy viewports are marked by dom.js with data-tw-item-count / -window-size /
// -window-start. Scroll events do not bubble, so the listener is attached in the
// capture phase on the mount root and survives patch churn.

import { VIRT_STYLE_ID as STYLE_ID } from "./constants.js";

const LAZY_ATTR = "data-tw-item-count";

/**
 * Read a non-negative integer data attribute, defaulting when absent/invalid.
 * @param {HTMLElement} el
 * @param {string} name
 * @param {number} fallback
 * @returns {number}
 */
function intAttr(el, name, fallback) {
  const raw = el.getAttribute(name);
  const value = raw == null ? NaN : Number.parseInt(raw, 10);
  return Number.isFinite(value) ? value : fallback;
}

/**
 * Measure a viewport's per-item pixel extent from its first window child.
 * @param {HTMLElement} viewport
 * @returns {number} The item extent in px (0 when the window is empty).
 */
function itemExtent(viewport) {
  const first = viewport.firstElementChild;
  return first != null ? first.offsetHeight : 0;
}

/**
 * The shared stylesheet that carries each list's spacer pseudo-element heights.
 * @returns {?HTMLStyleElement}
 */
function styleSheet() {
  if (typeof document === "undefined") {
    return null;
  }
  let el = document.getElementById(STYLE_ID);
  if (el == null) {
    el = document.createElement("style");
    el.id = STYLE_ID;
    document.head.appendChild(el);
  }
  return /** @type {HTMLStyleElement} */ (el);
}

/**
 * Install scroll-driven virtualization for every lazy viewport under `root`.
 *
 * Maps `scrollTop` to the top item index and reports a `scroll` wire event when
 * the window changes; `refresh()` (re-run after each patch batch) reserves the
 * off-window scroll space so the scrollbar is proportional to `item_count`. About
 * a third of the window is kept as leading context above the viewport top. The
 * last window start reported per key is remembered so repeated scroll ticks before
 * the slide lands don't resend the same window. Because `scroll` does not bubble,
 * the listener is registered in the capture phase on the root.
 *
 * @param {HTMLElement} root  The mount root.
 * @param {import("./transport.js").Transport} transport  The event sink.
 * @returns {{refresh: () => void, dispose: () => void}}
 */
export function installVirtualization(root, transport) {
  const requested = new Map();

  /** Rebuild the spacer stylesheet for every lazy viewport under `root`. */
  const refresh = () => {
    const sheet = styleSheet();
    if (sheet == null) {
      return;
    }
    const rules = [];
    for (const node of root.querySelectorAll(`[${LAZY_ATTR}]`)) {
      const viewport = /** @type {HTMLElement} */ (node);
      const key = viewport.getAttribute("data-tw-key");
      if (key == null) {
        continue;
      }
      const count = intAttr(viewport, LAZY_ATTR, 0);
      const start = intAttr(viewport, "data-tw-window-start", 0);
      const rendered = viewport.childElementCount;
      const extent = itemExtent(viewport);
      if (extent <= 0 || count <= rendered) {
        continue;
      }
      const before = start * extent;
      const after = Math.max(0, count - start - rendered) * extent;
      const escaped =
        typeof globalThis.CSS?.escape === "function"
          ? globalThis.CSS.escape(key)
          : key.replace(/["\\]/g, "\\$&");
      const sel = `[${LAZY_ATTR}][data-tw-key="${escaped}"]`;
      rules.push(`${sel}::before{content:"";display:block;height:${before}px}`);
      rules.push(`${sel}::after{content:"";display:block;height:${after}px}`);
    }
    sheet.textContent = rules.join("\n");
  };

  /** @param {Event} event */
  const onScroll = (event) => {
    const viewport = /** @type {HTMLElement} */ (event.target);
    if (
      viewport == null ||
      typeof viewport.hasAttribute !== "function" ||
      !viewport.hasAttribute(LAZY_ATTR)
    ) {
      return;
    }
    const key = viewport.getAttribute("data-tw-key");
    if (key == null) {
      return;
    }
    const count = intAttr(viewport, LAZY_ATTR, 0);
    const windowSize = intAttr(viewport, "data-tw-window-size", viewport.childElementCount);
    const start = intAttr(viewport, "data-tw-window-start", 0);
    const extent = itemExtent(viewport);
    if (extent <= 0 || windowSize <= 0 || windowSize >= count) {
      return;
    }
    const lead = Math.floor(windowSize / 3);
    const top = Math.floor(viewport.scrollTop / extent);
    const maxStart = Math.max(0, count - windowSize);
    const next = Math.min(maxStart, Math.max(0, top - lead));
    if (next === start || requested.get(key) === next) {
      return;
    }
    requested.set(key, next);
    transport.sendEvent({
      type: "scroll",
      key,
      payload: { start: next, end: Math.min(count, next + windowSize) },
    });
  };

  root.addEventListener("scroll", onScroll, true);
  return {
    refresh,
    dispose() {
      root.removeEventListener("scroll", onScroll, true);
      const sheet = typeof document !== "undefined" ? document.getElementById(STYLE_ID) : null;
      if (sheet != null) {
        sheet.textContent = "";
      }
    },
  };
}
