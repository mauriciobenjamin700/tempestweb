// component-carry.test.js — a Mode C builder carries the caller's base props.
//
// A component in Modes A and B is a node the core expands, and `tempest-core`
// 0.17.0 made it carry `semantics`, `focusable`, `focus_order`, `tag` and `attrs`
// onto the root it rendered. In Mode C a component is a *function*: whatever the
// caller passes that the builder does not read reaches nothing at all. Same
// defect, one runtime over — and the one place a screen can be accessible in the
// browser and mute in the transpiled build of itself.
//
// The cross-language halves are pinned by the `__named` twins in
// tests/fixtures/transpile_component_samples.json (built from the real core).
// What this file adds is the sweep: *every* builder, not the six the fixture
// samples, plus the guard against the two prop lists drifting apart.
import { test } from "node:test";
import assert from "node:assert/strict";
import * as components from "../../client/transpile/components.js";
import { CARRIED_PROPS, Semantics } from "../../client/transpile/values.gen.js";

/** Builders whose return value is not a node, so nothing is carried. */
const NOT_BUILDERS = new Set(["confidence_scheme"]);

/** The caller-facing name of a wire prop (`focus_order` → `focusOrder`). */
const camel = (wire) => wire.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());

/** A distinctive value per carried prop, falsy ones included. */
const VALUES = {
  semantics: Semantics({ label: "Quantidade contratada" }),
  focusable: false,
  focus_order: 0,
  tag: "section",
  attrs: { "data-probe": "1" },
};

/**
 * Call every component builder with the base props a caller may set.
 * @returns {Array<[string, import("../../client/transport.js").Node]>}
 */
function builtWithBaseProps() {
  const args = Object.fromEntries(
    CARRIED_PROPS.map((wire) => [camel(wire), VALUES[wire]]),
  );
  return Object.entries(components)
    .filter(([name, value]) => typeof value === "function" && !NOT_BUILDERS.has(name))
    .map(([name, builder]) => [name, builder({ ...args })]);
}

/**
 * Whether a subtree carries one prop's value on any node.
 * @param {import("../../client/transport.js").Node} node  The subtree root.
 * @param {string} wire  The prop's wire name.
 * @param {*} value  The value the caller passed.
 * @returns {boolean}
 */
function carries(node, wire, value) {
  const found = node.props?.[wire];
  if (JSON.stringify(found) === JSON.stringify(value)) return true;
  return (node.children ?? []).some((child) => carries(child, wire, value));
}

test("every Mode C builder carries the base props the caller set", () => {
  for (const [name, node] of builtWithBaseProps()) {
    for (const wire of CARRIED_PROPS) {
      assert.ok(
        carries(node, wire, VALUES[wire]),
        `${name} dropped ${wire} — a builder is the component boundary here, so a prop it does not read reaches no node`,
      );
    }
  }
});

test("a builder that owns nothing puts all five on its own root", () => {
  const [, node] = builtWithBaseProps().find(([name]) => name === "Card");
  for (const wire of CARRIED_PROPS) {
    assert.deepEqual(node.props[wire], VALUES[wire], `Card kept ${wire} off its root`);
  }
});

test("the sweep covers every builder the module exports", () => {
  const swept = builtWithBaseProps().length;
  assert.ok(swept >= 45, `only ${swept} builders swept — the module lost exports`);
});

test("a builder that routes a prop keeps its own routing", () => {
  const field = components.TextField({
    onChange: () => {},
    key: "q",
    semantics: Semantics({ label: "Quantidade" }),
  });
  assert.equal(field.props.semantics, null, "the wrapper has no role, so a name there is a prohibited attribute — and the control would be announced twice");
  const control = field.children.find((child) => child.type === "Input");
  assert.equal(control.props.semantics.label, "Quantidade");
});

test("the carried list is the core's, not a copy that drifted", () => {
  const card = components.Card({
    children: [],
    ...Object.fromEntries(CARRIED_PROPS.map((wire) => [camel(wire), VALUES[wire]])),
  });
  for (const wire of CARRIED_PROPS) {
    assert.notEqual(
      card.props[wire],
      undefined,
      `${wire} is in the core's CARRIED_PROPS and this client never carries it`,
    );
  }
  assert.deepEqual([...CARRIED_PROPS].sort(), [...CARRIED_PROPS], "the generated list is sorted");
});
