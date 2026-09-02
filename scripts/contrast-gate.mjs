#!/usr/bin/env node
// contrast-gate.mjs — the colour-contrast half of the accessibility gate (#202).
//
// `scripts/a11y-gate.mjs` runs axe over the DOM the real renderer builds, in
// jsdom, and disables one rule for a stated reason: `color-contrast` needs a
// laid-out box to sample colours from, which jsdom does not produce. It delegated
// that rule to "the Lighthouse layer" — a layer that audited nothing for its
// whole life, and whose PWA category Lighthouse has since removed (#201).
//
// So contrast had two halves and one measurer. `tests/client/theme-contrast.test.js`
// covers the half that needs no layout: every foreground/background *pair the
// palette promises* meets WCAG AA, computed from the tokens. What nothing
// measured is the other half, named in that file's own header — whether a widget
// actually used the pair it was supposed to. A widget painting `--tw-on-surface`
// over `--tw-primary` is a pair the palette never promised, so the token test
// cannot see it, and the a11y gate had the rule switched off.
//
// This gate closes that. Same scenes as `a11y-gate.mjs` — generated from the apps
// this repo ships, so the two cannot drift — mounted by the same renderer, but in
// a real Chromium where axe can read computed colours off laid-out boxes. Each
// scene runs twice, in light and in dark: dark is a whole second palette
// (`data-tw-theme="dark"`), and it shipped with nothing in CI able to tell a
// legible one from an illegible one (#148).
//
// Exit code 0 means no contrast violation in either theme.

import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize, resolve as resolvePath, sep } from "node:path";
import { fileURLToPath } from "node:url";
import axe from "axe-core";

/** The repo root, without a trailing separator, so path containment can be tested. */
const ROOT = resolvePath(fileURLToPath(new URL("..", import.meta.url)));

/**
 * The themes every scene is audited in, and the fixture each one reads.
 *
 * A theme is not a switch flipped on a rendered tree: what the core resolves —
 * a Text's colour, a Card's surface — travels as inline style on the IR, so a
 * tree built in light under a dark sheet is a mixture that exists in no app.
 * Each theme therefore has scenes generated under it
 * (`python -m tests.conformance._a11y_scenes`).
 */
const THEMES = {
  light: "a11y_scenes.json",
  dark: "a11y_scenes_dark.json",
};

/**
 * Failing colour pairs accepted for a stated reason, keyed by `<fg> on <bg>`.
 *
 * An exception is a decision with an owner, not a mute button — the same rule
 * `scripts/a11y-gate.mjs` set for its own list. Both entries here are owned by
 * `tempest-core`, whose palette this repo pins and does not edit: the fix has to
 * land there, and until it does the gate would fail on every PR for a defect no
 * change here can reach.
 *
 * They are keyed by the colour pair rather than by scene or element, because the
 * pair is what has to change. Any scene painting the same pair is covered, and a
 * scene that stops painting it stops holding the exception open.
 */
const KNOWN_EXCEPTIONS = {
  "#9ca3af on #374151":
    "tempest-core: ON_MUTED on MUTED is 4.06:1, just under AA for text. The " +
    "palette promises this pair by naming — `on-<x>` is drawn on `<x>` — so the " +
    "fix is the token, not the caller.",
  "#22aa54 on #e5e5e6":
    "tempest-core: the `success` role tinting a Metric's delta. 2.40:1 at 13px.",
  "#22aa54 on #fcfcfc":
    "tempest-core: the same `success` role on the lighter surface. 2.94:1 at 13px.",
};

/** Content types for the handful of files the harness fetches. */
const CONTENT_TYPES = {
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".css": "text/css; charset=utf-8",
};

/**
 * The harness page: the real renderer and the real stylesheet, nothing else.
 *
 * Served rather than injected with `setContent` so that the client's ES modules
 * resolve over http — a `file://` document cannot import them, and rewriting the
 * imports would mean auditing something other than what ships.
 */
