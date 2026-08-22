// lists.js — the list events the core declares and the DOM has to detect.
//
// A list widget declares `on_end_reached` (fire near the end, for infinite
// scroll) and — on LazyColumn / LazyRow / RefreshControl — `on_refresh`
// (pull-to-refresh). Both resolve on the Python side through the plain
// `on_<type>` fallback, so nothing but the *detection* is missing: this module
// is that half, and it is shared by all three modes (mount() installs it).
//
// End-reached is deliberately **scroll-driven only**: it is evaluated when a
// scroll happens, never after a patch batch. A handler typically appends items,
// which re-renders the list — re-evaluating there would fire again on the taller
// list and grow it forever without the user moving. One crossing per scroll
// gesture, latched per key until the list scrolls back under its threshold.
//
// Two geometries count as "near the end", because both exist on the web:
//   * a bounded viewport that scrolls itself (LazyColumn with a height) —
//     progress is (scrollTop + clientHeight) / scrollHeight, which for a
//     virtualized list includes the reserved off-window space (virtualize.js),
//     so it tracks the real item_count and not just the materialized window;
//   * a list that flows in the page (SectionList, an unbounded LazyColumn) —
//     progress is how much of its box the page scroll has revealed.
//
// Verify in tests/client/lists.test.js (jsdom has no layout, so scroll and rect
// metrics are stubbed).

import { PULL_REFRESH_PX } from "./constants.js";
import { KEY_ATTR, TYPE_ATTR } from "./dom.js";

/** Marks a list that reports `end_reached`; the value is its threshold (0..1). */
const END_ATTR = "data-tw-end-threshold";

/** Marks a widget that reports `refresh`; the value is the pull axis (`y`/`x`). */
const REFRESH_ATTR = "data-tw-refresh";

/** Set by the app (via the `refreshing` prop) while the reload runs. */
const REFRESHING_ATTR = "data-tw-refreshing";

/** Set while the pull has passed the threshold, so the theme can show it. */
const ARMED_ATTR = "data-tw-pull-armed";

/** Threshold used when the attribute is absent or unparsable (the core's default). */
const DEFAULT_THRESHOLD = 0.8;

/**
 * Read a list's end-reached threshold, clamped to the meaningful `(0, 1]` range.
 *
 * @param {HTMLElement} el  The marked list element.
 * @returns {number}        The fraction of scroll progress that fires the event.
 */
function threshold(el) {
  const raw = Number.parseFloat(el.getAttribute(END_ATTR) ?? "");
  if (!Number.isFinite(raw) || raw <= 0) {
    return DEFAULT_THRESHOLD;
  }
  return Math.min(1, raw);
}

/**
 * Scroll progress of a list that scrolls its own box, or `null` when it doesn't.
 *
 * `null` (rather than 0) distinguishes "this element is not the scroller" from
 * "it is scrolled to the very top", so the caller can fall back to the page
 * geometry instead of reading a meaningless 0.
 *
 * @param {HTMLElement} el       The list element.
 * @param {boolean} horizontal   Whether the list scrolls along the x axis.
 * @returns {?number}            Progress in `0..1`, or null when not a scroller.
 */
function selfProgress(el, horizontal) {
  const extent = horizontal ? el.scrollWidth : el.scrollHeight;
  const client = horizontal ? el.clientWidth : el.clientHeight;
  const offset = horizontal ? el.scrollLeft : el.scrollTop;
  if (!(extent > client) || !(client > 0)) {
    return null;
  }
  return (offset + client) / extent;
}

/**
 * Scroll progress of a list that flows in the page, from its viewport rect.
 *
 * Measures how much of the element's box the viewport has revealed: 0 while its
 * top edge is still below the fold, 1 once its bottom edge reaches the bottom of
 * the viewport. A horizontal list uses the x axis and the viewport width.
 *
 * @param {HTMLElement} el       The list element.
 * @param {boolean} horizontal   Whether the list runs along the x axis.
 * @returns {number}             Progress in `0..1`.
 */
function pageProgress(el, horizontal) {
  const rect = typeof el.getBoundingClientRect === "function" ? el.getBoundingClientRect() : null;
  const view = horizontal ? (globalThis.innerWidth ?? 0) : (globalThis.innerHeight ?? 0);
  const extent = rect == null ? 0 : horizontal ? rect.width : rect.height;
  if (rect == null || !(view > 0) || !(extent > 0)) {
    return 0;
  }
  const revealed = view - (horizontal ? rect.left : rect.top);
  return Math.max(0, Math.min(1, revealed / extent));
}

/**
 * How far through a list the reader currently is, whichever geometry applies.
 *
 * @param {HTMLElement} el  The marked list element.
 * @returns {number}        Progress in `0..1`.
 */
function progressOf(el) {
  const horizontal = el.getAttribute(TYPE_ATTR) === "LazyRow";
  const self = selfProgress(el, horizontal);
  return self == null ? pageProgress(el, horizontal) : self;
}

/**
 * Find the nearest ancestor-or-self element that reports `refresh`.
 *
 * @param {EventTarget|null} target  The pointer event's target node.
 * @param {HTMLElement} root         The delegation root (search stops above it).
 * @returns {?HTMLElement}           The pullable element, or null.
 */
