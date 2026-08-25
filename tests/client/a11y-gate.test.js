// a11y-gate.test.js — the accessibility gate, and proof that it bites.
//
// The gate itself (scripts/a11y-gate.mjs) runs axe-core over the DOM the real
// renderer builds, for scenes generated from the apps this repo ships. Running it
// here means a local `node --test` fails on an accessibility regression, not only
// CI — and the second test is the part that matters: a gate nobody has seen fail
// is a gate nobody knows works.
import { test } from "node:test";
import assert from "node:assert/strict";
import { auditScene, runGate, staleExceptions } from "../../scripts/a11y-gate.mjs";

test("every generated scene passes axe-core with no serious or critical violation", async () => {
  assert.equal(await runGate(), 0);
});

test("the gate fails an image with no alt text", async () => {
  const violations = await auditScene("probe", {
    type: "Column",
    key: "probe-root",
    props: {},
    children: [
      { type: "Image", key: "photo", props: { src: "/cat.png" }, children: [] },
    ],
  });

  assert.deepEqual(
    violations.map((v) => v.id),
    ["image-alt"],
  );
  assert.equal(violations[0].impact, "critical");
});

// The #109 shape: a control that renders, takes a click, and tells a screen
// reader nothing.
test("the gate fails a button with no accessible name", async () => {
  const violations = await auditScene("probe", {
    type: "Column",
    key: "probe-root",
    props: {},
    children: [{ type: "Button", key: "nameless", props: {}, children: [] }],
  });

  assert.deepEqual(
    violations.map((v) => v.id),
    ["button-name"],
  );
});

test("the gate fails an invalid ARIA role the app set through semantics", async () => {
  const violations = await auditScene("probe", {
    type: "Column",
    key: "probe-root",
    props: {},
    children: [
      {
        type: "Container",
        key: "box",
        props: { semantics: { role: "buton", label: "typo" } },
        children: [],
      },
    ],
  });

  assert.ok(
    violations.some((v) => v.id === "aria-roles"),
    `expected aria-roles, got ${violations.map((v) => v.id).join(", ") || "none"}`,
  );
});

// The exception list is a mute button unless something notices when an entry
// stops being needed. The blocking pass disables those rules, so it structurally
// cannot notice; this is the second pass that can.
test("a nameless range slider fails the gate, which is how the thumbs got names", async () => {
  const violations = await auditScene("probe", {
    type: "Column",
    key: "probe-root",
    props: {},
    children: [
      {
        type: "RangeSlider",
        key: "fare",
        props: { low: 1, high: 9, min_value: 0, max_value: 10 },
        children: [],
      },
    ],
  });

  assert.deepEqual(violations, []);
});

test("no accepted exception has stopped being needed", async () => {
  const scenes = JSON.parse(
    await import("node:fs/promises").then((fs) =>
      fs.readFile(new URL("../fixtures/a11y_scenes.json", import.meta.url), "utf8"),
    ),
  );

  assert.deepEqual(await staleExceptions(scenes), []);
});
