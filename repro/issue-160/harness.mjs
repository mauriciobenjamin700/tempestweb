// harness.mjs — drive one cold-origin run of the issue #160 reproduction.
//
// One run = one fresh Chrome profile, one fresh port, an empty HTTP cache and a
// service worker that registers for the first time on that origin. The harness
// measures instead of eyeballing: boot time to Pyodide-ready, how many assets the
// worker precached, the child count of every container the report names, and every
// console line the client emitted (with `globalThis.__tempestweb_debug` on from
// before the first script runs, so the batch log cannot be missed).
//
// Usage:
//   node harness.mjs --port 8901 --profile /tmp/p1 --out /tmp/run1.json \
//        [--down-mbps 4] [--rtt-ms 150] [--cpu 4] [--ticks 4] [--label clean-1]

import { createRequire } from "node:module";
import { writeFileSync } from "node:fs";

const require = createRequire(import.meta.url);
const PW = "/home/mauriciobenjamin700/projects/my/packages/tempest-react-sdk/node_modules/playwright-core";
const { chromium } = require(PW);

/**
 * Parse `--flag value` pairs from argv.
 * @returns {Record<string, string>} The flags, without their leading dashes.
 */
function args() {
  const out = {};
  for (let i = 2; i < process.argv.length; i += 2) {
    out[process.argv[i].replace(/^--/, "")] = process.argv[i + 1];
  }
  return out;
}

const opts = args();
const port = Number(opts.port);
const ticks = Number(opts.ticks ?? 4);
const origin = `http://127.0.0.1:${port}`;

/** Recorded console lines, page errors and failed requests. */
const console_lines = [];
const page_errors = [];
const failed_requests = [];

/**
 * Serialize a console argument for the log without blowing up on a 700 KB batch.
 * @param {*} value  The argument.
 * @returns {{text: string, chars: number}}  A capped rendering plus the real size.
 */
function cap(value) {
  let text;
  try {
    text = typeof value === "string" ? value : JSON.stringify(value);
  } catch {
    text = String(value);
  }
  if (text == null) text = String(value);
  return { text: text.slice(0, 3000), chars: text.length };
}

const result = {
  label: opts.label ?? "run",
  port,
  origin,
  viewport: { width: Number(opts.width ?? 1280), height: Number(opts.height ?? 900) },
  throttle: {
    down_mbps: opts["down-mbps"] ? Number(opts["down-mbps"]) : null,
    rtt_ms: opts["rtt-ms"] ? Number(opts["rtt-ms"]) : null,
    cpu_rate: opts.cpu ? Number(opts.cpu) : null,
  },
};

const context = await chromium.launchPersistentContext(opts.profile, {
  executablePath: "/usr/bin/google-chrome",
  headless: false,
  viewport: {
    width: Number(opts.width ?? 1280),
    height: Number(opts.height ?? 900),
  },
  args: ["--no-first-run", "--no-default-browser-check", "--disable-features=Translate"],
});

const page = await context.newPage();

await page.addInitScript(() => {
  globalThis.__tempestweb_debug = true;
  globalThis.__twLog = [];
  globalThis.__twDamage = null;

  /**
   * Snapshot the containers the report names, from inside the page.
   * Taken at the instant the renderer reports a patch it could not apply, so the
   * truncated tree is measured before the resync repairs it.
   * @returns {Object} Child counts and the values the aborted batch carried.
   */
  const snapshot = () => {
    const at = (key) => document.querySelector(`[data-tw-key="${key}"]`);
    const actions = at("appbar-actions");
    const filters = at("filters");
    const header = at("table-header");
    return {
      appbar_actions_children: actions ? actions.children.length : null,
      appbar_action_labels: actions
        ? Array.from(actions.children).map((el) => el.textContent.trim())
        : null,
      filter_placeholders: filters
        ? Array.from(filters.querySelectorAll("input")).map((el) =>
            el.getAttribute("placeholder"),
          )
        : null,
      table_columns: header ? header.children.length : null,
      usage_label: at("usage-label") ? at("usage-label").textContent.trim() : null,
      footer: at("footer") ? at("footer").textContent.trim() : null,
    };
  };

  for (const level of ["log", "warn", "error"]) {
    const original = console[level].bind(console);
    console[level] = (...items) => {
      let rendered = [];
      for (const item of items) {
        let text;
        if (typeof item === "string") {
          text = item;
        } else if (item instanceof Error) {
          text = `${item.name}: ${item.message}`;
        } else {
          try {
            text = JSON.stringify(item);
          } catch {
            text = String(item);
          }
        }
        if (text == null) text = String(item);
        rendered.push({ chars: text.length, head: text.slice(0, 3000) });
      }
      globalThis.__twLog.push({ level, at: Date.now(), args: rendered });
      if (
        globalThis.__twDamage === null &&
        rendered.some((entry) => entry.head.includes("patch could not be applied"))
      ) {
        globalThis.__twDamage = { at: Date.now(), dom: snapshot() };
      }
      original(...items);
    };
  }
});

page.on("pageerror", (error) => page_errors.push(String(error)));
page.on("requestfailed", (request) =>
  failed_requests.push({ url: request.url(), failure: request.failure()?.errorText ?? "" }),
);

