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
