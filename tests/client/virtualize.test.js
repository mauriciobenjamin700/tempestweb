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

test("a grid reserves space by row, and its spacers span the row", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  globalThis.CSS = dom.window.CSS;
  const children = [];
  for (let i = 0; i < 12; i++) {
    children.push({ type: "Text", key: String(i), props: { content: String(i) }, children: [] });
  }
  const el = buildElement({
    type: "LazyGrid",
    key: "G",
    props: { item_count: 90, window_size: 12, columns: 3, window: [0, 12] },
    children,
  });
  dom.root.appendChild(el);
  for (const child of el.children) {
    Object.defineProperty(child, "offsetHeight", { value: 40, configurable: true });
  }
  const v = installVirtualization(dom.root, transportNoop());
  v.refresh();

  // 78 items off-window over 3 columns is 26 rows, not 78: reserving per item
  // would make the scrollbar describe a list three times too long.
  const sheet = dom.document.getElementById("tw-virt-styles").textContent;
  assert.match(sheet, /::after\{[^}]*height:1040px\}/);
  // A pseudo-element takes a grid *cell* unless it is told to span the row.
  assert.match(sheet, /::after\{[^}]*grid-column:1\/-1;/);
  assert.match(sheet, /::before\{[^}]*grid-column:1\/-1;/);
});

test("a single-column list keeps the arithmetic it always had", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  globalThis.CSS = dom.window.CSS;
  lazyViewport(dom, { count: 100, windowSize: 10, start: 10, rendered: 10, h: 20 });
  const v = installVirtualization(dom.root, transportNoop());
  v.refresh();
  const sheet = dom.document.getElementById("tw-virt-styles").textContent;
  assert.match(sheet, /::before\{[^}]*height:200px\}/);
  assert.match(sheet, /::after\{[^}]*height:1600px\}/);
  assert.ok(!sheet.includes("grid-column"), "no grid rule for a plain list");
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