function refreshAncestor(target, root) {
  let node = /** @type {Node|null} */ (target);
  while (node != null && node.nodeType !== 1) {
    node = node.parentNode;
  }
  let el = /** @type {HTMLElement|null} */ (node);
  while (el != null) {
    if (el.hasAttribute?.(REFRESH_ATTR) && el.hasAttribute(KEY_ATTR)) {
      return el;
    }
    if (el === root) {
      break;
    }
    el = el.parentElement;
  }
  return null;
}

/**
 * Install list event detection (`end_reached` + pull-to-refresh) under `root`.
 *
 * End-reached: one capture-phase scroll listener on the document (falling back
 * to `root`) covers both geometries at once — a `scroll` on a bounded list
 * viewport does not bubble, and a page scroll fires on the document, so capture
 * sees both. Every marked list is then measured, and the ones past their
 * threshold report `end_reached` once, until they fall back under it.
 *
 * Refresh: the browser has no pull-to-refresh of its own for an element, so the
 * gesture is recognized from pointer events — a drag along the widget's axis,
 * started at its scroll origin (otherwise the drag is a scroll, not a pull) and
 * longer along that axis than across it. Passing {@link PULL_REFRESH_PX} arms the
 * pull (marked on the element, which is what the base theme draws); releasing
 * while armed reports `refresh`. A widget the app already marked as refreshing is
 * skipped, so holding the list down does not queue a second reload.
 *
 * @param {HTMLElement} root  The mount root.
 * @param {import("./transport.js").Transport} transport  The event sink.
 * @returns {{dispose: () => void}}
 */
export function installListEvents(root, transport) {
  /** Keys currently past their threshold, so a crossing reports exactly once. */
  const latched = new Set();

  const evaluate = () => {
    for (const node of root.querySelectorAll(`[${END_ATTR}]`)) {
      const el = /** @type {HTMLElement} */ (node);
      const key = el.getAttribute(KEY_ATTR);
      if (key == null) {
        continue;
      }
      if (progressOf(el) < threshold(el)) {
        latched.delete(key);
        continue;
      }
      if (latched.has(key)) {
        continue;
      }
      latched.add(key);
      transport.sendEvent({ type: "end_reached", key, payload: {} });
    }
  };

  const host = typeof document !== "undefined" ? document : root;
  host.addEventListener("scroll", evaluate, true);

  /** @type {Map<number, {el: HTMLElement, key: string, axis: string, x: number, y: number, armed: boolean}>} */
  const pulls = new Map();

  /** @param {PointerEvent} event */
  const onPointerDown = (event) => {
    const el = refreshAncestor(event.target, root);
    if (el == null || el.getAttribute(REFRESHING_ATTR) === "true") {
      return;
    }
    const key = el.getAttribute(KEY_ATTR);
    if (key == null) {
      return;
    }
    const axis = el.getAttribute(REFRESH_ATTR) === "x" ? "x" : "y";
    if ((axis === "x" ? el.scrollLeft : el.scrollTop) > 0) {
      return;
    }
    pulls.set(event.pointerId, {
      el,
      key,
      axis,
      x: event.clientX,
      y: event.clientY,
      armed: false,
    });
  };

  /** @param {PointerEvent} event */
  const onPointerMove = (event) => {
    const pull = pulls.get(event.pointerId);
    if (pull === undefined) {
      return;
    }
    const dx = event.clientX - pull.x;
    const dy = event.clientY - pull.y;
    const along = pull.axis === "x" ? dx : dy;
    const across = pull.axis === "x" ? dy : dx;
    pull.armed = along >= PULL_REFRESH_PX && along > Math.abs(across);
    if (pull.armed) {
      pull.el.setAttribute(ARMED_ATTR, "");
    } else {
      pull.el.removeAttribute(ARMED_ATTR);
    }
  };

  /** @param {PointerEvent} event */
  const onPointerUp = (event) => {
    const pull = pulls.get(event.pointerId);
    if (pull === undefined) {
      return;
    }
    pulls.delete(event.pointerId);
    pull.el.removeAttribute(ARMED_ATTR);
    if (pull.armed) {
      transport.sendEvent({ type: "refresh", key: pull.key, payload: {} });
    }
  };

  /** @param {PointerEvent} event */
  const onPointerCancel = (event) => {
    const pull = pulls.get(event.pointerId);
    if (pull === undefined) {
      return;
    }
    pulls.delete(event.pointerId);
    pull.el.removeAttribute(ARMED_ATTR);
  };

  root.addEventListener("pointerdown", onPointerDown);
  root.addEventListener("pointermove", onPointerMove);
  root.addEventListener("pointerup", onPointerUp);
  root.addEventListener("pointercancel", onPointerCancel);

  return {
    dispose() {
      host.removeEventListener("scroll", evaluate, true);
      root.removeEventListener("pointerdown", onPointerDown);
      root.removeEventListener("pointermove", onPointerMove);
      root.removeEventListener("pointerup", onPointerUp);
      root.removeEventListener("pointercancel", onPointerCancel);
      latched.clear();
      pulls.clear();
    },
  };
}
