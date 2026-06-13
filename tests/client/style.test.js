// Tests for client/style.js — styleToCss over the golden style fixture + edges.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fixture } from "./setup.js";
import { colorToRgba, styleToCss } from "../../client/style.js";

/** Parse a "a: b; c: d" CSS body into a {a:b, c:d} map for order-independent checks. */
function declarations(css) {
  /** @type {Record<string, string>} */
  const out = {};
  for (const part of css.split(";")) {
    const trimmed = part.trim();
    if (!trimmed) continue;
    const i = trimmed.indexOf(":");
    out[trimmed.slice(0, i).trim()] = trimmed.slice(i + 1).trim();
  }
  return out;
}

test("style_sample.json maps to the expected CSS declarations", () => {
  const css = styleToCss(fixture("style_sample.json"));
  const d = declarations(css);
  // direction: column -> display:flex + flex-direction:column
  assert.equal(d["display"], "flex");
  assert.equal(d["flex-direction"], "column");
  assert.equal(d["gap"], "8px");
  assert.equal(d["padding"], "16px 16px 16px 16px");
  assert.equal(d["background"], "rgba(255, 255, 255, 1)");
  assert.equal(d["color"], "rgba(17, 17, 17, 1)");
  assert.equal(d["width"], "320px");
  // Null fields produce no declarations.
  assert.equal("margin" in d, false);
  assert.equal("border" in d, false);
  assert.equal("height" in d, false);
});

test("null style yields an empty string", () => {
  assert.equal(styleToCss(null), "");
  assert.equal(styleToCss(undefined), "");
});

test("empty style object yields an empty string", () => {
  assert.equal(styleToCss({}), "");
});

test("Row/Column are flex containers by type (no explicit direction)", () => {
  // A null/empty style still becomes a flex container when the widget type is
  // Row or Column — so gap/justify/align are never silently inert on the web.
  assert.equal(styleToCss(null, "Column"), "display: flex; flex-direction: column");
  assert.equal(styleToCss(null, "Row"), "display: flex; flex-direction: row");
  const col = declarations(styleToCss({ gap: 8 }, "Column"));
  assert.equal(col["display"], "flex");
  assert.equal(col["flex-direction"], "column");
  assert.equal(col["gap"], "8px");
});

test("an explicit style.direction overrides the type's natural axis", () => {
  const d = declarations(styleToCss({ direction: "row" }, "Column"));
  assert.equal(d["display"], "flex");
  assert.equal(d["flex-direction"], "row");
});

test("non-flex types (Container) stay block without a direction", () => {
  assert.equal(styleToCss(null, "Container"), "");
  const d = declarations(styleToCss({ padding: { top: 4, right: 4, bottom: 4, left: 4 } }, "Container"));
  assert.equal("display" in d, false);
});

test("transition maps to the CSS transition shorthand (E.4)", () => {
  const css = styleToCss({
    transition: { duration_ms: 200, curve: "ease-in-out", delay_ms: 50 },
  });
  assert.ok(css.includes("transition: all 200ms ease-in-out 50ms"), css);
});

test("transition with a zero delay omits the delay term", () => {
  const css = styleToCss({
    transition: { duration_ms: 120, curve: "linear", delay_ms: 0 },
  });
  assert.ok(css.includes("transition: all 120ms linear"), css);
  assert.ok(!css.includes("0ms 0ms"), css);
});

test("bounce/elastic curves fall back to overshooting cubic-beziers", () => {
  const bounce = styleToCss({ transition: { duration_ms: 100, curve: "bounce", delay_ms: 0 } });
  assert.ok(bounce.includes("cubic-bezier("), bounce);
});

test("colorToRgba renders {r,g,b,a} as rgba(...)", () => {
  assert.equal(colorToRgba({ r: 10, g: 20, b: 30, a: 0.5 }), "rgba(10, 20, 30, 0.5)");
});

test("flex justify/align map start/end to flex-start/flex-end", () => {
  const d = declarations(styleToCss({ justify: "start", align: "end" }));
  assert.equal(d["justify-content"], "flex-start");
  assert.equal(d["align-items"], "flex-end");
});

test("flex justify keeps space-* and center verbatim", () => {
  const d = declarations(styleToCss({ justify: "space-between", align: "center" }));
  assert.equal(d["justify-content"], "space-between");
  assert.equal(d["align-items"], "center");
});

