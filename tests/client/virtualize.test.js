// Tests for client/virtualize.js — lazy viewport marking + edge-paging scroll.
// jsdom has no layout, so item/scroll metrics are stubbed via defineProperty.
import { test } from "node:test";
import assert from "node:assert/strict";
import { freshDom } from "./setup.js";
import { buildElement } from "../../client/dom.js";
import { installVirtualization } from "../../client/virtualize.js";

/** A mock Transport recording sendEvent calls. */
function mockTransport() {
  const events = [];
  return { events, onPatches() {}, sendEvent(e) { events.push(e); }, async close() {} };
}

/** Build a LazyColumn element with `rendered` window children of height `h`. */
function lazyViewport(dom, { count, windowSize, start, rendered, h }) {
  const children = [];
  for (let i = 0; i < rendered; i++) {
    children.push({ type: "Text", key: String(start + i), props: { content: String(start + i) }, children: [] });
  }
  const node = {
    type: "LazyColumn",
    key: "L",
    props: { item_count: count, window_size: windowSize, window: [start, start + rendered] },
    children,
  };
  const el = buildElement(node);
  dom.root.appendChild(el);
  for (const child of el.children) {
    Object.defineProperty(child, "offsetHeight", { value: h, configurable: true });
  }
  return el;
}

/** Stub a viewport's scroll metrics (jsdom reports 0 for all of them). */
function stubScroll(el, { scrollTop, clientHeight, scrollHeight }) {
  el.scrollTop = scrollTop;
  Object.defineProperty(el, "clientHeight", { value: clientHeight, configurable: true });
  Object.defineProperty(el, "scrollHeight", { value: scrollHeight, configurable: true });
}

test("buildElement marks a LazyColumn as a scroll viewport with metadata", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = lazyViewport(dom, { count: 1000, windowSize: 10, start: 0, rendered: 10, h: 20 });
  assert.equal(el.getAttribute("data-tw-item-count"), "1000");
  assert.equal(el.getAttribute("data-tw-window-size"), "10");
  assert.equal(el.getAttribute("data-tw-window-start"), "0");
  assert.equal(el.style.overflowY, "auto");
});

test("scrolling to the bottom edge pages the window forward", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = lazyViewport(dom, { count: 1000, windowSize: 10, start: 0, rendered: 10, h: 20 });
  const transport = mockTransport();
  installVirtualization(dom.root, transport);

  // window 10 items * 20px = 200 content; viewport 100 tall; scrolled to bottom.
  stubScroll(el, { scrollTop: 100, clientHeight: 100, scrollHeight: 200 });
  el.dispatchEvent(new dom.window.Event("scroll", { bubbles: false }));

  assert.equal(transport.events.length, 1);
  // page = floor(10/2) = 5 -> next window [5, 15).
  assert.deepEqual(transport.events[0], {
    type: "scroll",
    key: "L",
    payload: { start: 5, end: 15 },
  });
});

test("scrolling back to the top edge pages the window backward", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = lazyViewport(dom, { count: 1000, windowSize: 10, start: 40, rendered: 10, h: 20 });
  const transport = mockTransport();
  installVirtualization(dom.root, transport);

  stubScroll(el, { scrollTop: 0, clientHeight: 100, scrollHeight: 200 });
  el.dispatchEvent(new dom.window.Event("scroll", { bubbles: false }));

  assert.equal(transport.events.length, 1);
  assert.deepEqual(transport.events[0], { type: "scroll", key: "L", payload: { start: 35, end: 45 } });
});

test("scrolling in the middle (no edge) reports nothing", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = lazyViewport(dom, { count: 1000, windowSize: 10, start: 40, rendered: 10, h: 20 });
  const transport = mockTransport();
  installVirtualization(dom.root, transport);

  stubScroll(el, { scrollTop: 60, clientHeight: 100, scrollHeight: 200 });
  el.dispatchEvent(new dom.window.Event("scroll", { bubbles: false }));
  assert.equal(transport.events.length, 0);
});
