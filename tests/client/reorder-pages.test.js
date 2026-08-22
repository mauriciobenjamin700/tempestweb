// ReorderableList and PageView: the two container gestures the DOM lacked.
//
// The core declares `on_reorder` and `on_page_change`; both were inert. A
// reorderable list rendered rows nobody could pick up, and a PageView rendered a
// plain box — no pages to swipe, nothing to report.
import { test } from "node:test";
import assert from "node:assert/strict";
import { freshDom } from "./setup.js";
import { applyPatches, buildElement, syncContainerGestures } from "../../client/dom.js";
import { bindEvents } from "../../client/events.js";
import { installPageViews } from "../../client/pages.js";
import { BASE_THEME_CSS } from "../../client/theme.js";
import { PAGE_SETTLE_MS } from "../../client/constants.js";

/** A mock Transport that records every sendEvent call. */
function mockTransport() {
  /** @type {import("../../client/transport.js").TWEvent[]} */
  const events = [];
  return { events, onPatches() {}, sendEvent: (e) => events.push(e), async close() {} };
}

/** A minimal DataTransfer stand-in: jsdom does not implement the real one. */
function fakeDataTransfer() {
  const store = {};
  return {
    effectAllowed: "",
    dropEffect: "",
    setData(type, value) {
      store[type] = String(value);
    },
    getData(type) {
      return store[type] ?? "";
    },
  };
}

/** Wait for a carousel to be considered settled (the page report is debounced). */
function settled() {
  return new Promise((resolve) => setTimeout(resolve, PAGE_SETTLE_MS + 40));
}

/** Dispatch a drag-family event carrying a dataTransfer, as a browser would. */
function dispatchDrag(dom, el, type, dataTransfer) {
  const event = new dom.window.Event(type, { bubbles: true, cancelable: true });
  Object.defineProperty(event, "dataTransfer", { value: dataTransfer });
  el.dispatchEvent(event);
  return event;
}

/** Build a ReorderableList of `n` rows under the dom root. */
function sortableList(dom, n = 3) {
  const el = buildElement({
    type: "ReorderableList",
    key: "tasks",
    props: {},
    children: Array.from({ length: n }, (_, i) => ({
      type: "Text",
      key: `t${i}`,
      props: { content: `Task ${i}` },
      children: [],
    })),
  });
  dom.root.appendChild(el);
  syncContainerGestures(dom.root);
  return el;
}

/** Build a PageView of `n` pages, with `width` px per page. */
function carousel(dom, { pages = 3, page = 0, width = 400 } = {}) {
  const el = buildElement({
    type: "PageView",
    key: "tour",
    props: { page },
    children: Array.from({ length: pages }, (_, i) => ({
      type: "Text",
      key: `p${i}`,
      props: { content: `Page ${i}` },
      children: [],
    })),
  });
  dom.root.appendChild(el);
  Object.defineProperty(el, "clientWidth", { value: width, configurable: true });
  el.scrollLeft = page * width;
  syncContainerGestures(dom.root);
  return el;
}

test("a reorderable list's rows are marked draggable", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const list = sortableList(dom);

  assert.equal(list.getAttribute("data-tw-reorder"), "");
  for (const row of list.children) {
    assert.equal(row.getAttribute("draggable"), "true");
    assert.equal(row.style.cursor, "grab");
  }
});

test("rows inserted by a later patch are marked too", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const list = sortableList(dom, 2);

  // A row arrives through an Insert on the *list*, which never passes through
  // the element's own props — the post-layout marking is what catches it.
  applyPatches(list, [
    { path: [], index: 2, node: { type: "Text", key: "t2", props: { content: "New" }, children: [] } },
  ]);
  assert.equal(list.children[2].getAttribute("draggable"), null, "not marked yet");

  syncContainerGestures(dom.root);
  assert.equal(list.children[2].getAttribute("draggable"), "true");
});

test("dragging a row onto another reports the two positions", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const list = sortableList(dom);
  const transport = mockTransport();
  bindEvents(dom.root, transport);
  const data = fakeDataTransfer();

  dispatchDrag(dom, list.children[0], "dragstart", data);
  assert.equal(data.getData("text/x-tw-reorder"), "0", "the source index rides on the drag");
  const over = dispatchDrag(dom, list.children[2], "dragover", data);
  assert.equal(over.defaultPrevented, true, "the browser needs this to allow the drop");
  dispatchDrag(dom, list.children[2], "drop", data);

  assert.deepEqual(transport.events, [
    { type: "reorder", key: "tasks", payload: { from_index: 0, to_index: 2 } },
  ]);
});

