// field-name.test.js — a caption-less field names the control, not its wrapper.
//
// The Python side of the rule is pinned in tests/unit/test_component_semantics.py:
// with no visible caption a field puts the app's `semantics` on its `Input`. This
// is the half that only the DOM can answer — that the attribute lands on the
// element a screen reader stops at, and that axe agrees.
//
// The IR audited here is not written by hand. It comes from
// tests/fixtures/transpile_component_samples.json, built from the real core by
// `python -m tests.conformance._transpile_components`, so a component that stops
// forwarding the name fails here too. Hand-written markup would only prove the
// snippet is accessible.
import { test } from "node:test";
import assert from "node:assert/strict";
import { auditScene } from "../../scripts/a11y-gate.mjs";
import { buildElement } from "../../client/dom.js";
import { fixture, freshDom } from "./setup.js";

const SAMPLES = fixture("transpile_component_samples.json");

/**
 * Wrap one fixture case as the root of an auditable scene.
 *
 * A case is serialized with `key: null` at the root (the fixture compares trees
 * key-agnostically), and axe needs a mounted element, so the case is hung under a
 * root column with a key of its own.
 *
 * @param {string} name  The fixture case name.
 * @returns {Object}     A wire node ready for `auditScene`.
 */
function scene(name) {
  const node = structuredClone(SAMPLES[name]);
  node.key = name;
  return { type: "Column", key: `${name}-root`, props: {}, children: [node] };
}

/**
 * Render one fixture case through the real DOM renderer.
 *
 * `client/dom.js` reaches for a global `document`, so jsdom's is installed first —
 * the same shape `conformance-dom.test.js` uses.
 *
 * @param {string} name  The fixture case name.
 * @returns {HTMLElement}  The rendered scene root.
 */
function rendered(name) {
  globalThis.document = freshDom().document;
  return buildElement(scene(name));
}

test("a caption-less named field puts the name on the input", () => {
  const input = rendered("text_field_named_no_caption").querySelector("input");

  assert.equal(input.getAttribute("aria-label"), "Quantidade");
});

test("a captioned field names its input from the caption", () => {
  const host = rendered("text_field_named_by_caption");
  const input = host.querySelector("input");
  const wrapper = host.querySelector('[data-tw-key="text_field_named_by_caption"]');

  assert.equal(input.getAttribute("aria-label"), "Qtd.");
  assert.equal(wrapper.getAttribute("aria-label"), null);
});

test("the app's name wins over the caption, and stays on the input", () => {
  const host = rendered("text_field_named_over_caption");
  const input = host.querySelector("input");
  const wrapper = host.querySelector('[data-tw-key="text_field_named_over_caption"]');

  assert.equal(input.getAttribute("aria-label"), "Quantidade");
  assert.equal(input.getAttribute("aria-description"), "unidades contratadas");
  assert.equal(wrapper.getAttribute("aria-label"), null);
});

// The whole reason the rule is "always name the control": a password field has no
// default placeholder, so before 0.113.0 its control had no name at all — and a
// LoginForm shipped that violation to every app that used it.
test("axe accepts the password field, which was critical before", async () => {
  const violations = await auditScene(
    "password_field_default",
    scene("password_field_default"),
  );

  assert.deepEqual(violations, []);
});

test("axe accepts LoginForm and SignupForm, which were critical through it", async () => {
  for (const name of ["login_form_default", "signup_form_default"]) {
    assert.deepEqual(await auditScene(name, scene(name)), [], name);
  }
});

test("axe accepts the caption-less field the fields now build", async () => {
  const violations = await auditScene(
    "text_field_named_no_caption",
    scene("text_field_named_no_caption"),
  );

  assert.deepEqual(violations, []);
});

// What forwarding `semantics` straight through would have produced: the name on
// the role-less wrapper. axe reports it twice, and the second finding is the
// sharper one — `aria-label` on a `<div>` with no role is not merely useless, it is
// prohibited.
test("axe fails a name that stops at the wrapper", async () => {
  const violations = await auditScene("probe", {
    type: "Column",
    key: "probe-root",
    props: {},
    children: [
      {
        type: "Column",
        key: "wrapper",
        props: { semantics: { label: "Quantidade", role: null, hint: null } },
        children: [{ type: "Input", key: "control", props: { value: "" }, children: [] }],
      },
    ],
  });

  assert.deepEqual(
    violations.map((violation) => violation.id),
    ["aria-prohibited-attr", "label"],
  );
  assert.deepEqual(
    violations.map((violation) => violation.impact),
    ["serious", "critical"],
  );
});
