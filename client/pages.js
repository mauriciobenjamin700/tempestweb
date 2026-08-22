// pages.js — a PageView is a carousel, and the DOM has to say which page it is on.
//
// `PageView` declares `page` plus `on_page_change`, and the handler never fired:
// the widget rendered as a plain box, so there were no pages to swipe between and
// nothing to report. The base sheet makes it a snapping horizontal scroller (one
// child per viewport width, `scroll-snap-align`), which gets swipe on touch,
// trackpad and shift+wheel for free — the browser is good at this. What the
// browser does not do is tell the app *which* page it landed on.
//
// This module is that half: on scroll, the page under the viewport is
// `round(scrollLeft / clientWidth)`, and when it differs from the page the app
// last rendered (`data-tw-page`), it reports
// `{type: "page_change", key, payload: {page, previous}}` — the shape of the
// core's `PageChangeEvent`.
//
// The page is reported only once the scrolling has stopped, and that is not a
// nicety: a carousel scrolls smoothly, so a single move — whether the reader
// flicked it or the app moved `page` from a button — produces a stream of scroll
// events whose intermediate positions round to the page being *left*. Reporting
// those made the app fight itself: press "Next", the renderer scrolls towards
// page 1, the first intermediate scroll reports "back to page 0", and the app
// obediently goes back. Measured in Chrome, with the click and the bogus
// `page_change` landing in the same breath.

import { PAGE_SETTLE_MS } from "./constants.js";
import { PAGE_ATTR } from "./dom.js";

/**
 * Which page a carousel is currently showing.
 *
 * @param {HTMLElement} el  The PageView element.
 * @returns {?number}       The page index, or null when it cannot be measured.
 */
function pageOf(el) {
  const width = el.clientWidth;
  if (!(width > 0)) {
    return null;
  }
  return Math.round(el.scrollLeft / width);
}

/**
 * Install page reporting for every `PageView` under `root`.
 *
 * One capture-phase scroll listener on the document, for the same reason
 * virtualization uses one: a scroll inside an element does not bubble, and
 * capture sees it anyway.
 *
 * @param {HTMLElement} root  The mount root.
 * @param {import("./transport.js").Transport} transport  The event sink.
 * @returns {{dispose: () => void}}
 */
export function installPageViews(root, transport) {
  /** Pending settle timers, one per carousel. @type {Map<HTMLElement, number>} */
  const settling = new Map();

  /**
   * Report the page a carousel came to rest on, if it is a new one.
   *
   * @param {HTMLElement} el  The carousel.
   * @returns {void}
   */
  const settle = (el) => {
    settling.delete(el);
    const key = el.getAttribute("data-tw-key");
    const page = pageOf(el);
    if (key == null || page == null) {
      return;
    }
    const parsed = Number.parseInt(el.getAttribute(PAGE_ATTR) ?? "0", 10);
    const known = Number.isFinite(parsed) ? parsed : 0;
    if (page === known) {
      return;
    }
    // Written back before sending: the app answers with a rebuild, and until it
    // lands this attribute is what stops the next settle from reporting again.
    el.setAttribute(PAGE_ATTR, String(page));
    transport.sendEvent({
      type: "page_change",
      key,
      payload: { page, previous: known },
    });
  };

  /** @param {Event} event */
  const onScroll = (event) => {
    const el = /** @type {HTMLElement} */ (event.target);
    if (el == null || typeof el.hasAttribute !== "function" || !el.hasAttribute(PAGE_ATTR)) {
      return;
    }
    const pending = settling.get(el);
    if (pending !== undefined) {
      clearTimeout(pending);
    }
    settling.set(el, setTimeout(() => settle(el), PAGE_SETTLE_MS));
  };

  const host = typeof document !== "undefined" ? document : root;
  host.addEventListener("scroll", onScroll, true);

  return {
    dispose() {
      host.removeEventListener("scroll", onScroll, true);
      for (const timer of settling.values()) {
        clearTimeout(timer);
      }
      settling.clear();
    },
  };
}
