// Tests for client/tempestweb.js — mount() wiring against a mock transport.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fixture, freshDom } from "./setup.js";
import { mount } from "../../client/tempestweb.js";

/**
 * A mock Transport capturing the patch handler and events, so the test can push
 * a patch batch ("from Python") and read events sent back.
 */
function mockTransport() {
  /** @type {import("../../client/transport.js").TWEvent[]} */
  const events = [];
  /** @type {?(patches: import("../../client/transport.js").Patch[]) => void} */
  let handler = null;
  return {
    events,
    push(patches) {
      if (handler) handler(patches);
    },
    onPatches(fn) {
      handler = fn;
    },
    sendEvent(event) {
      events.push(event);
    },
    async close() {},
  };
}

test("mount builds the initial tree under root", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const transport = mockTransport();
  mount(dom.root, transport, fixture("node_initial.json"));

  assert.equal(dom.root.children.length, 1);
  const tree = dom.root.children[0];
  assert.equal(tree.tagName, "DIV");
  assert.equal(tree.children[0].textContent, "Count: 0");
});

test("mount applies pushed patches to the mounted tree", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const transport = mockTransport();
  mount(dom.root, transport, fixture("node_initial.json"));

  transport.push(fixture("patches_count_0_to_1.json"));
  assert.equal(dom.root.children[0].children[0].textContent, "Count: 1");
});

test("mount wires events so a button click reaches sendEvent with its key", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const transport = mockTransport();
  mount(dom.root, transport, fixture("node_initial.json"));

  dom.root
    .querySelector("[data-tw-key=\"inc\"]")
    .dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));

  assert.equal(transport.events.length, 1);
  assert.equal(transport.events[0].key, "inc");
  assert.equal(transport.events[0].type, "click");
});

test("overlay-path patches render into a lazy overlay layer, not the tree", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const transport = mockTransport();
  mount(dom.root, transport, fixture("node_initial.json"));

  // No overlay host until an overlay patch arrives (apps without overlays add
  // no extra DOM): the tree is the only child.
  assert.equal(dom.root.children.length, 1);
  assert.equal(dom.root.querySelector("[data-tw-overlays]"), null);

  // An insert at the reserved ["overlay"] path mounts an overlay (e.g. a dialog).
  transport.push([
    { path: ["overlay"], index: 0, node: fixture("node_initial.json") },
  ]);
  const overlayHost = dom.root.querySelector("[data-tw-overlays]");
  assert.ok(overlayHost, "overlay host created on first overlay patch");
  assert.equal(overlayHost.children.length, 1);
  // The screen tree is untouched by overlay patches.
  assert.equal(dom.root.children[0].children[0].textContent, "Count: 0");

  // Removing the overlay clears the layer, leaving the tree in place.
  transport.push([{ path: ["overlay"], index: 0 }]);
  assert.equal(overlayHost.children.length, 0);
});

test("unmount removes the tree and stops events", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const transport = mockTransport();
  const handle = mount(dom.root, transport, fixture("node_initial.json"));

  const inc = dom.root.querySelector("[data-tw-key=\"inc\"]");
  handle.unmount();
  assert.equal(dom.root.children.length, 0);

  inc.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
  assert.equal(transport.events.length, 0);
});
