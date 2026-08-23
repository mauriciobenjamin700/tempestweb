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

test("a window past the end of a shrunken list asks for the last page", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  globalThis.CSS = dom.window.CSS;
  // The stuck state: the app slid to [45, 75), then a refresh cut the list to 25
  // items. The core's clamp takes that to [25, 25) — zero rows — and with no rows
  // there is no scroll, so no event can ever put it back. Measured in
  // examples/list_demo: "25 of 200 items" over an empty box.
  const el = buildElement({
    type: "LazyColumn",
    key: "rows",
    props: { item_count: 25, window_size: 30, window: [45, 75] },
    children: [],
  });
  dom.root.appendChild(el);
  const transport = mockTransport();
  const v = installVirtualization(dom.root, transport);
  v.refresh();

  assert.deepEqual(transport.events, [
    { type: "scroll", key: "rows", payload: { start: 0, end: 25 } },
  ]);
});

test("the recovery asks for the last page, not the top", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  globalThis.CSS = dom.window.CSS;
  const el = buildElement({
    type: "LazyColumn",
    key: "rows",
    props: { item_count: 100, window_size: 30, window: [90, 120] },
    children: [],
  });
  dom.root.appendChild(el);
  const transport = mockTransport();
  installVirtualization(dom.root, transport).refresh();

  // 100 items over a 30-row window: the last page starts at 70, and the reader
  // keeps the end of the list they were looking at.
  assert.deepEqual(transport.events, [
    { type: "scroll", key: "rows", payload: { start: 70, end: 100 } },
  ]);
});

test("a window that still fits is left alone", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  globalThis.CSS = dom.window.CSS;
  lazyViewport(dom, { count: 200, windowSize: 30, start: 40, rendered: 30, h: 20 });
  const transport = mockTransport();
  installVirtualization(dom.root, transport).refresh();
  assert.deepEqual(transport.events, [], "no corrective scroll for a valid window");
});

test("the recovery is asked for once, not on every patch batch", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  globalThis.CSS = dom.window.CSS;
  const el = buildElement({
    type: "LazyColumn",
    key: "rows",
    props: { item_count: 25, window_size: 30, window: [45, 75] },
    children: [],
  });
  dom.root.appendChild(el);
  const transport = mockTransport();
  const v = installVirtualization(dom.root, transport);
  v.refresh();
  v.refresh();
  assert.equal(transport.events.length, 1);
});

test("a list with items and no rendered rows is recovered, whatever the attribute says", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  globalThis.CSS = dom.window.CSS;
  // The shape the stuck state actually has in Mode C: the slide lives in the
  // app, so the element still reads window-start 0 — what gives it away is that
  // a list of 25 items materialized none.
  const el = buildElement({
    type: "LazyColumn",
    key: "rows",
    props: { item_count: 25, window_size: 30 },
    children: [],
  });
  dom.root.appendChild(el);
  const transport = mockTransport();
  installVirtualization(dom.root, transport).refresh();

  assert.deepEqual(transport.events, [
    { type: "scroll", key: "rows", payload: { start: 0, end: 25 } },
  ]);
});

test("an empty list is left alone — there is nothing to recover to", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  globalThis.CSS = dom.window.CSS;
  const el = buildElement({
    type: "LazyColumn",
    key: "rows",
    props: { item_count: 0, window_size: 30 },
    children: [],
  });
  dom.root.appendChild(el);
  const transport = mockTransport();
  installVirtualization(dom.root, transport).refresh();
  assert.deepEqual(transport.events, []);
});
