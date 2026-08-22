// Tests for client/lists.js — end_reached in both list geometries, plus the
// pull-to-refresh gesture. jsdom has no layout, so scroll metrics and rects are
// stubbed via defineProperty and pointer events are dispatched by hand.
import { test } from "node:test";
import assert from "node:assert/strict";
import { freshDom } from "./setup.js";
import { applyPatches, buildElement } from "../../client/dom.js";
import { installListEvents } from "../../client/lists.js";
import { PULL_REFRESH_PX } from "../../client/constants.js";

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

// --------------------------------------------------------------------------- //
// pull-to-refresh                                                             //
// --------------------------------------------------------------------------- //

/** Dispatch one pointer event on `target` (jsdom has no PointerEvent). */
function pointer(dom, target, type, { x = 0, y = 0 } = {}) {
  target.dispatchEvent(
    new dom.window.MouseEvent(type, { bubbles: true, clientX: x, clientY: y }),
  );
}

/** Drag from (0,0) by (dx, dy) over `target`, releasing at the end. */
function drag(dom, target, { dx = 0, dy = 0, release = "pointerup" } = {}) {
  pointer(dom, target, "pointerdown", { x: 0, y: 0 });
  pointer(dom, target, "pointermove", { x: dx, y: dy });
  pointer(dom, target, release, { x: dx, y: dy });
}

test("a widget that declares on_refresh is marked with its pull axis", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const column = listElement(dom, "LazyColumn", { item_count: 10, refreshing: false });
  const row = listElement(dom, "LazyRow", { item_count: 10, refreshing: false });
  const grid = listElement(dom, "LazyGrid", { item_count: 10 });

  assert.equal(column.getAttribute("data-tw-refresh"), "y");
  assert.equal(row.getAttribute("data-tw-refresh"), "x");
  assert.equal(grid.getAttribute("data-tw-refresh"), null, "a grid has no pull-to-refresh");
});

test("a RefreshControl owns a spinner, and `refreshing` announces the wait", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = listElement(dom, "RefreshControl", { refreshing: true });

  assert.equal(el.getAttribute("data-tw-refresh"), "y");
  assert.equal(el.querySelectorAll("[data-tw-part=\"spinner\"]").length, 1);
  assert.equal(el.getAttribute("data-tw-refreshing"), "true");
  assert.equal(el.getAttribute("aria-busy"), "true");

  applyPatches(el, [{ path: [], set_props: { refreshing: false }, unset_props: [] }]);
  assert.equal(el.getAttribute("data-tw-refreshing"), null);
  assert.equal(el.getAttribute("aria-busy"), null);
  assert.equal(
    el.querySelectorAll("[data-tw-part=\"spinner\"]").length,
    1,
    "the renderer-owned spinner is not duplicated by an update",
  );
});

test("pulling a list past the threshold reports refresh on release", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = listElement(dom, "LazyColumn", { item_count: 100, refreshing: false });
  const transport = mockTransport();
  installListEvents(dom.root, transport);

  drag(dom, el, { dy: PULL_REFRESH_PX + 10 });
  assert.deepEqual(transport.events, [{ type: "refresh", key: "L", payload: {} }]);
  assert.equal(el.getAttribute("data-tw-pull-armed"), null, "the mark is cleared on release");
});

test("the pull is marked while it is armed, so the theme can show it", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = listElement(dom, "LazyColumn", { item_count: 100, refreshing: false });
  installListEvents(dom.root, mockTransport());

  pointer(dom, el, "pointerdown", { x: 0, y: 0 });
  pointer(dom, el, "pointermove", { x: 0, y: PULL_REFRESH_PX + 5 });
  assert.equal(el.getAttribute("data-tw-pull-armed"), "");

  pointer(dom, el, "pointermove", { x: 0, y: 4 });
  assert.equal(el.getAttribute("data-tw-pull-armed"), null, "dragging back disarms it");
});

test("a pull short of the threshold reports nothing", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = listElement(dom, "LazyColumn", { item_count: 100, refreshing: false });
  const transport = mockTransport();
  installListEvents(dom.root, transport);

  drag(dom, el, { dy: PULL_REFRESH_PX - 1 });
  assert.deepEqual(transport.events, []);
});

test("a mostly-sideways drag is not a pull on a vertical list", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = listElement(dom, "LazyColumn", { item_count: 100, refreshing: false });
  const transport = mockTransport();
  installListEvents(dom.root, transport);

  drag(dom, el, { dx: 300, dy: PULL_REFRESH_PX + 10 });
  assert.deepEqual(transport.events, []);
});

test("a list already scrolled down is being scrolled, not pulled", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = listElement(dom, "LazyColumn", { item_count: 100, refreshing: false });
  const transport = mockTransport();
  installListEvents(dom.root, transport);
  Object.defineProperty(el, "scrollTop", { value: 120, configurable: true });

  drag(dom, el, { dy: PULL_REFRESH_PX + 40 });
  assert.deepEqual(transport.events, []);
});

test("a list already refreshing does not queue a second reload", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = listElement(dom, "LazyColumn", { item_count: 100, refreshing: true });
  const transport = mockTransport();
  installListEvents(dom.root, transport);

  drag(dom, el, { dy: PULL_REFRESH_PX + 40 });
  assert.deepEqual(transport.events, []);
});

test("a cancelled pull reports nothing and clears its mark", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = listElement(dom, "LazyColumn", { item_count: 100, refreshing: false });
  const transport = mockTransport();
  installListEvents(dom.root, transport);

  drag(dom, el, { dy: PULL_REFRESH_PX + 10, release: "pointercancel" });
  assert.deepEqual(transport.events, []);
  assert.equal(el.getAttribute("data-tw-pull-armed"), null);
});

test("a LazyRow is pulled along its own axis", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = listElement(dom, "LazyRow", { item_count: 100, refreshing: false });
  const transport = mockTransport();
  installListEvents(dom.root, transport);

  drag(dom, el, { dy: PULL_REFRESH_PX + 10 });
  assert.deepEqual(transport.events, [], "a vertical drag is not its pull");

  drag(dom, el, { dx: PULL_REFRESH_PX + 10 });
  assert.deepEqual(transport.events, [{ type: "refresh", key: "L", payload: {} }]);
});

test("a pull that starts on a child of the control still counts", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = listElement(dom, "RefreshControl", { refreshing: false });
  const transport = mockTransport();
  installListEvents(dom.root, transport);

  const spinner = el.querySelector("[data-tw-part=\"spinner\"]");
  drag(dom, spinner, { dy: PULL_REFRESH_PX + 10 });
  assert.deepEqual(transport.events, [{ type: "refresh", key: "L", payload: {} }]);
});

test("dispose stops the pull gesture too", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = listElement(dom, "LazyColumn", { item_count: 100, refreshing: false });
  const transport = mockTransport();
  const handle = installListEvents(dom.root, transport);
  handle.dispose();

  drag(dom, el, { dy: PULL_REFRESH_PX + 40 });
  assert.deepEqual(transport.events, []);
});
