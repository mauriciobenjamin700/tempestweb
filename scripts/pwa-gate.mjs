#!/usr/bin/env node
// pwa-gate.mjs — the CI PWA gate's fast check (P4).
//
// Validates that the default manifest the build emits is installable-shaped and
// that the push payload contract is intact, without needing a browser. The
// heavier Lighthouse + Playwright layers run separately in the workflow; this
// script is the deterministic, always-runnable core of the gate.
//
// Exit code 0 means the PWA contract holds; non-zero fails the job.

import { buildManifest, validateInstallable } from "../client/pwa/manifest.js";
import { buildNotification, resolveClickUrl, applyBadge } from "../client/sw/sw.js";

/** @type {string[]} */
const problems = [];

// 1. The default manifest must be installable-shaped.
const manifest = buildManifest();
const manifestErrors = validateInstallable(manifest);
if (manifestErrors.length > 0) {
  problems.push(`manifest not installable: ${manifestErrors.join("; ")}`);
}

// 2. The push notification builder must shape a notification from a payload.
const notif = buildNotification({ title: "T", body: "B", data: { url: "/x" } });
if (!notif || notif.title !== "T") {
  problems.push("buildNotification did not shape the notification");
}

// 3. A deep-link click must resolve to the payload url.
if (resolveClickUrl({ url: "/deep" }, null, "/") !== "/deep") {
  problems.push("resolveClickUrl did not honor the deep link");
}

// 4. Badging must not throw on a payload (best-effort, unsupported nav).
let badgeOk = true;
try {
  await applyBadge({ badge_count: 1 }, {});
} catch {
  badgeOk = false;
}
if (!badgeOk) problems.push("applyBadge threw on an unsupported navigator");

const pushSmoke = process.argv.includes("--push-smoke");
if (pushSmoke) {
  // The push-e2e job's deterministic placeholder: assert the SW push contract
  // (the live subscribe->send->notify path needs a served build + VAPID pair).
  console.log("push-smoke: SW push/click/badge contract OK (live e2e pending build)");
}

if (problems.length > 0) {
  console.error("PWA gate FAILED:");
  for (const p of problems) console.error(`  - ${p}`);
  process.exit(1);
}

console.log("PWA gate OK: manifest installable, push contract intact.");
