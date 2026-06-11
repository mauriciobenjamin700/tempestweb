// Tests for client/pwa/manifest.js — P0 (installable manifest).
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  buildManifest,
  emitManifest,
  validateInstallable,
  DEFAULT_ICONS,
} from "../../client/pwa/manifest.js";

test("buildManifest fills installable defaults", () => {
  const m = buildManifest();
  assert.equal(m.display, "standalone");
  assert.equal(m.start_url, "/");
  assert.equal(m.scope, "/");
  assert.ok(m.name || m.short_name);
  assert.ok(Array.isArray(m.icons) && m.icons.length >= 2);
  assert.equal(m.id, "/"); // defaults to scope
});

test("buildManifest is installable-shaped by default", () => {
  assert.deepEqual(validateInstallable(buildManifest()), []);
});

test("default icon set has 192/512 and an 'any' purpose", () => {
  const hasSize = (s) =>
    DEFAULT_ICONS.some((i) => i.sizes.split(/\s+/).includes(s));
  assert.ok(hasSize("192x192"));
  assert.ok(hasSize("512x512"));
  assert.ok(DEFAULT_ICONS.some((i) => (i.purpose ?? "any").split(/\s+/).includes("any")));
});

test("project overrides win and pass through extras", () => {
  const m = buildManifest({
    name: "My App",
    short_name: "App",
    start_url: "/home",
    scope: "/app/",
    theme_color: "#0af",
    shortcuts: [{ name: "New", url: "/new" }],
    share_target: { action: "/share", method: "POST" },
    file_handlers: [{ action: "/open", accept: { "text/csv": [".csv"] } }],
    categories: ["productivity"],
    orientation: "portrait",
  });
  assert.equal(m.name, "My App");
  assert.equal(m.start_url, "/home");
  assert.equal(m.scope, "/app/");
  assert.equal(m.id, "/app/");
  assert.equal(m.theme_color, "#0af");
  assert.equal(m.shortcuts[0].url, "/new");
  assert.equal(m.share_target.method, "POST");
  assert.equal(m.file_handlers[0].action, "/open");
  assert.deepEqual(m.categories, ["productivity"]);
  assert.equal(m.orientation, "portrait");
});

test("invalid display falls back to standalone", () => {
  assert.equal(buildManifest({ display: "browser" }).display, "standalone");
  assert.equal(buildManifest({ display: "weird" }).display, "standalone");
  assert.equal(buildManifest({ display: "fullscreen" }).display, "fullscreen");
});

test("emitManifest produces valid JSON", () => {
  const json = emitManifest(buildManifest({ name: "X" }));
  const parsed = JSON.parse(json);
  assert.equal(parsed.name, "X");
});

test("validateInstallable flags missing pieces", () => {
  assert.deepEqual(validateInstallable({}).length > 0, true);
  const noBig = {
    name: "x",
    start_url: "/",
    display: "standalone",
    icons: [{ src: "/a.png", sizes: "192x192", type: "image/png", purpose: "any" }],
  };
  assert.ok(validateInstallable(noBig).includes("a 512x512 icon is required"));

  const onlyMaskable = {
    name: "x",
    start_url: "/",
    display: "standalone",
    icons: [
      { src: "/a.png", sizes: "192x192", type: "image/png", purpose: "maskable" },
      { src: "/b.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
  assert.ok(validateInstallable(onlyMaskable).includes('at least one icon must have purpose "any"'));
});