test("a drop back onto the same row reports nothing", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const list = sortableList(dom);
  const transport = mockTransport();
  bindEvents(dom.root, transport);
  const data = fakeDataTransfer();

  dispatchDrag(dom, list.children[1], "dragstart", data);
  dispatchDrag(dom, list.children[1], "drop", data);
  assert.deepEqual(transport.events, []);
});

test("a drag that starts inside a row still belongs to the row", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const list = buildElement({
    type: "ReorderableList",
    key: "tasks",
    props: {},
    children: [
      {
        type: "Container",
        key: "r0",
        props: {},
        children: [{ type: "Text", key: "label", props: { content: "Deep" }, children: [] }],
      },
      { type: "Container", key: "r1", props: {}, children: [] },
    ],
  });
  dom.root.appendChild(list);
  syncContainerGestures(dom.root);
  const transport = mockTransport();
  bindEvents(dom.root, transport);
  const data = fakeDataTransfer();

  const deep = list.children[0].firstElementChild;
  dispatchDrag(dom, deep, "dragstart", data);
  dispatchDrag(dom, list.children[1], "drop", data);

  assert.deepEqual(transport.events, [
    { type: "reorder", key: "tasks", payload: { from_index: 0, to_index: 1 } },
  ]);
});

test("a PageView carries its page and page count", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = carousel(dom, { pages: 4, page: 1 });

  assert.equal(el.getAttribute("data-tw-page"), "1");
  assert.equal(el.getAttribute("data-tw-pages"), "4");
});

test("scrolling to another page reports the change, once it settles", async () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = carousel(dom, { pages: 3, page: 0, width: 400 });
  const transport = mockTransport();
  installPageViews(dom.root, transport);

  el.scrollLeft = 800;
  el.dispatchEvent(new dom.window.Event("scroll", { bubbles: false }));
  assert.deepEqual(transport.events, [], "nothing while the scroll is still moving");
  await settled();

  assert.deepEqual(transport.events, [
    { type: "page_change", key: "tour", payload: { page: 2, previous: 0 } },
  ]);
  assert.equal(el.getAttribute("data-tw-page"), "2", "written back so a fast swipe reports once");
});

test("a scroll within the same page reports nothing", async () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = carousel(dom, { pages: 3, page: 0, width: 400 });
  const transport = mockTransport();
  installPageViews(dom.root, transport);

  el.scrollLeft = 120; // round(120/400) = 0, the page it is already on
  el.dispatchEvent(new dom.window.Event("scroll", { bubbles: false }));
  await settled();
  assert.deepEqual(transport.events, []);
});

test("a smooth scroll's intermediate positions are not reported", async () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = carousel(dom, { pages: 3, page: 0, width: 400 });
  const transport = mockTransport();
  installPageViews(dom.root, transport);

  // This is what "press Next" looks like in Chrome: the renderer sets the page,
  // the smooth scroll walks there, and every step in between rounds to the page
  // being left. Reporting those made the app undo its own move.
  el.setAttribute("data-tw-page", "1");
  for (const left of [40, 160, 300, 400]) {
    el.scrollLeft = left;
    el.dispatchEvent(new dom.window.Event("scroll", { bubbles: false }));
  }
  await settled();

  assert.deepEqual(transport.events, [], "only the resting position counts");
});

test("the app moving `page` scrolls the carousel there", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = carousel(dom, { pages: 3, page: 0, width: 400 });

  applyPatches(el, [{ path: [], set_props: { page: 2 }, unset_props: [] }]);

  assert.equal(el.scrollLeft, 800);
  assert.equal(el.getAttribute("data-tw-page"), "2");
});

test("the app's own page move does not report a change back", async () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = carousel(dom, { pages: 3, page: 0, width: 400 });
  const transport = mockTransport();
  installPageViews(dom.root, transport);

  applyPatches(el, [{ path: [], set_props: { page: 1 }, unset_props: [] }]);
  el.dispatchEvent(new dom.window.Event("scroll", { bubbles: false }));
  await settled();

  assert.deepEqual(transport.events, [], "no loop between the app and the carousel");
});

test("dispose stops reporting pages", async () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = carousel(dom);
  const transport = mockTransport();
  const handle = installPageViews(dom.root, transport);
  handle.dispose();

  el.scrollLeft = 800;
  el.dispatchEvent(new dom.window.Event("scroll", { bubbles: false }));
  await settled();
  assert.deepEqual(transport.events, []);
});

test("the base sheet makes the carousel snap and the rows grabbable", () => {
  assert.match(BASE_THEME_CSS, /\[data-tw-type="PageView"\][\s\S]*scroll-snap-type: x mandatory/);
  assert.match(BASE_THEME_CSS, /\[data-tw-type="PageView"\] > \*[\s\S]*scroll-snap-align: start/);
  assert.match(BASE_THEME_CSS, /\[data-tw-reorder\] > \*[\s\S]*cursor: grab/);
});