const cdp = await context.newCDPSession(page);
if (result.throttle.down_mbps != null) {
  await cdp.send("Network.enable");
  await cdp.send("Network.emulateNetworkConditions", {
    offline: false,
    latency: result.throttle.rtt_ms ?? 0,
    downloadThroughput: (result.throttle.down_mbps * 1000 * 1000) / 8,
    uploadThroughput: (result.throttle.down_mbps * 1000 * 1000) / 8,
  });
}
if (result.throttle.cpu_rate != null) {
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: result.throttle.cpu_rate });
}

const t0 = Date.now();
await page.goto(origin + "/", { waitUntil: "commit" });

// Boot is done when the app's own tree exists: the login button is in the DOM.
let boot_ms = null;
try {
  await page.waitForSelector('[data-tw-key="login-submit"]', { timeout: 180000 });
  boot_ms = Date.now() - t0;
} catch (error) {
  result.boot_error = String(error).slice(0, 400);
}
result.boot_ms = boot_ms;

/**
 * Read the service-worker and cache state of the origin from the page.
 * @returns {Promise<Object>} Registration scope/state plus per-cache entry counts.
 */
async function swState() {
  return page.evaluate(async () => {
    const registrations = await navigator.serviceWorker.getRegistrations();
    const names = await caches.keys();
    const counts = {};
    for (const name of names) {
      counts[name] = (await (await caches.open(name)).keys()).length;
    }
    return {
      registered: registrations.length > 0,
      scopes: registrations.map((r) => r.scope),
      states: registrations.map((r) => ({
        installing: !!r.installing,
        waiting: !!r.waiting,
        active: r.active ? r.active.state : null,
      })),
      controlled: !!navigator.serviceWorker.controller,
      caches: counts,
    };
  });
}

result.sw_at_boot = await swState();

/**
 * Measure the containers the report names, by their widget keys.
 * @returns {Promise<Object>} Child counts and the values a later patch changes.
 */
async function measure() {
  return page.evaluate(() => {
    const at = (key) => document.querySelector(`[data-tw-key="${key}"]`);
    const actions = at("appbar-actions");
    const filters = at("filters");
    const table = at("table");
    const inputs = filters ? Array.from(filters.querySelectorAll("input")) : [];
    const headerRow = at("table-header");
    return {
      appbar_actions_children: actions ? actions.children.length : null,
      appbar_action_labels: actions
        ? Array.from(actions.children).map((el) => el.textContent.trim())
        : null,
      filters_children: filters ? filters.children.length : null,
      filter_placeholders: inputs.map((el) => el.getAttribute("placeholder")),
      table_columns: headerRow ? headerRow.children.length : null,
      table_header_labels: headerRow
        ? Array.from(headerRow.children).map((el) => el.textContent.trim())
        : null,
      table_rows: table ? table.children.length : null,
      footer: at("footer") ? at("footer").textContent.trim() : null,
      usage_label: at("usage-label") ? at("usage-label").textContent.trim() : null,
      usage_bar_width: at("usage-bar") ? at("usage-bar").style.width : null,
      root_children: at("root") ? at("root").children.length : null,
    };
  });
}

result.before_login = await measure();

if (boot_ms != null) {
  const dwellMs = Number(opts["dwell-ms"] ?? 0);
  if (dwellMs > 0) {
    await page.waitForTimeout(dwellMs);
    result.dwell_dom = await measure();
    result.dwell_sw = await swState();
  }
  const typeChars = Number(opts["type-chars"] ?? 14);
  result.login_field = await page.evaluate(() => {
    const el = document.querySelector('[data-tw-key="login-user"]');
    if (el == null) return null;
    return { tag: el.tagName.toLowerCase(), nested_inputs: el.querySelectorAll("input").length };
  });
  if (typeChars > 0) {
    const field =
      result.login_field && result.login_field.nested_inputs > 0
        ? '[data-tw-key="login-user"] input'
        : '[data-tw-key="login-user"]';
    try {
      await page.click(field, { timeout: 15000 });
      await page.fill(field, "", { timeout: 15000 });
      await page.type(field, "admin@acme.com".slice(0, typeChars), { delay: 25 });
      result.typed_user = await page.inputValue(field);
      result.typed_at_ms = Date.now() - t0;
    } catch (error) {
      result.type_error = String(error).slice(0, 300);
    }
  }
  result.clicked_at_ms = Date.now() - t0;
  await page.click('[data-tw-key="login-submit"]');
  await page
    .waitForSelector('[data-tw-key="table"]', { timeout: 120000 })
    .catch((error) => (result.swap_error = String(error).slice(0, 300)));
  result.after_swap = await measure();
  result.samples = [];
  for (let tick = 0; tick < ticks; tick += 1) {
    await page.waitForTimeout(7300);
    result.samples.push({ tick, at_ms: Date.now() - t0, dom: await measure() });
  }
}

result.sw_at_end = await swState();
result.page_log = await page.evaluate(() => globalThis.__twLog ?? []);
result.damage_at_failure = await page.evaluate(() => globalThis.__twDamage ?? null);
result.page_errors = page_errors;
result.failed_requests = failed_requests;
result.range_errors = result.page_log
  .flatMap((entry) => entry.args.map((a) => a.head))
  .filter((text) => text.includes("patch path out of range"));

await context.close();
writeFileSync(opts.out, JSON.stringify(result, null, 2));
console.log(
  `[${result.label}] boot=${result.boot_ms}ms sw=${result.sw_at_boot.registered} ` +
    `precache=${JSON.stringify(result.sw_at_boot.caches)} rangeErrors=${result.range_errors.length}`,
);
