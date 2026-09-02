// contrast-gate.test.js — the contrast gate, and proof that it bites.
//
// The gate (scripts/contrast-gate.mjs) runs axe's `color-contrast` over the DOM
// the real renderer paints, in a real Chromium, for the same generated scenes the
// structural gate audits — in light and in dark. Running it here means a local
// `node --test` catches an illegible palette, not only CI.
//
// The second test is the one that matters, and it is the reason this file exists:
// a gate nobody has seen fail is a gate nobody knows works. That is not a
// hypothetical here — the rule this gate runs was switched off in the structural
// gate and delegated to a Lighthouse layer that audited nothing, so "contrast is
// covered" was true on paper for a long time.
//
// Playwright is installed with `--no-save` by the CI job that needs it, so these
// skip rather than fail where it is absent.
import { test } from "node:test";
import assert from "node:assert/strict";
import { auditScenes, runGate } from "../../scripts/contrast-gate.mjs";

/**
 * Whether Playwright can be loaded here.
 *
 * @returns {Promise<boolean>}  True when the browser driver is installed.
 */
async function hasPlaywright() {
  try {
    await import("playwright");
    return true;
  } catch {
    return false;
  }
}

const available = await hasPlaywright();
const options = {
  skip: available ? false : "playwright is not installed (npm install --no-save playwright)",
};

test("every generated scene passes color-contrast in light and dark", options, async () => {
  assert.equal(await runGate(), 0);
});

test("the gate fails text that cannot be read on its own background", options, async () => {
  const probe = {
    type: "Container",
    key: "probe-root",
    props: { style: { background: { r: 252, g: 252, b: 252, a: 1 } } },
    children: [
      {
        type: "Text",
        key: "invisible",
        props: {
          content: "you cannot read this",
          style: { color: { r: 249, g: 250, b: 251, a: 1 }, font_size: 14.0 },
        },
        children: [],
      },
    ],
  };

  const violations = await auditScenes({ light: { probe } }, true);

  assert.equal(violations.length, 1);
  assert.equal(violations[0].scene, "probe");
  assert.equal(violations[0].pair, "#f9fafb on #fcfcfc");
  assert.ok(
    violations[0].contrastRatio < 4.5,
    `expected a failing ratio, got ${violations[0].contrastRatio}`,
  );
});
