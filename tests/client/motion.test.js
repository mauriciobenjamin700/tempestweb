// Tests for client/transpile/motion.js — declarative transition values.
import { test } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import { Curve, Transition } from "../../client/transpile/motion.js";
import { buildElement } from "../../client/dom.js";
import { Style } from "../../client/transpile/widget-support.js";

test("Transition returns the wire shape style.js reads", () => {
  const tr = Transition({ duration_ms: 300, curve: Curve.EASE_IN_OUT });
  assert.deepEqual(tr, { duration_ms: 300, curve: "ease-in-out", delay_ms: 0 });
  assert.equal(Transition({ duration_ms: 120, curve: Curve.LINEAR, delay_ms: 50 }).delay_ms, 50);
});

test("a Style transition renders a CSS transition on the element", () => {
  const dom = new JSDOM("<!doctype html><body></body>");
  globalThis.document = dom.window.document;
  const node = {
    type: "Container",
    key: "b",
    props: {
      attrs: {},
      focus_order: null,
      focusable: null,
      semantics: null,
      tag: null,
      style: Style({ width: 100.0, transition: Transition({ duration_ms: 300, curve: Curve.EASE }) }),
    },
    children: [],
  };
  const el = buildElement(node);
  const css = el.getAttribute("style") || "";
  assert.match(css, /transition:/);
  assert.match(css, /300ms/);
});
