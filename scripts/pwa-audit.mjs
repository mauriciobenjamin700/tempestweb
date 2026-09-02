#!/usr/bin/env node
// pwa-audit.mjs — the CI PWA audit, against a built artifact in a real browser (P4).
//
// This replaces a Lighthouse job that could not have worked. `.lighthouserc.json`
// asserted `installable-manifest`, `service-worker`, `maskable-icon`,
// `apple-touch-icon`, `splash-screen` and `themed-omnibox` — and Lighthouse 12
// removed the PWA category outright, so six of those seven audits are simply
// absent from a modern report (measured on 12.1.0: `categories: []` under
// `onlyCategories: ["pwa"]`). The job stayed green because it was wrapped in
// `continue-on-error` and `|| echo soft-fail`, over a `staticDistDir` no step
// ever built. Three layers of silence over an audit that had stopped existing.
//
// What P4 actually wants is "installable + offline", so this measures that
// directly, in Chromium, over the artifact `tempestweb build` emits:
//
//   1. the viewport meta the installability heuristic requires;
//   2. the manifest the artifact *serves* — parsed from the page's own
//      `<link rel="manifest">`, not the one `buildManifest()` returns in-process;
//   3. every icon the manifest promises: it resolves, and its real pixel size is
//      the size the manifest declared;
//   4. the service worker registering *and controlling* the page;
//   5. offline: with the network cut, a reload still renders the app.
//
// (2) and (3) are the seam `scripts/pwa-gate.mjs` cannot reach. That script
// validates the manifest object the builder returns — a stand-in for the file.
// This one reads what the browser reads, which is where a manifest that promises
// a 512px icon over a 192px PNG becomes visible.
//
// Usage: node scripts/pwa-audit.mjs <base-url>
// Exit code 0 means the artifact is installable and works offline.

import { validateInstallable } from "../client/pwa/manifest.js";

/** How long to wait for the service worker to take control, in milliseconds. */
const CONTROL_TIMEOUT_MS = 15000;

/**
 * Read a PNG's pixel dimensions from its IHDR chunk.
 *
 * The header is fixed-layout — an 8-byte signature, then a chunk length and type,
 * then width and height as big-endian uint32 — so the size can be read without a
 * decoder. A file that is not a PNG returns null rather than a wrong number.
 *
 * @param {Buffer} bytes  The file's bytes.
 * @returns {{width: number, height: number} | null}  The dimensions, or null.
 */
function pngSize(bytes) {
  const signature = "89504e470d0a1a0a";
  if (bytes.length < 24 || bytes.subarray(0, 8).toString("hex") !== signature) {
    return null;
  }
  return { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) };
}

/**
 * Check the page declares a viewport the installability heuristic accepts.
 *
 * @param {import("playwright").Page} page  The loaded page.
 * @returns {Promise<Array<string>>}  The problems found.
 */
async function auditViewport(page) {
  const content = await page.getAttribute("meta[name=viewport]", "content");
  if (content === null) {
    return ["no <meta name=\"viewport\">"];
  }
  if (!/width=|initial-scale=/.test(content)) {
    return [`viewport lacks width/initial-scale: ${content}`];
  }
  return [];
}

/**
 * Fetch and validate the manifest the artifact serves.
 *
 * The href is read from the page so that a build which emits a manifest but
 * forgets to link it fails here, which is exactly how a browser would see it.
 *
 * @param {import("playwright").Page} page  The loaded page.
 * @param {import("playwright").APIRequestContext} request  The request context.
 * @returns {Promise<{problems: Array<string>, manifest: Object | null}>}
 */
async function auditManifest(page, request) {
  const href = await page.getAttribute("link[rel=manifest]", "href");
  if (href === null) {
    return { problems: ["no <link rel=\"manifest\">"], manifest: null };
  }
  const url = new URL(href, page.url()).toString();
  const response = await request.get(url);
  if (!response.ok()) {
    return { problems: [`manifest ${url} -> HTTP ${response.status()}`], manifest: null };
  }
  let manifest;
  try {
    manifest = JSON.parse(await response.text());
  } catch (error) {
    return { problems: [`manifest is not valid JSON: ${error.message}`], manifest: null };
  }
  return {
    problems: validateInstallable(manifest).map((problem) => `manifest: ${problem}`),
    manifest,
  };
}

/**
 * Check every icon the manifest promises resolves at the size it declares.
 *
 * A manifest listing a 512x512 icon over a 192px file is installable-shaped and
 * still wrong: the install prompt and the splash screen read the real file. The
 * shape check in `pwa-gate.mjs` cannot see this, because it never opens the PNG.
 *
 * @param {Object | null} manifest  The parsed manifest.
 * @param {string} baseUrl  The page URL the icon srcs resolve against.
 * @param {import("playwright").APIRequestContext} request  The request context.
 * @returns {Promise<Array<string>>}  The problems found.
 */
