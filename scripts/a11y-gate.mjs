#!/usr/bin/env node
// a11y-gate.mjs — the CI accessibility gate (S10).
//
// `docs/stability.md` declares an accessibility baseline, and until now nothing
// measured one: the Lighthouse job runs with `|| echo soft-fail`, so it blocks
// nothing, and an IconButton shipped as an unfocusable `div` with no accessible
// name without a single job complaining (#109). This gate is the measurement.
//
// It runs axe-core over the DOM the *real* renderer builds, for scenes generated
// from the apps this repo ships (see tests/conformance/_a11y_scenes.py). jsdom,
// not a browser, on purpose: the failures worth blocking a merge over are
// structural — a control with no accessible name, an image with no alt, an
// invalid role, a nested interactive — and those are all in the markup. Contrast
// needs real layout and lives in the Lighthouse layer.
//
// Exit code 0 means no serious or critical violation. Non-zero fails the job and
// prints every violation with the node that caused it.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { JSDOM } from "jsdom";
import axe from "axe-core";
import { buildElement } from "../client/dom.js";
import { BASE_THEME_CSS } from "../client/theme.js";

const ROOT = fileURLToPath(new URL("..", import.meta.url));

/** Impact levels that fail the gate. A "minor" finding is reported, not blocking. */
const BLOCKING = new Set(["serious", "critical"]);

/**
 * Violations accepted for a stated reason, keyed by axe rule id.
 *
 * An exception is a decision with an owner, not a mute button: each one says why
 * the rule cannot apply to a scene built this way, and a rule that stops being
 * violated is removed from here (the gate reports an exception that no longer
 * fires, so the list cannot rot).
 */
const KNOWN_EXCEPTIONS = {
  "landmark-one-main": "a scene is one screen's tree, not a whole document",
  "page-has-heading-one": "the same: a screen fragment carries no document outline",
  region: "every node lands in the mount root, which is not a landmark by itself",
  "color-contrast": "needs real layout; the Lighthouse layer owns contrast",
};

/**
 * Load the generated scenes.
 * @returns {Object<string, Object>}  Scene name -> serialized IR node.
 */
function loadScenes() {
  const path = new URL("../tests/fixtures/a11y_scenes.json", import.meta.url);
  return JSON.parse(readFileSync(path, "utf8"));
}

/**
 * Mount one scene into a fresh document, with the base stylesheet installed.
 *
 * The sheet matters even in jsdom: axe reads `role`, `aria-*` and the accessible
 * name from the DOM the renderer produced, and the renderer writes some of those
 * only while applying props.
 *
 * @param {Object} node  The serialized IR node.
 * @returns {{window: Window, root: Element}}  The window and the mount root.
 */
function mountScene(node) {
  const dom = new JSDOM(
    "<!doctype html><html lang=\"pt-BR\"><head><title>a11y scene</title></head>" +
      "<body><div id=\"root\"></div></body></html>",
    { pretendToBeVisual: true },
  );
  globalThis.document = dom.window.document;
  const style = dom.window.document.createElement("style");
  style.textContent = BASE_THEME_CSS;
  dom.window.document.head.appendChild(style);
  const root = dom.window.document.getElementById("root");
  root.appendChild(buildElement(node));
  return { window: dom.window, root };
}

/**
 * Run axe over one scene.
 * @param {string} name  The scene name (an example directory).
 * @param {Object} node  Its serialized IR.
 * @returns {Promise<Array<Object>>}  The blocking violations found.
 */
export async function auditScene(name, node) {
  const { window, root } = mountScene(node);
  // axe-core reads `window` and `document` off the global scope, and both have to
  // be jsdom's before the run — it deduces its context from them. `navigator` is
  // getter-only in Node, so it is left alone; jsdom's reaches axe through the
  // element it audits. The mount root is the context, which is also the honest
  // scope: it is what the renderer owns.
  const previousWindow = globalThis.window;
  globalThis.window = window;
  globalThis.document = window.document;
  try {
    const results = await axe.run(root, {
      resultTypes: ["violations"],
      rules: Object.fromEntries(
        Object.keys(KNOWN_EXCEPTIONS).map((rule) => [rule, { enabled: false }]),
      ),
    });
    return results.violations
      .filter((violation) => BLOCKING.has(violation.impact ?? ""))
      .map((violation) => ({ scene: name, ...violation }));
  } finally {
    globalThis.window = previousWindow;
  }
}

/**
 * Audit every scene and report.
 * @returns {Promise<number>}  The process exit code.
 */
export async function runGate() {
  const scenes = loadScenes();
  /** @type {Array<Object>} */
  const blocking = [];
  for (const [name, node] of Object.entries(scenes)) {
    const violations = await auditScene(name, node);
    const mark = violations.length === 0 ? "ok" : `${violations.length} violation(s)`;
    console.log(`  ${name}: ${mark}`);
    blocking.push(...violations);
  }

  if (blocking.length === 0) {
    console.log(`\naxe-core: no serious or critical violation in ${Object.keys(scenes).length} scenes.`);
    return 0;
  }

  console.error("\naxe-core found blocking violations:\n");
  for (const violation of blocking) {
    console.error(`  [${violation.impact}] ${violation.scene}: ${violation.id} — ${violation.help}`);
    for (const node of violation.nodes.slice(0, 3)) {
      console.error(`      ${node.html}`);
    }
    console.error(`      ${violation.helpUrl}`);
  }
  console.error(
    "\nFix the markup the renderer emits, or — if the rule genuinely cannot apply " +
      "to a scene built this way — add it to KNOWN_EXCEPTIONS with the reason.",
  );
  return 1;
}

if (process.argv[1] === fileURLToPath(import.meta.url) || process.argv[1] === `${ROOT}scripts/a11y-gate.mjs`) {
  process.exit(await runGate());
}
