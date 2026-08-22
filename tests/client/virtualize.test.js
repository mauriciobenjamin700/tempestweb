// Tests for client/virtualize.js — marking, scroll→window mapping, spacers.
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

test("buildElement marks a LazyColumn as a scroll viewport with metadata", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = lazyViewport(dom, { count: 1000, windowSize: 30, start: 0, rendered: 30, h: 20 });
  assert.equal(el.getAttribute("data-tw-item-count"), "1000");
  assert.equal(el.getAttribute("data-tw-window-size"), "30");
  assert.equal(el.getAttribute("data-tw-window-start"), "0");
  assert.equal(el.style.overflowY, "auto");
});

test("scrolling maps scrollTop to a window start (with leading context)", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  globalThis.CSS = dom.window.CSS;
  const el = lazyViewport(dom, { count: 1000, windowSize: 30, start: 0, rendered: 30, h: 20 });
  const transport = mockTransport();
  installVirtualization(dom.root, transport);

  el.scrollTop = 2000; // 2000 / 20 = item 100 at the top
  el.dispatchEvent(new dom.window.Event("scroll", { bubbles: false }));

  assert.equal(transport.events.length, 1);
  // lead = floor(30/3) = 10 -> start = 100 - 10 = 90.
  assert.deepEqual(transport.events[0], {
    type: "scroll",
    key: "L",
    payload: { start: 90, end: 120 },
  });
});

test("scrolling that does not change the window reports nothing", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  globalThis.CSS = dom.window.CSS;
  const el = lazyViewport(dom, { count: 1000, windowSize: 30, start: 0, rendered: 30, h: 20 });
  const transport = mockTransport();
  installVirtualization(dom.root, transport);

  el.scrollTop = 100; // top item 5; start = max(0, 5-10) = 0 == current
  el.dispatchEvent(new dom.window.Event("scroll", { bubbles: false }));
  assert.equal(transport.events.length, 0);
});

test("refresh writes proportional spacer rules for the full item_count", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  globalThis.CSS = dom.window.CSS;
  const el = lazyViewport(dom, { count: 1000, windowSize: 30, start: 40, rendered: 30, h: 20 });
  const v = installVirtualization(dom.root, transportNoop());
  v.refresh();

  const sheet = dom.document.getElementById("tw-virt-styles");
  assert.ok(sheet, "stylesheet created");
  // before = start*extent = 40*20 = 800; after = (1000-40-30)*20 = 18600.
  assert.match(sheet.textContent, /::before\{content:"";display:block;flex:0 0 auto;height:800px\}/);
  assert.match(sheet.textContent, /::after\{content:"";display:block;flex:0 0 auto;height:18600px\}/);
});

test("the spacers refuse to shrink, or the scrollbar describes only the window", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  globalThis.CSS = dom.window.CSS;
  lazyViewport(dom, { count: 200, windowSize: 30, start: 0, rendered: 30, h: 35 });
  const v = installVirtualization(dom.root, transportNoop());
  v.refresh();

  // A lazy viewport is a flex container, so a spacer is a flex item: without
  // flex:0 0 auto the browser shrinks it to nothing and the reserved 5950px
  // never reach the scroll extent (measured in Chrome: scrollHeight stayed at
  // 1050 — the 30 materialized rows — until the spacers stopped shrinking).
  const rules = dom.document.getElementById("tw-virt-styles").textContent.split("\n");
  assert.equal(rules.length, 2);
  for (const rule of rules) {
    assert.match(rule, /flex:0 0 auto/);
  }
});

function transportNoop() {
  return { onPatches() {}, sendEvent() {}, async close() {} };
}
