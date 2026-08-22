// Drag and drop: the Draggable/DragTarget contract, end to end in the client.
//
// The core has always had both widgets and the SSR renderer drew their boxes, but
// the DOM renderer left them as anonymous divs: nothing was marked `draggable`,
// no listener watched for a drop, and no wire event type routed to `on_drag` /
// `on_drop`. A "drag-and-drop board" rendered and did nothing in every mode.
import { test } from "node:test";
import assert from "node:assert/strict";
import { freshDom } from "./setup.js";
import {
  applyPatches,
  buildElement,
  DRAG_DATA_ATTR,
  DROP_TARGET_ATTR,
} from "../../client/dom.js";
import { bindEvents } from "../../client/events.js";

/** A mock Transport that records every sendEvent call. */
function mockTransport() {
  /** @type {import("../../client/transport.js").TWEvent[]} */
  const events = [];
  return {
    events,
    onPatches() {},
    sendEvent(event) {
      events.push(event);
    },
    async close() {},
  };
}

/** A minimal DataTransfer stand-in: jsdom does not implement the real one. */
function fakeDataTransfer(initial = {}) {
  const store = { ...initial };
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

/**
 * Dispatch a drag-family event carrying a dataTransfer, as a browser would.
 * @param {*} dom            The jsdom handle.
 * @param {HTMLElement} el   The element to dispatch on.
 * @param {string} type      "dragstart" | "dragover" | "drop".
 * @param {*} dataTransfer   The DataTransfer stand-in.
 * @returns {Event}          The dispatched event (to inspect defaultPrevented).
 */
function dispatchDrag(dom, el, type, dataTransfer) {
  const event = new dom.window.Event(type, { bubbles: true, cancelable: true });
  Object.defineProperty(event, "dataTransfer", { value: dataTransfer });
  Object.defineProperty(event, "clientX", { value: 12 });
  Object.defineProperty(event, "clientY", { value: 34 });
  el.dispatchEvent(event);
  return event;
}

/** Build a board: one Draggable card and one DragTarget column. */
function mountBoard() {
  const dom = freshDom();
  globalThis.document = dom.document;
  const tree = buildElement({
    type: "Column",
    key: "root",
    props: {},
    children: [
      {
        type: "Draggable",
        key: "drag-c1",
        props: { drag_data: "c1:Backlog" },
        children: [
          { type: "Text", key: "card-c1", props: { content: "a card" }, children: [] },
        ],
      },
      {
        type: "DragTarget",
        key: "drop-Done",
        props: {},
        children: [
          { type: "Text", key: "col-Done", props: { content: "Done" }, children: [] },
        ],
      },
    ],
  });
  dom.root.appendChild(tree);
  return { dom, tree };
}

test("a Draggable renders as a real draggable element carrying its payload", () => {
  const { tree } = mountBoard();
  const card = tree.querySelector('[data-tw-key="drag-c1"]');
  assert.equal(card.getAttribute("draggable"), "true");
  assert.equal(card.getAttribute(DRAG_DATA_ATTR), "c1:Backlog");
  assert.equal(card.style.cursor, "grab");
});

test("a DragTarget is marked as a drop target", () => {
  const { tree } = mountBoard();
  const column = tree.querySelector('[data-tw-key="drop-Done"]');
  assert.equal(column.hasAttribute(DROP_TARGET_ATTR), true);
});

test("dragstart puts the payload on the dataTransfer and emits drag", () => {
  const { dom, tree } = mountBoard();
  const transport = mockTransport();
  bindEvents(dom.root, transport);

  const data = fakeDataTransfer();
  // Dispatch on the inner text, as a browser would: the payload lives on the
  // Draggable ancestor.
  dispatchDrag(dom, tree.querySelector('[data-tw-key="card-c1"]'), "dragstart", data);

  assert.equal(data.getData("text/plain"), "c1:Backlog");
  assert.equal(data.effectAllowed, "move");
  assert.deepEqual(transport.events, [
    { type: "drag", key: "drag-c1", payload: { data: "c1:Backlog", x: 12, y: 34 } },
  ]);
});

test("dragover on a target accepts the drop", () => {
  const { dom, tree } = mountBoard();
  bindEvents(dom.root, mockTransport());

  const data = fakeDataTransfer();
  const event = dispatchDrag(
    dom,
    tree.querySelector('[data-tw-key="col-Done"]'),
    "dragover",
    data,
  );

  // Without preventDefault the browser refuses the drop and `drop` never fires.
  assert.equal(event.defaultPrevented, true);
  assert.equal(data.dropEffect, "move");
});

test("drop emits the payload against the target's key", () => {
  const { dom, tree } = mountBoard();
  const transport = mockTransport();
  bindEvents(dom.root, transport);

  const data = fakeDataTransfer({ "text/plain": "c1:Backlog" });
  const event = dispatchDrag(
    dom,
    tree.querySelector('[data-tw-key="col-Done"]'),
    "drop",
    data,
  );

  assert.equal(event.defaultPrevented, true);
  assert.deepEqual(transport.events, [
    { type: "drop", key: "drop-Done", payload: { data: "c1:Backlog", x: 12, y: 34 } },
  ]);
});

test("dragging something that is not a Draggable emits nothing", () => {
  const { dom, tree } = mountBoard();
  const transport = mockTransport();
  bindEvents(dom.root, transport);

  dispatchDrag(dom, tree, "dragstart", fakeDataTransfer());
  dispatchDrag(dom, tree, "drop", fakeDataTransfer());

  assert.deepEqual(transport.events, []);
});

test("a cleared drag_data leaves an empty payload, not a stale one", () => {
  const { dom, tree } = mountBoard();
  const card = tree.querySelector('[data-tw-key="drag-c1"]');
  // The same widget re-rendered with no payload.
  applyPatches(card, [{ path: [], set_props: { drag_data: null } }]);
  assert.equal(card.getAttribute(DRAG_DATA_ATTR), "");
  const transport = mockTransport();
  bindEvents(dom.root, transport);
  dispatchDrag(dom, card, "dragstart", fakeDataTransfer());
  assert.deepEqual(transport.events, [
    { type: "drag", key: "drag-c1", payload: { data: "", x: 12, y: 34 } },
  ]);
});