test("grow, gap, flex_wrap and align_self map to flex CSS", () => {
  const d = declarations(
    styleToCss({ grow: 1, gap: 12, flex_wrap: "wrap", align_self: "start" }),
  );
  assert.equal(d["flex-grow"], "1");
  assert.equal(d["gap"], "12px");
  assert.equal(d["flex-wrap"], "wrap");
  assert.equal(d["align-self"], "flex-start");
});

test("Edge padding and margin render as four-value px shorthands", () => {
  const d = declarations(
    styleToCss({
      padding: { top: 1, right: 2, bottom: 3, left: 4 },
      margin: { top: 5, right: 6, bottom: 7, left: 8 },
    }),
  );
  assert.equal(d["padding"], "1px 2px 3px 4px");
  assert.equal(d["margin"], "5px 6px 7px 8px");
});

test("uniform Border renders Npx solid rgba(...)", () => {
  const d = declarations(
    styleToCss({ border: { width: 2, color: { r: 0, g: 0, b: 0, a: 1 } } }),
  );
  assert.equal(d["border"], "2px solid rgba(0, 0, 0, 1)");
});

test("uniform Border with null color falls back to currentColor", () => {
  const d = declarations(styleToCss({ border: { width: 1, color: null } }));
  assert.equal(d["border"], "1px solid currentColor");
});

test("per-side SideBorder renders only the set sides", () => {
  const css = styleToCss({
    border: {
      top: null,
      right: null,
      bottom: { width: 1, color: { r: 200, g: 0, b: 0, a: 1 } },
      left: null,
    },
  });
  const d = declarations(css);
  assert.equal(d["border-bottom"], "1px solid rgba(200, 0, 0, 1)");
  assert.equal("border-top" in d, false);
  assert.equal("border" in d, false);
});

test("uniform radius and per-corner Corners both render", () => {
  assert.equal(declarations(styleToCss({ radius: 8 }))["border-radius"], "8px");
  const corners = declarations(
    styleToCss({
      radius: { top_left: 1, top_right: 2, bottom_right: 3, bottom_left: 4 },
    }),
  );
  assert.equal(corners["border-radius"], "1px 2px 3px 4px");
});

test("gradient background renders linear-gradient with axis + stops", () => {
  const css = styleToCss({
    background: {
      direction: "left-right",
      stops: [
        { color: { r: 0, g: 0, b: 0, a: 1 }, position: 0 },
        { color: { r: 255, g: 255, b: 255, a: 1 }, position: 1 },
      ],
    },
  });
  const d = declarations(css);
  assert.equal(
    d["background"],
    "linear-gradient(to right, rgba(0, 0, 0, 1) 0%, rgba(255, 255, 255, 1) 100%)",
  );
});

test("typography fields map to CSS", () => {
  const d = declarations(
    styleToCss({
      font_family: "Inter",
      font_size: 14,
      font_weight: 700,
      font_style: "italic",
      text_align: "center",
      text_decoration: "underline",
      letter_spacing: 0.5,
      line_height: 1.5,
    }),
  );
  assert.equal(d["font-family"], "Inter");
  assert.equal(d["font-size"], "14px");
  assert.equal(d["font-weight"], "700");
  assert.equal(d["font-style"], "italic");
  assert.equal(d["text-align"], "center");
  assert.equal(d["text-decoration"], "underline");
  assert.equal(d["letter-spacing"], "0.5px");
  assert.equal(d["line-height"], "1.5");
});

test("dimension fields map to CSS px (and unitless aspect-ratio)", () => {
  const d = declarations(
    styleToCss({
      width: 100,
      height: 50,
      min_width: 10,
      max_width: 200,
      min_height: 20,
      max_height: 300,
      aspect_ratio: 1.5,
    }),
  );
  assert.equal(d["width"], "100px");
  assert.equal(d["height"], "50px");
  assert.equal(d["min-width"], "10px");
  assert.equal(d["max-width"], "200px");
  assert.equal(d["min-height"], "20px");
  assert.equal(d["max-height"], "300px");
  assert.equal(d["aspect-ratio"], "1.5");
});

test("opacity maps verbatim", () => {
  assert.equal(declarations(styleToCss({ opacity: 0.25 }))["opacity"], "0.25");
});
