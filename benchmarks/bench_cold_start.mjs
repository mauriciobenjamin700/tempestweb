#!/usr/bin/env node
// bench_cold_start.mjs — Mode A cold start, cold and warm (Track S — S9).
//
// Mode A's trade-off is stated in the docs ("Mode A does not promise a small
// bundle") and was never measured, so there was no number to watch get worse
// (tempestweb#120). This measures the two that matter, and they are different
// numbers for the same page:
//
//   cold — service worker and caches cleared: Pyodide and the core come over the
//          network. This is a first visit.
//   warm — the SW precache serves them. This is every visit after.
//
// Both are reported. Reporting only the warm one would hide the cost a first-time
// reader actually pays; only the cold one would hide what the SW buys.
//
// Playwright is an optional dependency on purpose: this runs in a scheduled job,
// not on every PR (a Pyodide download does not belong in a PR's critical path).
//
//   npm install --no-save playwright && npx playwright install chromium
//   node benchmarks/bench_cold_start.mjs http://127.0.0.1:8000/

const url = process.argv[2] ?? "http://127.0.0.1:8000/";

/**
 * Load Playwright, or explain how to get it.
 * @returns {Promise<Object>}  The playwright module.
 */
async function loadPlaywright() {
  try {
    return await import("playwright");
  } catch {
    console.error(
      "playwright is not installed. This benchmark needs a real browser:\n" +
        "  npm install --no-save playwright && npx playwright install chromium",
    );
    process.exit(2);
  }
}

/**
 * Measure one load.
 *
 * The clock starts at navigation and stops when the app's first tree is on
 * screen — which is the honest definition of "the reader can use it". Waiting for
 * `load` would stop before Pyodide even starts; waiting for a fixed timeout would
 * measure the timeout.
 *
 * @param {import("playwright").Page} page  The page to drive.
 * @param {boolean} clearCaches  Whether to clear the SW and caches first.
 * @returns {Promise<{ms: number, transferredKb: number}>}  The measurement.
 */
async function measureLoad(page, clearCaches) {
  if (clearCaches) {
    await page.goto(url);
    await page.evaluate(async () => {
      for (const registration of (await navigator.serviceWorker?.getRegistrations?.()) ?? []) {
        await registration.unregister();
      }
      for (const key of (await caches?.keys?.()) ?? []) await caches.delete(key);
    });
  }

  let transferred = 0;
  const onResponse = async (response) => {
    const length = Number(response.headers()["content-length"] ?? 0);
    transferred += Number.isFinite(length) ? length : 0;
  };
  page.on("response", onResponse);

  const started = Date.now();
  await page.goto(url, { waitUntil: "commit" });
  // The app's first tree carries data-tw-key; nothing else on the page does.
  await page.waitForSelector("[data-tw-key]", { timeout: 120_000 });
  const elapsed = Date.now() - started;
  page.off("response", onResponse);

  return { ms: elapsed, transferredKb: Math.round(transferred / 1024) };
}

const { chromium } = await loadPlaywright();
const browser = await chromium.launch();
const context = await browser.newContext();
const page = await context.newPage();

console.log(`Mode A cold start — ${url}\n`);

const cold = await measureLoad(page, true);
console.log(`cold (no SW, no cache)  ${cold.ms.toString().padStart(6)} ms  ${cold.transferredKb} KB transferred`);

// Give the service worker a moment to finish precaching before the warm run.
await page.waitForTimeout(3000);
const warm = await measureLoad(page, false);
console.log(`warm (SW precache)      ${warm.ms.toString().padStart(6)} ms  ${warm.transferredKb} KB transferred`);

const saved = cold.ms - warm.ms;
console.log(
  `\nthe service worker saves ${saved} ms on a repeat visit ` +
    `(${((saved / cold.ms) * 100).toFixed(0)}% of the cold load)`,
);

await browser.close();
