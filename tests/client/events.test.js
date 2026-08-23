// Tests for client/events.js — delegated capture -> transport.sendEvent.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fixture, freshDom } from "./setup.js";
import { buildElement } from "../../client/dom.js";
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

/** Build the counter tree under a fresh jsdom root; returns dom + the tree. */
function mountCounter() {
  const dom = freshDom();
  globalThis.document = dom.document;
  const tree = buildElement(fixture("node_initial.json"));
  dom.root.appendChild(tree);
  return { dom, tree };
}

test("clicking a Button calls sendEvent with its key", () => {
  const { dom, tree } = mountCounter();
  const transport = mockTransport();
  bindEvents(dom.root, transport);

  const incButton = tree.querySelector("[data-tw-key=\"inc\"]");
  incButton.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));

  assert.equal(transport.events.length, 1);
  assert.deepEqual(transport.events[0], { type: "click", key: "inc", payload: {} });
});

test("the dec Button reports its own key", () => {
  const { dom, tree } = mountCounter();
  const transport = mockTransport();
  bindEvents(dom.root, transport);

  tree
    .querySelector("[data-tw-key=\"dec\"]")
    .dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));

  assert.equal(transport.events[0].key, "dec");
});

test("a click on an unkeyed element sends nothing", () => {
  const { dom, tree } = mountCounter();
  const transport = mockTransport();
  bindEvents(dom.root, transport);

  // The Row (index 1) has no key; clicking it directly resolves no widget.
  tree.children[1].dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
  assert.equal(transport.events.length, 0);
});

test("a click bubbling up from inside a keyed widget uses the keyed ancestor", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  // A keyed button wrapping an inner span; click the span.
  const button = dom.document.createElement("button");
  button.setAttribute("data-tw-key", "wrap");
  const inner = dom.document.createElement("span");
  button.appendChild(inner);
  dom.root.appendChild(button);

  const transport = mockTransport();
  bindEvents(dom.root, transport);
  inner.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));

  assert.equal(transport.events[0].key, "wrap");
});

test("input event carries the control value in payload", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const input = dom.document.createElement("input");
  input.setAttribute("data-tw-key", "field");
  input.value = "hello";
  dom.root.appendChild(input);

  const transport = mockTransport();
  bindEvents(dom.root, transport);
  input.dispatchEvent(new dom.window.Event("input", { bubbles: true }));

  assert.deepEqual(transport.events[0], {
    type: "input",
    key: "field",
    payload: { value: "hello" },
  });
});

test("change event carries the control value in payload", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const input = dom.document.createElement("input");
  input.setAttribute("data-tw-key", "field");
  input.value = "x";
  dom.root.appendChild(input);

  const transport = mockTransport();
  bindEvents(dom.root, transport);
  input.dispatchEvent(new dom.window.Event("change", { bubbles: true }));
  assert.deepEqual(transport.events[0].payload, { value: "x" });
});

test("the unbind function detaches all listeners", () => {
  const { dom, tree } = mountCounter();
  const transport = mockTransport();
  const unbind = bindEvents(dom.root, transport);
  unbind();

  tree
    .querySelector("[data-tw-key=\"inc\"]")
    .dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
  assert.equal(transport.events.length, 0);
});

/** Build a keyed GestureDetector element under a fresh root. */
function mountGesture() {
  const dom = freshDom();
  globalThis.document = dom.document;
  const node = {
    type: "GestureDetector",
    key: "g",
    props: {},
    children: [{ type: "Text", key: "t", props: { content: "swipe me" }, children: [] }],
  };
  const el = buildElement(node);
  dom.root.appendChild(el);
  return { dom, el };
}