const HARNESS = `<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="utf-8" />
    <title>contrast scene</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module">
      import { buildElement } from "/client/dom.js";
      import { BASE_THEME_CSS, THEME_MODE_ATTR } from "/client/theme.js";

      const sheet = document.createElement("style");
      sheet.textContent = BASE_THEME_CSS;
      document.head.appendChild(sheet);

      window.__mount = (node, theme) => {
        document.documentElement.setAttribute(THEME_MODE_ATTR, theme);
        const root = document.getElementById("root");
        root.replaceChildren(buildElement(node));
      };
      window.__ready = true;
    </script>
  </body>
</html>
`;

/**
 * Serve the repo's client modules and the harness page.
 *
 * @returns {Promise<{origin: string, close: () => Promise<void>}>}  The server.
 */
async function serveRepo() {
  const server = createServer((request, response) => {
    const path = new URL(request.url ?? "/", "http://localhost").pathname;
    if (path === "/" || path === "/index.html") {
      response.writeHead(200, { "content-type": "text/html; charset=utf-8" });
      response.end(HARNESS);
      return;
    }
    const resolved = normalize(join(ROOT, path));
    if (!resolved.startsWith(ROOT + sep)) {
      response.writeHead(403).end();
      return;
    }
    readFile(resolved).then(
      (bytes) => {
        const type = CONTENT_TYPES[extname(resolved)] ?? "application/octet-stream";
        response.writeHead(200, { "content-type": type });
        response.end(bytes);
      },
      () => response.writeHead(404).end(),
    );
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = /** @type {{port: number}} */ (server.address());
  return {
    origin: `http://127.0.0.1:${port}/`,
    close: () => new Promise((resolve) => server.close(() => resolve())),
  };
}

/**
 * Load the generated scenes for one theme.
 *
 * @param {string} fixture  The fixture file name under ``tests/fixtures/``.
 * @returns {Promise<Object<string, Object>>}  Scene name -> serialized IR node.
 */
async function loadScenes(fixture) {
  const path = new URL(`../tests/fixtures/${fixture}`, import.meta.url);
  return JSON.parse(await readFile(path, "utf8"));
}

/** The excepted pairs actually seen in this run, for the staleness report. */
const excepted = new Set();

/**
 * Name a failing colour pair the way ``KNOWN_EXCEPTIONS`` keys it.
 *
 * @param {{fgColor: string, bgColor: string}} data  One axe check's data.
 * @returns {string}  The `<fg> on <bg>` key.
 */
function pairKey(data) {
  return `${data.fgColor} on ${data.bgColor}`;
}

/**
 * Audit one scene in one theme.
 *
 * The context is the mount root, which is the honest scope: it is what the
 * renderer owns. Only `color-contrast` runs — every structural rule is already
 * measured, faster, by `a11y-gate.mjs`.
 *
 * @param {import("playwright").Page} page  The harness page.
 * @param {string} name  The scene name.
 * @param {Object} node  The serialized IR node.
 * @param {string} theme  `"light"` or `"dark"`.
 * @returns {Promise<Array<Object>>}  The violations found.
 */
async function auditScene(page, name, node, theme) {
  await page.evaluate(
    ([sceneNode, sceneTheme]) => window.__mount(sceneNode, sceneTheme),
    [node, theme],
  );
  const results = await page.evaluate(async () => {
    return await window.axe.run(document.getElementById("root"), {
      resultTypes: ["violations"],
      runOnly: { type: "rule", values: ["color-contrast"] },
    });
  });
  /** @type {Array<Object>} */
  const found = [];
  for (const violation of results.violations) {
    for (const node of violation.nodes) {
      for (const check of node.any ?? []) {
        const pair = pairKey(check.data);
        if (pair in KNOWN_EXCEPTIONS) {
          excepted.add(pair);
          continue;
        }
        found.push({ scene: name, theme, html: node.html, pair, ...check.data });
      }
    }
  }
  return found;
}

/**
 * Report every exception that no longer fires on any scene.
 *
 * This is what keeps ``KNOWN_EXCEPTIONS`` from rotting: an entry nothing violates
 * any more is a decision nobody needs, and a mute button nobody notices. It
 * reports rather than fails — a stale exception is untidy, not broken — and it is
 * how the day `tempest-core` fixes its palette becomes visible here.
 *
 * @returns {void}
 */
function reportStaleExceptions() {
  const stale = Object.keys(KNOWN_EXCEPTIONS).filter((pair) => !excepted.has(pair));
  if (stale.length === 0) {
    return;
  }
  console.log(
    `\nKNOWN_EXCEPTIONS no longer violated by any scene — drop them:\n  ${stale.join("\n  ")}`,
  );
}

/**
 * Audit an explicit set of scenes, keyed by theme.
 *
 * Exported so a test can drive the gate with a probe scene and watch it fail: a
 * gate nobody has seen fail is a gate nobody knows works.
 *
 * @param {Object<string, Object<string, Object>>} byTheme  theme -> {name: node}.
 * @param {boolean} [quiet]  Suppress the per-scene log.
 * @returns {Promise<Array<Object>>}  Every non-excepted violation found.
 */
export async function auditScenes(byTheme, quiet = false) {
  const server = await serveRepo();
  const { chromium } = await import("playwright");
  const browser = await chromium.launch();
  /** @type {Array<Object>} */
  const violations = [];
  try {
    const page = await browser.newPage();
    await page.goto(server.origin, { waitUntil: "load" });
    await page.waitForFunction(() => window.__ready === true);
    await page.addScriptTag({ content: axe.source });
    for (const [theme, scenes] of Object.entries(byTheme)) {
      for (const [name, node] of Object.entries(scenes)) {
        const found = await auditScene(page, name, node, theme);
        if (!quiet) {
          const mark = found.length === 0 ? "ok" : `${found.length} violation(s)`;
          console.log(`  ${name} [${theme}]: ${mark}`);
        }
        violations.push(...found);
      }
    }
  } finally {
    await browser.close();
    await server.close();
  }
  return violations;
}

/**
 * Audit every generated scene in every theme.
 *
 * @returns {Promise<number>}  The process exit code.
 */
export async function runGate() {
  /** @type {Object<string, Object<string, Object>>} */
  const byTheme = {};
  for (const [theme, fixture] of Object.entries(THEMES)) {
    byTheme[theme] = await loadScenes(fixture);
  }
  const audited = Object.values(byTheme).reduce(
    (total, scenes) => total + Object.keys(scenes).length,
    0,
  );
  const violations = await auditScenes(byTheme);

  reportStaleExceptions();

  if (violations.length === 0) {
    console.log(`\naxe color-contrast: no violation in ${audited} scene/theme pairs.`);
    return 0;
  }

  console.error(`\naxe found ${violations.length} contrast violation(s):\n`);
  for (const violation of violations) {
    console.error(
      `  [${violation.scene} / ${violation.theme}] ${violation.pair} is ` +
        `${violation.contrastRatio}:1, needs ${violation.expectedContrastRatio} ` +
        `(${violation.fontSize}, ${violation.fontWeight})`,
    );
    console.error(`      ${violation.html}`);
  }
  console.error(
    "\nFix the pair the widget paints, or the token it reads — a role named " +
      "`on-<x>` is drawn on `<x>`, and drawing it on anything else is what this " +
      "gate is for. If the pair belongs to tempest-core, it goes in " +
      "KNOWN_EXCEPTIONS with the reason, and the fix lands in that repo.",
  );
  return 1;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  try {
    process.exit(await runGate());
  } catch (error) {
    console.error(`contrast gate could not run: ${error.message}`);
    process.exit(2);
  }
}
