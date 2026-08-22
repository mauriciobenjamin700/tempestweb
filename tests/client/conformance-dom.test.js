// Round-trip the conformance scenarios through the real DOM renderer.
//
// tests/conformance/ derives its goldens from the real core and checks them
// against a reference applicator written in Python — which means client/dom.js,
// the renderer that actually paints Modes A/B/C, was never confronted with the
// core's own output. That is the gap a cleared prop slipped through: the core
// emitted `set_props: {"semantics": null}` and the patcher left the old
// aria-label on the element.
//
// The property here is the one the whole patch stream rests on: rendering the
// initial tree and applying every tick must produce exactly what rendering the
// final tree produces.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fixture, freshDom } from "./setup.js";
import { applyPatches, buildElement } from "../../client/dom.js";

/** Install jsdom's `document` globally so dom.js's `document.createElement` works. */
function withDocument() {
  const dom = freshDom();
  globalThis.document = dom.document;
  return dom;
}

/**
 * Apply one batch, following a root Replace so the tracked root stays live.
 * @param {HTMLElement} tree   The current root element.
 * @param {Object[]} batch     One tick's patch batch.
 * @returns {HTMLElement}      The root element after the batch.
 */
function applyBatch(tree, batch) {
  let current = tree;
  for (const patch of batch) {
    const isRootReplace =
      Array.isArray(patch.path) &&
      patch.path.length === 0 &&
      "node" in patch &&
      !("index" in patch) &&
      !("order" in patch) &&
      !("set_props" in patch) &&
      !("unset_props" in patch);
    if (isRootReplace) {
      current = buildElement(patch.node);
    } else {
      applyPatches(current, [patch]);
    }
  }
  return current;
}

const scenarios = fixture("conformance_scenarios.json");

for (const [name, scenario] of Object.entries(scenarios)) {
  test(`conformance: patching "${name}" matches building its final tree`, () => {
    withDocument();
    let tree = buildElement(scenario.initial);
    for (const batch of scenario.ticks) {
      tree = applyBatch(tree, batch);
    }
    const expected = buildElement(scenario.final);
    assert.equal(tree.outerHTML, expected.outerHTML);
  });
}