test("a quick pointer press/release over a GestureDetector emits a tap", () => {
  const { dom, el } = mountGesture();
  const transport = mockTransport();
  bindEvents(dom.root, transport);

  el.dispatchEvent(new dom.window.MouseEvent("pointerdown", { bubbles: true, clientX: 10, clientY: 10 }));
  el.dispatchEvent(new dom.window.MouseEvent("pointerup", { bubbles: true, clientX: 12, clientY: 11 }));

  assert.equal(transport.events.length, 1);
  assert.equal(transport.events[0].type, "tap");
  assert.equal(transport.events[0].key, "g");
});

test("a horizontal drag over a GestureDetector emits a directional swipe", () => {
  const { dom, el } = mountGesture();
  const transport = mockTransport();
  bindEvents(dom.root, transport);

  el.dispatchEvent(new dom.window.MouseEvent("pointerdown", { bubbles: true, clientX: 10, clientY: 10 }));
  el.dispatchEvent(new dom.window.MouseEvent("pointerup", { bubbles: true, clientX: 90, clientY: 14 }));

  assert.equal(transport.events.length, 1);
  assert.deepEqual(transport.events[0], {
    type: "swipe",
    key: "g",
    payload: { direction: "right", dx: 80, dy: 4 },
  });
});

test("pointer gestures on a non-GestureDetector element are ignored", () => {
  const { dom, tree } = mountCounter();
  const transport = mockTransport();
  bindEvents(dom.root, transport);

  const incButton = tree.querySelector("[data-tw-key=\"inc\"]");
  incButton.dispatchEvent(new dom.window.MouseEvent("pointerdown", { bubbles: true, clientX: 0, clientY: 0 }));
  incButton.dispatchEvent(new dom.window.MouseEvent("pointerup", { bubbles: true, clientX: 0, clientY: 0 }));
  assert.equal(transport.events.length, 0);
});

test("typing in a MaskedInput formats as you go, and reports the masked value", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const field = buildElement({
    type: "MaskedInput",
    key: "cpf",
    props: { value: "", mask: "999.999.999-99", keyboard: "number" },
    children: [],
  });
  dom.root.appendChild(field);
  const transport = mockTransport();
  bindEvents(dom.root, transport);

  // The reader types four digits; the mask has to have put the dot in before the
  // app is told what the field holds, or state and screen disagree.
  field.value = "1234";
  field.dispatchEvent(new dom.window.Event("input", { bubbles: true }));

  assert.equal(field.value, "123.4");
  assert.deepEqual(transport.events.at(-1), {
    type: "input",
    key: "cpf",
    payload: { value: "123.4" },
  });
});

test("a masked value the app writes back is left alone", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const field = buildElement({
    type: "MaskedInput",
    key: "cpf",
    props: { value: "529.982.247-25", mask: "999.999.999-99" },
    children: [],
  });
  dom.root.appendChild(field);
  bindEvents(dom.root, mockTransport());

  // Re-masking an already-masked value must be a no-op, or every round trip
  // through the app's state would chew the literals.
  field.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
  assert.equal(field.value, "529.982.247-25");
});

test("an unmasked field is untouched by the masking pass", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const field = buildElement({
    type: "Input",
    key: "free",
    props: { value: "" },
    children: [],
  });
  dom.root.appendChild(field);
  const transport = mockTransport();
  bindEvents(dom.root, transport);

  field.value = "1234";
  field.dispatchEvent(new dom.window.Event("input", { bubbles: true }));

  assert.equal(field.value, "1234");
  assert.deepEqual(transport.events.at(-1).payload, { value: "1234" });
});

test("typing in a TextArea reports its value like any other field", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const area = buildElement({
    type: "TextArea",
    key: "body",
    props: { value: "", rows: 4 },
    children: [],
  });
  dom.root.appendChild(area);
  const transport = mockTransport();
  bindEvents(dom.root, transport);

  area.value = "a note";
  area.dispatchEvent(new dom.window.Event("input", { bubbles: true }));

  assert.deepEqual(transport.events.at(-1), {
    type: "input",
    key: "body",
    payload: { value: "a note" },
  });
});
