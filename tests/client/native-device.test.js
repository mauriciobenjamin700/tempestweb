// native-device.test.js — coarse hardware facts, and the browser that says none.
//
// The case that matters is the LAST one: a browser exposing neither
// `deviceMemory` nor `performance.memory` must get a profile of nulls, not a
// throw. That is Safari and Firefox — the common case, not the edge — and an app
// that adapts quality has a default to fall back to.

import assert from "node:assert/strict";
import test from "node:test";
import "./setup.js";

import { deviceProfile } from "../../client/native/device.js";

test("reads what Chromium exposes", async () => {
  const profile = await deviceProfile(
    {},
    {
      navigator: { deviceMemory: 8, hardwareConcurrency: 12 },
      performance: { memory: { usedJSHeapSize: 52428800, jsHeapSizeLimit: 4294705152 } },
    },
  );
  assert.equal(profile.memory_gb, 8);
  assert.equal(profile.cores, 12);
  assert.equal(profile.heap_used_mb, 50);
  assert.equal(profile.heap_limit_mb, 4095.8);
});

test("cores alone is a valid answer — it is the widely available one", async () => {
  const profile = await deviceProfile({}, { navigator: { hardwareConcurrency: 4 }, performance: {} });
  assert.equal(profile.cores, 4);
  assert.equal(profile.memory_gb, null);
  assert.equal(profile.heap_used_mb, null);
});

test("a browser that exposes nothing answers nulls, not an exception", async () => {
  const profile = await deviceProfile({}, { navigator: {}, performance: {} });
  assert.deepEqual(profile, {
    memory_gb: null,
    cores: null,
    heap_used_mb: null,
    heap_limit_mb: null,
  });
});

test("with nothing injected it reads the real globals and does not throw", async () => {
  // deps.navigator absent falls back to globalThis.navigator, which is what a
  // real page wants; the point here is that the fallback path cannot raise.
  const profile = await deviceProfile({}, {});
  for (const field of ["memory_gb", "cores", "heap_used_mb", "heap_limit_mb"]) {
    assert.ok(
      profile[field] === null || typeof profile[field] === "number",
      `${field} must be a number or null, got ${profile[field]}`,
    );
  }
});

test("a zero means not measured, not measured as zero", async () => {
  const profile = await deviceProfile(
    {},
    { navigator: { deviceMemory: 0, hardwareConcurrency: 0 }, performance: { memory: { usedJSHeapSize: 0 } } },
  );
  assert.equal(profile.memory_gb, null);
  assert.equal(profile.cores, null);
  assert.equal(profile.heap_used_mb, null);
});

test("a non-number is refused rather than passed through", async () => {
  const profile = await deviceProfile(
    {},
    { navigator: { deviceMemory: "muita", hardwareConcurrency: NaN }, performance: {} },
  );
  assert.equal(profile.memory_gb, null);
  assert.equal(profile.cores, null);
});

test("Infinity is not a heap size", async () => {
  const profile = await deviceProfile(
    {},
    { navigator: {}, performance: { memory: { jsHeapSizeLimit: Infinity } } },
  );
  assert.equal(profile.heap_limit_mb, null);
});
