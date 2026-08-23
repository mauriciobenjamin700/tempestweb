// Tests for client/icons/ — name resolution + inline SVG rendering.
import { test } from "node:test";
import assert from "node:assert/strict";
import { freshDom } from "./setup.js";
import {
  createIconSvg,
  registerIcon,
  renderIcon,
  resolveIcon,
} from "../../client/icons/index.js";
import { LUCIDE_PATHS } from "../../client/icons/lucide.js";
import { MATERIAL_PATHS } from "../../client/icons/material.js";
import { applyPatches, buildElement } from "../../client/dom.js";

test("resolveIcon: a bare name resolves against the Lucide set (the default)", () => {
  const def = resolveIcon("mail");
  assert.equal(def.d, LUCIDE_PATHS["mail"]);
  assert.equal(def.viewBox, "0 0 24 24");
  assert.equal(def.mode, "stroke");
});

test("resolveIcon: the lucide: prefix is equivalent to a bare name", () => {
  assert.deepEqual(resolveIcon("lucide:mail"), resolveIcon("mail"));
});

test("resolveIcon: the material: prefix resolves against the Material set (filled)", () => {
  const def = resolveIcon("material:home");
  assert.equal(def.d, MATERIAL_PATHS["home"]);
  assert.equal(def.viewBox, "0 -960 960 960");
  assert.equal(def.mode, "fill");
});

test("resolveIcon: the path: prefix carries a raw d over the wire", () => {
  const def = resolveIcon("path:M3 3 l5 5");
  assert.equal(def.d, "M3 3 l5 5");
  assert.equal(def.mode, "stroke");
});

test("resolveIcon: an unknown or empty name resolves to null", () => {
  assert.equal(resolveIcon("material:not-a-real-icon"), null);
  assert.equal(resolveIcon("definitely-not-lucide"), null);
  assert.equal(resolveIcon(""), null);
  assert.equal(resolveIcon(null), null);
});

test("renderIcon: a Lucide icon draws a stroked path on the 24 grid", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const svg = createIconSvg();
  renderIcon(svg, { name: "mail" });

  assert.equal(svg.getAttribute("viewBox"), "0 0 24 24");
  assert.equal(svg.getAttribute("fill"), "none");
  assert.equal(svg.getAttribute("stroke"), "currentColor");
  const path = svg.querySelector("path");
  assert.ok(path, "has a path");
  assert.equal(path.getAttribute("d"), LUCIDE_PATHS["mail"]);
  assert.equal(svg.getAttribute("aria-hidden"), "true");
});

test("renderIcon: a Material icon draws a filled path on the 960 grid", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const svg = createIconSvg();
  renderIcon(svg, { name: "material:home" });

  assert.equal(svg.getAttribute("viewBox"), "0 -960 960 960");
  assert.equal(svg.getAttribute("fill"), "currentColor");
  assert.equal(svg.getAttribute("stroke"), null);
  assert.equal(svg.querySelector("path").getAttribute("d"), MATERIAL_PATHS["home"]);
});

test("renderIcon: an explicit size sets px width/height; default scales to 1em", () => {
  const dom = freshDom();
  globalThis.document = dom.document;

  const sized = createIconSvg();
  renderIcon(sized, { name: "mail", size: 32 });
  assert.equal(sized.style.width, "32px");
  assert.equal(sized.style.height, "32px");

  const unsized = createIconSvg();
  renderIcon(unsized, { name: "mail" });
  assert.equal(unsized.style.width, "1em");
});

test("renderIcon: a partial update changes the name but keeps the prior size", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const svg = createIconSvg();
  renderIcon(svg, { name: "mail", size: 20 });
  renderIcon(svg, { name: "material:home" }); // name only

  assert.equal(svg.style.width, "20px", "size preserved");
  assert.equal(svg.getAttribute("viewBox"), "0 -960 960 960", "name switched");
});

test("renderIcon: an unknown name clears the glyph but keeps the box", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const svg = createIconSvg();
  renderIcon(svg, { name: "mail" });
  renderIcon(svg, { name: "nope-not-real" });
  assert.equal(svg.querySelector("path"), null);
});

test("buildElement: an Icon node builds an inline <svg> carrying the glyph", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = buildElement({
    type: "Icon",
    key: "i",
    props: { name: "material:home", size: 24 },
    children: [],
  });
  assert.equal(el.tagName.toLowerCase(), "svg");
  assert.equal(el.getAttribute("data-tw-type"), "Icon");
  assert.equal(el.getAttribute("data-tw-key"), "i");
  assert.equal(el.querySelector("path").getAttribute("d"), MATERIAL_PATHS["home"]);
});

test("registerIcon: a custom icon resolves by name with its own viewBox/mode", () => {
  registerIcon("my-glyph", "M0 0 h10", { viewBox: "0 0 10 10", mode: "fill" });
  const def = resolveIcon("my-glyph");
  assert.equal(def.d, "M0 0 h10");
  assert.equal(def.viewBox, "0 0 10 10");
  assert.equal(def.mode, "fill");
});

test("buildElement: an IconButton is a real <button> carrying its glyph", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = buildElement({
    type: "IconButton",
    key: "burger",
    props: { icon: "menu", label: "menu" },
    children: [],
  });
  assert.equal(el.tagName.toLowerCase(), "button");
  assert.equal(el.getAttribute("type"), "button");
  // The label names the control instead of being painted as text: an icon-only
  // button showing the word "menu" is what the div fallback produced.
  assert.equal(el.getAttribute("aria-label"), "menu");
  assert.equal(el.textContent, "");
  const glyph = el.querySelector('[data-tw-part="glyph"]');
  assert.ok(glyph, "the glyph svg is drawn");
  assert.equal(glyph.querySelector("path").getAttribute("d"), LUCIDE_PATHS["menu"]);
});

test("an Update patch swaps the IconButton glyph without duplicating it", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const root = buildElement({
    type: "IconButton",
    key: "b",
    props: { icon: "menu", label: "menu" },
    children: [],
  });
  applyPatches(root, [{ op: "update", path: [], set_props: { icon: "x" } }]);
  assert.equal(root.querySelectorAll('[data-tw-part="glyph"]').length, 1);
  const glyph = root.querySelector('[data-tw-part="glyph"]');
  assert.equal(glyph.querySelector("path").getAttribute("d"), LUCIDE_PATHS["x"]);
});

test("buildElement: an app's semantics label wins over the icon label", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = buildElement({
    type: "IconButton",
    key: "b",
    props: { icon: "x", label: "clear", semantics: { label: "Limpar busca" } },
    children: [],
  });
  assert.equal(el.getAttribute("aria-label"), "Limpar busca");
});
