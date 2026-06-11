// virtualize.js — scroll-driven windowing for virtualized lists.  PHASE E.2.
//
// The core materializes only a list's visible window (window_size items); the
// runtime slides that window when it receives a `scroll` wire event. This module
// is the client half: it watches a lazy viewport's scroll, and when the user
// reaches an edge it asks Python to slide the window by a page, keeping the DOM
// bounded to ~window_size nodes however large item_count is.
//
// Lazy viewports are marked by dom.js with data-tw-item-count / -window-size /
// -window-start. Scroll events do not bubble, so the listener is attached in the
// capture phase on the mount root and survives patch churn.
//
// Note: the scrollbar reflects the current window, not the full item_count — a
// proportional scrollbar needs an off-window sizer, a follow-up that the wire's
// child-indexed patches make non-trivial.

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
 * Measure a viewport's per-item pixel extent from its first child.
 * @param {HTMLElement} viewport
 * @returns {number} The item extent in px (0 when the window is empty).
 */
function itemExtent(viewport) {
  const first = viewport.firstElementChild;
  return first != null ? first.offsetHeight : 0;
}

/**
 * Install scroll-driven virtualization for every lazy viewport under `root`.
 *
 * When a viewport is scrolled to an edge, the window is slid by a page (half the
 * window, so a row of context is kept) toward that edge and a `scroll` wire event
 * reports the new window; scroll position is nudged off the edge so the next pull
 * keeps paging. Bounded to ~window_size DOM nodes regardless of item_count.
 *
 * @param {HTMLElement} root  The mount root.
 * @param {import("./transport.js").Transport} transport  The event sink.
 * @returns {{dispose: () => void}}  `dispose` removes the listener.
 */
export function installVirtualization(root, transport) {
  // Window start last reported per key, so repeated edge scrolls before the slide
  // lands don't resend the same window.
  const requested = new Map();

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
    const page = Math.max(1, Math.floor(windowSize / 2));
    const atBottom =
      viewport.scrollTop + viewport.clientHeight >= viewport.scrollHeight - extent;
    const atTop = viewport.scrollTop <= extent;

    let next = start;
    if (atBottom && start + windowSize < count) {
      next = Math.min(count - windowSize, start + page);
    } else if (atTop && start > 0) {
      next = Math.max(0, start - page);
    }
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

  // The window-start each viewport was last anchored at, so re-anchoring only
  // happens when a slide actually changed the window.
  const anchored = new Map();

  const reanchor = () => {
    for (const node of root.querySelectorAll(`[${LAZY_ATTR}]`)) {
      const viewport = /** @type {HTMLElement} */ (node);
      const key = viewport.getAttribute("data-tw-key");
      if (key == null) {
        continue;
      }
      const start = intAttr(viewport, "data-tw-window-start", 0);
      if (anchored.get(key) === start) {
        continue;
      }
      anchored.set(key, start);
      requested.set(key, start);
      // Park scroll at the middle of the window so neither edge is active; the
      // user must scroll to an edge again to page. Without this, replacing the
      // children pins scrollTop at an edge and the window oscillates.
      const span = viewport.scrollHeight - viewport.clientHeight;
      if (span > 0) {
        viewport.scrollTop = Math.floor(span / 2);
      }
    }
  };

  // scroll does not bubble — capture it on the root.
  root.addEventListener("scroll", onScroll, true);
  return {
    reanchor,
    dispose() {
      root.removeEventListener("scroll", onScroll, true);
    },
  };
}
