// Regression: a root Replace (path []) must re-track the mounted tree so later
// patches resolve against the new tree, not the detached old one.
import { test } from "node:test";
import assert from "node:assert/strict";
import { freshDom } from "./setup.js";
import { mount } from "../../client/tempestweb.js";

/** Minimal mock transport exposing push(). */
function mockTransport() {
  let handler = null;
  return {
    push(patches) {
      if (handler) handler(patches);
    },
    onPatches(fn) {
      handler = fn;
    },
    sendEvent() {},
    async close() {},
  };
}

/** A small login-shaped IR tree (few children). */
const loginNode = {
  type: "Column",
  key: "login",
  props: {},
  children: [{ type: "Text", props: { content: "login" }, children: [] }],
};

/** A dashboard-shaped IR tree with a deeper second child. */
const dashNode = {
  type: "Column",
  key: "dash",
  props: {},
  children: [
    { type: "Text", props: { content: "appbar" }, children: [] },
    {
      type: "Column",
      props: {},
      children: [{ type: "Text", props: { content: "row0" }, children: [] }],
    },
  ],
};

test("root Replace re-tracks the tree so later patches hit the new tree", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const transport = mockTransport();
  mount(dom.root, transport, loginNode);

  // Swap the whole tree (login -> dashboard) via a root Replace at path [].
  transport.push([{ path: [], node: dashNode }]);
  const tree = dom.root.children[0];
  assert.equal(tree.getAttribute("data-tw-key"), "dash");
  assert.equal(tree.children.length, 2);

  // A deep patch into the NEW tree must apply (would throw "out of range" if the
  // mount still pointed at the detached 1-child login tree).
  assert.doesNotThrow(() => {
    transport.push([{ path: [1, 0], set_props: { content: "updated" } }]);
  });
  assert.equal(tree.children[1].children[0].textContent, "updated");
});

test("consecutive root Replaces keep tracking", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const transport = mockTransport();
  mount(dom.root, transport, loginNode);

  transport.push([{ path: [], node: dashNode }]);
  transport.push([{ path: [], node: loginNode }]);
  transport.push([{ path: [], node: dashNode }]);

  const tree = dom.root.children[0];
  assert.equal(tree.getAttribute("data-tw-key"), "dash");
  assert.doesNotThrow(() => {
    transport.push([{ path: [1, 0], set_props: { content: "ok" } }]);
  });
  assert.equal(tree.children[1].children[0].textContent, "ok");
});
