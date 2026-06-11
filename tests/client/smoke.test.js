// Proves the JS test harness runs. Real W1/W2/W3 tests replace/extend this.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fixture, freshDom } from "./setup.js";

test("fixtures load and jsdom works", () => {
  const node = fixture("node_initial.json");
  assert.equal(node.type, "Column");
  const { root } = freshDom();
  assert.ok(root);
});
