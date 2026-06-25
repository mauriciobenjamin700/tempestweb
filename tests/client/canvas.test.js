// Tests for Canvas rendering in client/dom.js — buildElement maps a Canvas node
// to a real <canvas>, sizes its buffer and stores its draw-command list.
//
// jsdom has no 2D canvas backend (getContext returns null), so paintCanvas
// no-ops on the actual drawing; these tests cover the element shape, sizing and
// command storage. The pixel output is verified live in a browser (Playwright).
import { test } from "node:test";
import assert from "node:assert/strict";
import { freshDom } from "./setup.js";
import { buildElement } from "../../client/dom.js";

/** Install jsdom's `document` globally so dom.js's `document.createElement` works. */
function withDocument() {
  const dom = freshDom();
  globalThis.document = dom.document;
  return dom;
}

/**
 * Build a minimal Canvas IR node.
 * @param {Object[]} commands  The draw-command list.
 * @returns {import("../../client/transport.js").Node}
 */
function canvasNode(commands) {
  return {
    type: "Canvas",
    key: "chart",
    props: { width: 320, height: 200, commands },
    children: [],
  };
}

test("buildElement maps a Canvas node to a sized <canvas>", () => {
  withDocument();
  const el = buildElement(
    canvasNode([
      { kind: "move_to", x: 0, y: 0 },
      { kind: "line_to", x: 10, y: 10 },
      { kind: "stroke", color: [0, 0, 0, 1], width: 1 },
    ])
  );
  assert.equal(el.tagName, "CANVAS");
  assert.equal(el.width, 320);
  assert.equal(el.height, 200);
});

test("buildElement remembers the Canvas command list on the element", () => {
  withDocument();
  const commands = [
    { kind: "draw_rect", x: 4, y: 4, width: 20, height: 40 },
    { kind: "fill", color: [0.5, 0.2, 0.8, 1] },
    { kind: "draw_text", text: "42", x: 8, y: 8, size: 11, color: [0, 0, 0, 1] },
  ];
  const el = buildElement(canvasNode(commands));
  assert.deepEqual(el._twCanvasCmds, commands);
  assert.equal(el._twCanvasW, 320);
  assert.equal(el._twCanvasH, 200);
});

test("painting a Canvas with no 2D context does not throw", () => {
  withDocument();
  // jsdom getContext returns null; paintCanvas must degrade gracefully.
  assert.doesNotThrow(() =>
    buildElement(
      canvasNode([
        { kind: "move_to", x: 1, y: 1 },
        { kind: "line_to", x: 2, y: 2 },
        { kind: "stroke", color: [1, 0, 0, 1], width: 2 },
        { kind: "draw_text", text: "x", x: 0, y: 0, size: 12, color: [0, 0, 0, 1] },
      ])
    )
  );
});

test("an unknown draw command is ignored", () => {
  withDocument();
  assert.doesNotThrow(() =>
    buildElement(canvasNode([{ kind: "warp_field", x: 1 }]))
  );
});
