// Tests for client/lists.js — end_reached detection in both list geometries.
// jsdom has no layout, so scroll metrics and rects are stubbed via defineProperty.
import { test } from "node:test";
import assert from "node:assert/strict";
import { freshDom } from "./setup.js";
import { buildElement } from "../../client/dom.js";
import { installListEvents } from "../../client/lists.js";

/** A mock Transport recording sendEvent calls. */
function mockTransport() {
  const events = [];
  return { events, onPatches() {}, sendEvent(e) { events.push(e); }, async close() {} };
}

/** Stub an element's scroll geometry (jsdom reports 0 for all of it). */
function stubScroll(el, { extent, client, offset, horizontal = false }) {
  const names = horizontal
    ? ["scrollWidth", "clientWidth", "scrollLeft"]
    : ["scrollHeight", "clientHeight", "scrollTop"];
  const values = [extent, client, offset];
  names.forEach((name, i) => {
    Object.defineProperty(el, name, { value: values[i], configurable: true });
  });
}

/** Build a list element of `type` under the dom root, with `props`. */
function listElement(dom, type, props) {
  const el = buildElement({ type, key: "L", props, children: [] });
  dom.root.appendChild(el);
  return el;
}

/** Dispatch a scroll on `target` (capture reaches the document listener). */
function scroll(dom, target) {
  target.dispatchEvent(new dom.window.Event("scroll", { bubbles: false }));
}

test("buildElement marks a list with the threshold it wants end_reached at", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = listElement(dom, "LazyColumn", {
    item_count: 100,
    window_size: 20,
    end_reached_threshold: 0.9,
  });
  assert.equal(el.getAttribute("data-tw-end-threshold"), "0.9");
});

test("a SectionList is marked too — it reaches its end in page flow", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = listElement(dom, "SectionList", { sections: [], end_reached_threshold: 0.8 });
  assert.equal(el.getAttribute("data-tw-end-threshold"), "0.8");
});

test("scrolling a bounded list past its threshold reports end_reached once", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = listElement(dom, "LazyColumn", { item_count: 100, end_reached_threshold: 0.8 });
  const transport = mockTransport();
  installListEvents(dom.root, transport);

  // 1500 + 400 = 1900 of 2000 -> progress 0.95 >= 0.8.
  stubScroll(el, { extent: 2000, client: 400, offset: 1500 });
  scroll(dom, el);
  assert.deepEqual(transport.events, [{ type: "end_reached", key: "L", payload: {} }]);

  // Still inside the end zone: latched, so no second report.
  stubScroll(el, { extent: 2000, client: 400, offset: 1600 });
  scroll(dom, el);
  assert.equal(transport.events.length, 1);
});

test("scrolling back above the threshold re-arms the next crossing", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = listElement(dom, "LazyColumn", { item_count: 100, end_reached_threshold: 0.8 });
  const transport = mockTransport();
  installListEvents(dom.root, transport);

  stubScroll(el, { extent: 2000, client: 400, offset: 1600 });
  scroll(dom, el);
  stubScroll(el, { extent: 2000, client: 400, offset: 200 }); // progress 0.3
  scroll(dom, el);
  stubScroll(el, { extent: 2000, client: 400, offset: 1600 });
  scroll(dom, el);

  assert.equal(transport.events.length, 2);
});

test("a list short of its threshold reports nothing", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = listElement(dom, "LazyColumn", { item_count: 100, end_reached_threshold: 0.8 });
  const transport = mockTransport();
  installListEvents(dom.root, transport);

  stubScroll(el, { extent: 2000, client: 400, offset: 400 }); // progress 0.4
  scroll(dom, el);
  assert.deepEqual(transport.events, []);
});

test("the widget's own threshold decides when it fires", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = listElement(dom, "LazyColumn", { item_count: 100, end_reached_threshold: 0.5 });
  const transport = mockTransport();
  installListEvents(dom.root, transport);

  stubScroll(el, { extent: 2000, client: 400, offset: 800 }); // progress 0.6
  scroll(dom, el);
  assert.equal(transport.events.length, 1);
});

test("a LazyRow measures its end along the x axis", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = listElement(dom, "LazyRow", { item_count: 100, end_reached_threshold: 0.8 });
  const transport = mockTransport();
  installListEvents(dom.root, transport);

  // Vertically it looks untouched; horizontally it is at the end.
  stubScroll(el, { extent: 3000, client: 600, offset: 2200, horizontal: true });
  scroll(dom, el);
  assert.deepEqual(transport.events, [{ type: "end_reached", key: "L", payload: {} }]);
});

test("a list that flows in the page reaches its end from the page scroll", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  globalThis.innerHeight = 800;
  const el = listElement(dom, "SectionList", { sections: [], end_reached_threshold: 0.8 });
  const transport = mockTransport();
  installListEvents(dom.root, transport);

  // Box 2000px tall starting 1000px above the viewport top: 1800 of 2000 revealed.
  el.getBoundingClientRect = () => ({ top: -1000, left: 0, width: 400, height: 2000 });
  scroll(dom, dom.document);
  assert.deepEqual(transport.events, [{ type: "end_reached", key: "L", payload: {} }]);

  delete globalThis.innerHeight;
});

test("an in-flow list still below the fold reports nothing", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  globalThis.innerHeight = 800;
  const el = listElement(dom, "SectionList", { sections: [], end_reached_threshold: 0.8 });
  const transport = mockTransport();
  installListEvents(dom.root, transport);

  el.getBoundingClientRect = () => ({ top: 600, left: 0, width: 400, height: 2000 });
  scroll(dom, dom.document);
  assert.deepEqual(transport.events, []);

  delete globalThis.innerHeight;
});

test("dispose stops reporting", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = listElement(dom, "LazyColumn", { item_count: 100, end_reached_threshold: 0.8 });
  const transport = mockTransport();
  const handle = installListEvents(dom.root, transport);
  handle.dispose();

  stubScroll(el, { extent: 2000, client: 400, offset: 1600 });
  scroll(dom, el);
  assert.deepEqual(transport.events, []);
});
