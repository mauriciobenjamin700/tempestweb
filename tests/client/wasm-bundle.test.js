/**
 * The committed Mode A bundle is exactly what esbuild produces from the sources.
 *
 * The Python suite re-hashes the bundle's inputs (tests/unit/test_wasm_boot.py),
 * which catches an edited module. This one re-runs the bundler itself, which
 * also catches a bundle edited by hand or produced by another esbuild version
 * than the pinned devDependency.
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

test("client/bundle/tempestweb-wasm.js matches a fresh esbuild run", () => {
  const output = execFileSync(
    process.execPath,
    [join(ROOT, "scripts", "bundle-client.mjs"), "--check"],
    { cwd: ROOT, encoding: "utf8" },
  );
  assert.match(output, /bundle up to date/);
});

test("the bundle exports every name the wasm shell imports", async () => {
  const bundle = await import(join(ROOT, "client", "bundle", "tempestweb-wasm.js"));
  for (const name of [
    "mount",
    "createWasmTransport",
    "installNativeBridge",
    "applyThemeMode",
    "mountConnectivityBanner",
  ]) {
    assert.equal(typeof bundle[name], "function", name);
  }
});