async function auditIcons(manifest, baseUrl, request) {
  if (manifest === null) {
    return [];
  }
  /** @type {Array<string>} */
  const problems = [];
  for (const icon of manifest.icons ?? []) {
    const url = new URL(icon.src, baseUrl).toString();
    const response = await request.get(url);
    if (!response.ok()) {
      problems.push(`icon ${icon.src} -> HTTP ${response.status()}`);
      continue;
    }
    const size = pngSize(await response.body());
    if (size === null) {
      problems.push(`icon ${icon.src} is not a PNG`);
      continue;
    }
    const declared = String(icon.sizes ?? "").split(" ")[0];
    const actual = `${size.width}x${size.height}`;
    if (declared !== actual) {
      problems.push(`icon ${icon.src} declares ${declared} but the file is ${actual}`);
    }
  }
  return problems;
}

/**
 * Check the service worker registers and takes control of the page.
 *
 * Controlling is the property that matters: a worker that registers but never
 * controls the page cannot serve a single navigation, so the app has no offline
 * story no matter what the registration says. The first load is usually
 * uncontrolled by design, so this reloads and waits for the controller.
 *
 * @param {import("playwright").Page} page  The loaded page.
 * @returns {Promise<Array<string>>}  The problems found.
 */
async function auditServiceWorker(page) {
  const registered = await page.evaluate(async (timeout) => {
    if (!("serviceWorker" in navigator)) {
      return "this browser has no serviceWorker";
    }
    const ready = navigator.serviceWorker.ready;
    const expired = new Promise((resolve) => setTimeout(() => resolve(null), timeout));
    return (await Promise.race([ready, expired])) === null ? "no worker became ready" : "";
  }, CONTROL_TIMEOUT_MS);
  if (registered !== "") {
    return [`service worker: ${registered}`];
  }
  await page.reload({ waitUntil: "load" });
  const controlled = await page.evaluate(() => navigator.serviceWorker.controller !== null);
  return controlled ? [] : ["service worker: registered but does not control the page"];
}

/**
 * Check the app still renders with the network cut.
 *
 * This is the half of "installable + offline" that no unit test reaches: it needs
 * a real worker, a real cache and a real navigation. The assertion is that the
 * mount root has children — the app painted — not merely that the document
 * loaded, since a precached shell that renders nothing is still a blank screen.
 *
 * @param {import("playwright").BrowserContext} context  The browser context.
 * @param {import("playwright").Page} page  The controlled page.
 * @returns {Promise<Array<string>>}  The problems found.
 */
async function auditOffline(context, page) {
  await context.setOffline(true);
  try {
    await page.reload({ waitUntil: "load" });
  } catch (error) {
    return [`offline reload failed: ${error.message}`];
  } finally {
    await context.setOffline(false);
  }
  const painted = await page.evaluate(() => {
    const root = document.getElementById("app") ?? document.body;
    return root.childElementCount > 0;
  });
  return painted ? [] : ["offline: the page loaded but rendered nothing"];
}

/**
 * Load Playwright's Chromium launcher.
 *
 * The import is deferred rather than declared at module scope because an ESM
 * `import` is resolved before any of this file's code runs: with a static one, a
 * checkout that has not installed the browser fails with `ERR_MODULE_NOT_FOUND`
 * before the script can so much as check its arguments — which is what the unit
 * gate saw, since only the audit job installs Playwright (`--no-save`).
 *
 * @returns {Promise<import("playwright").BrowserType>}  The chromium launcher.
 * @throws {Error} If Playwright is not installed, naming how to install it.
 */
async function chromiumLauncher() {
  try {
    return (await import("playwright")).chromium;
  } catch (error) {
    throw new Error(
      `this audit needs Playwright, which is not installed here (${error.code ?? error.message}). ` +
        "Install it with: npm install --no-save playwright && npx playwright install chromium",
    );
  }
}

/**
 * Audit the artifact served at ``baseUrl``.
 *
 * @param {string} baseUrl  The base URL the artifact is served from.
 * @returns {Promise<number>}  The process exit code.
 */
export async function runAudit(baseUrl) {
  const chromium = await chromiumLauncher();
  const browser = await chromium.launch();
  const context = await browser.newContext();
  /** @type {Array<string>} */
  const problems = [];
  try {
    const page = await context.newPage();
    await page.goto(baseUrl, { waitUntil: "load" });

    problems.push(...(await auditViewport(page)));
    const { problems: manifestProblems, manifest } = await auditManifest(page, context.request);
    problems.push(...manifestProblems);
    problems.push(...(await auditIcons(manifest, page.url(), context.request)));

    const workerProblems = await auditServiceWorker(page);
    problems.push(...workerProblems);
    if (workerProblems.length === 0) {
      problems.push(...(await auditOffline(context, page)));
    }
  } finally {
    await context.close();
    await browser.close();
  }

  if (problems.length === 0) {
    console.log(`PWA audit OK: ${baseUrl} is installable and renders offline.`);
    return 0;
  }
  console.error(`PWA audit found ${problems.length} problem(s) at ${baseUrl}:\n`);
  for (const problem of problems) {
    console.error(`  - ${problem}`);
  }
  return 1;
}

const target = process.argv[2];
if (target === undefined) {
  console.error("usage: node scripts/pwa-audit.mjs <base-url>");
  process.exit(2);
}
try {
  process.exit(await runAudit(target));
} catch (error) {
  console.error(`PWA audit could not run: ${error.message}`);
  process.exit(2);
}
