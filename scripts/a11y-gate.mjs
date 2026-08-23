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
 * the rule cannot apply to a scene built this way. The blocking pass disables
 * them — a disabled rule produces no result at all — so `staleExceptions` runs a
 * second pass with only these enabled and reports the ones that no longer fire
 * anywhere. Without that pass the list could not rot loudly, only silently.
 */
const KNOWN_EXCEPTIONS = {
  "color-contrast": "needs real layout; the Lighthouse layer owns contrast",
};

/**
 * Exceptions the staleness pass cannot judge, and why.
 *
 * `color-contrast` needs a laid-out box to sample colours from, which jsdom does
 * not produce: axe returns it as incomplete rather than as a violation, so its
 * silence here says nothing about whether the rule still applies. Reporting it as
 * stale would teach the reader to ignore the report.
 */
const NOT_EVALUABLE = new Set(["color-contrast"]);

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
 * The excepted rules the staleness pass can actually judge.
 *
 * @returns {Array<string>}  The rule ids to re-enable in the second pass.
 */
function evaluableExceptions() {
  return Object.keys(KNOWN_EXCEPTIONS).filter((rule) => !NOT_EVALUABLE.has(rule));
}

/**
 * Run one scene with only the excepted rules enabled.
 *
 * @param {Object} node  The serialized IR node.
 * @returns {Promise<Set<string>>}  The excepted rule ids that fired on it.
 */
async function firedExceptions(node) {
  const { window, root } = mountScene(node);
  const previousWindow = globalThis.window;
  globalThis.window = window;
  globalThis.document = window.document;
  try {
    const results = await axe.run(root, {
      resultTypes: ["violations"],
      runOnly: { type: "rule", values: evaluableExceptions() },
    });
    return new Set(results.violations.map((violation) => violation.id));
  } finally {
    globalThis.window = previousWindow;
  }
}

/**
 * Report every exception that no longer fires on any scene.
 *
 * This is what keeps `KNOWN_EXCEPTIONS` from rotting: an entry that stopped being
 * violated is a decision nobody needs any more, and a mute button nobody notices.
 * It reports rather than fails — a stale exception is untidy, not broken.
 *
 * @param {Object<string, Object>} scenes  Scene name -> serialized IR.
 * @returns {Promise<Array<string>>}  The stale rule ids, in listed order.
 */
export async function staleExceptions(scenes) {
  const candidates = evaluableExceptions();
  if (candidates.length === 0) {
    return [];
  }
  const fired = new Set();
  for (const node of Object.values(scenes)) {
    for (const rule of await firedExceptions(node)) {
      fired.add(rule);
    }
  }
  return candidates.filter((rule) => !fired.has(rule));
}

/**
 * Print the staleness report, when there is one.
 *
 * @param {Object<string, Object>} scenes  Scene name -> serialized IR.
 * @returns {Promise<void>}
 */
async function reportStaleExceptions(scenes) {
  const stale = await staleExceptions(scenes);
  if (stale.length === 0) {
    return;
  }
  console.log(
    `\nKNOWN_EXCEPTIONS no longer violated by any scene — drop them: ${stale.join(", ")}`,
  );
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

  await reportStaleExceptions(scenes);

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
