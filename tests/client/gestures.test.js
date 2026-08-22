// Multi-pointer gestures: pan, pinch, double tap, and pan+zoom together.
//
// The core declares `on_pan`, `on_scale`, `on_double_tap` and `on_interaction`,
// and the client recognized none of them: it tracked one pointer and only ever
// classified tap / swipe / long press. jsdom has no PointerEvent, so pointer
// events are dispatched as MouseEvents with a pointerId defined on them — which
// is exactly what the recognizer reads.
import { test } from "node:test";
import assert from "node:assert/strict";
import { freshDom } from "./setup.js";
import { buildElement } from "../../client/dom.js";
import { installGestures } from "../../client/gestures.js";
import { BASE_THEME_CSS } from "../../client/theme.js";
import { DOUBLE_TAP_MS } from "../../client/constants.js";

/** A mock Transport that records every sendEvent call. */
function mockTransport() {
  /** @type {import("../../client/transport.js").TWEvent[]} */
  const events = [];
  return { events, onPatches() {}, sendEvent: (e) => events.push(e), async close() {} };
}

/** Mount a gesture widget of `type` under the dom root. */
function surface(dom, type, key = "g") {
  const el = buildElement({ type, key, props: {}, children: [] });
  dom.root.appendChild(el);
  return el;
}

/** Dispatch one pointer event with an explicit pointerId. */
function pointer(dom, el, type, { id = 1, x = 0, y = 0 } = {}) {
  const event = new dom.window.MouseEvent(type, { bubbles: true, clientX: x, clientY: y });
  Object.defineProperty(event, "pointerId", { value: id });
  el.dispatchEvent(event);
}

/** Let the per-frame coalescing flush (rAF is absent in jsdom, so it is a microtask). */
function flush() {
  return new Promise((resolve) => setTimeout(resolve, 10));
}

test("dragging a PanHandler reports pan with deltas and velocity", async () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = surface(dom, "PanHandler", "canvas");
  const transport = mockTransport();
  installGestures(dom.root, transport);

  pointer(dom, el, "pointerdown", { x: 100, y: 100 });
  pointer(dom, el, "pointermove", { x: 130, y: 90 });
  await flush();

  assert.equal(transport.events.length, 1);
  const [event] = transport.events;
  assert.equal(event.type, "pan");
  assert.equal(event.key, "canvas");
  assert.equal(event.payload.dx, 30);
  assert.equal(event.payload.dy, -10);
  assert.ok(Number.isFinite(event.payload.vx), "velocity is reported, in px/s");
});

test("a pan stream is coalesced to one report per frame", async () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = surface(dom, "PanHandler");
  const transport = mockTransport();
  installGestures(dom.root, transport);

  pointer(dom, el, "pointerdown", { x: 0, y: 0 });
  for (let i = 1; i <= 8; i++) {
    pointer(dom, el, "pointermove", { x: i * 5, y: 0 });
  }
  await flush();

  // Eight moves, one report: in Mode B each one would be a round trip.
  assert.equal(transport.events.length, 1);
});

test("releasing a pan surface reports nothing extra", async () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = surface(dom, "PanHandler");
  const transport = mockTransport();
  installGestures(dom.root, transport);

  pointer(dom, el, "pointerdown", { x: 10, y: 10 });
  pointer(dom, el, "pointermove", { x: 60, y: 10 });
  await flush();
  pointer(dom, el, "pointerup", { x: 60, y: 10 });
  await flush();

  assert.deepEqual(
    transport.events.map((e) => e.type),
    ["pan"],
    "everything a pan says, it says while moving",
  );
});

test("pinching a ScaleHandler reports scale, focus and rotation", async () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = surface(dom, "ScaleHandler", "photo");
  const transport = mockTransport();
  installGestures(dom.root, transport);

  // Two fingers 100px apart, then 200px apart: a 2x pinch about the same centre.
  pointer(dom, el, "pointerdown", { id: 1, x: 100, y: 100 });
  pointer(dom, el, "pointerdown", { id: 2, x: 200, y: 100 });
  pointer(dom, el, "pointermove", { id: 2, x: 300, y: 100 });
  await flush();

  assert.equal(transport.events.length, 1);
  const [event] = transport.events;
  assert.equal(event.type, "scale");
  assert.equal(event.key, "photo");
  assert.equal(event.payload.scale, 2);
  assert.equal(event.payload.focus_x, 200);
  assert.equal(event.payload.focus_y, 100);
  assert.equal(event.payload.rotation, 0);
});

test("rotating two pointers reports the angle change", async () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = surface(dom, "ScaleHandler");
  const transport = mockTransport();
  installGestures(dom.root, transport);

  pointer(dom, el, "pointerdown", { id: 1, x: 0, y: 0 });
  pointer(dom, el, "pointerdown", { id: 2, x: 100, y: 0 });
  // Same distance, rotated a quarter turn.
  pointer(dom, el, "pointermove", { id: 2, x: 0, y: 100 });
  await flush();

  const [event] = transport.events;
  assert.equal(Math.round(event.payload.rotation), 90);
});

test("two pointers on two widgets stay two independent drags", async () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const first = surface(dom, "PanHandler", "left");
  const second = surface(dom, "PanHandler", "right");
  const transport = mockTransport();
  installGestures(dom.root, transport);

  pointer(dom, first, "pointerdown", { id: 1, x: 0, y: 0 });
  pointer(dom, second, "pointerdown", { id: 2, x: 500, y: 0 });
  pointer(dom, first, "pointermove", { id: 1, x: 20, y: 0 });
  pointer(dom, second, "pointermove", { id: 2, x: 540, y: 0 });
  await flush();

  assert.deepEqual(
    transport.events.map((e) => [e.type, e.key, e.payload.dx]),
    [
      ["pan", "left", 20],
      ["pan", "right", 40],
    ],
    "a pinch needs both pointers on the same widget",
  );
});

test("two quick taps in place report a double tap", async () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = surface(dom, "GestureDetector", "card");
  const transport = mockTransport();
  installGestures(dom.root, transport);

  pointer(dom, el, "pointerdown", { x: 40, y: 40 });
  pointer(dom, el, "pointerup", { x: 40, y: 40 });
  pointer(dom, el, "pointerdown", { x: 42, y: 41 });
  pointer(dom, el, "pointerup", { x: 42, y: 41 });

  assert.deepEqual(
    transport.events.map((e) => e.type),
    ["tap", "double_tap"],
    "the first release is still a tap; the second is the double",
  );
  assert.deepEqual(transport.events[1].payload, { x: 42, y: 41 });
});

test("two taps far apart are two taps", async () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = surface(dom, "GestureDetector");
  const transport = mockTransport();
  installGestures(dom.root, transport);

  pointer(dom, el, "pointerdown", { x: 10, y: 10 });
  pointer(dom, el, "pointerup", { x: 10, y: 10 });
  pointer(dom, el, "pointerdown", { x: 200, y: 10 });
  pointer(dom, el, "pointerup", { x: 200, y: 10 });

  assert.deepEqual(transport.events.map((e) => e.type), ["tap", "tap"]);
});

test("two slow taps are two taps", async () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = surface(dom, "GestureDetector");
  const transport = mockTransport();
  installGestures(dom.root, transport);

  pointer(dom, el, "pointerdown", { x: 10, y: 10 });
  pointer(dom, el, "pointerup", { x: 10, y: 10 });
  await new Promise((resolve) => setTimeout(resolve, DOUBLE_TAP_MS + 40));
  pointer(dom, el, "pointerdown", { x: 10, y: 10 });
  pointer(dom, el, "pointerup", { x: 10, y: 10 });

  assert.deepEqual(transport.events.map((e) => e.type), ["tap", "tap"]);
});

test("a ScaleHandler reports its double tap and not a tap", async () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = surface(dom, "ScaleHandler", "photo");
  const transport = mockTransport();
  installGestures(dom.root, transport);

  pointer(dom, el, "pointerdown", { x: 30, y: 30 });
  pointer(dom, el, "pointerup", { x: 30, y: 30 });
  assert.deepEqual(transport.events, [], "a pinch surface has no tap handler");

  pointer(dom, el, "pointerdown", { x: 31, y: 30 });
  pointer(dom, el, "pointerup", { x: 31, y: 30 });
  assert.deepEqual(transport.events.map((e) => e.type), ["double_tap"]);
});

test("a swipe is not mistaken for a double tap", async () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = surface(dom, "GestureDetector");
  const transport = mockTransport();
  installGestures(dom.root, transport);

  pointer(dom, el, "pointerdown", { x: 10, y: 10 });
  pointer(dom, el, "pointermove", { x: 90, y: 12 });
  pointer(dom, el, "pointerup", { x: 90, y: 12 });
  pointer(dom, el, "pointerdown", { x: 10, y: 10 });
  pointer(dom, el, "pointermove", { x: 90, y: 12 });
  pointer(dom, el, "pointerup", { x: 90, y: 12 });

  assert.deepEqual(
    transport.events.map((e) => e.type),
    ["swipe", "swipe"],
    "a pointer that travelled is never a tap, so it is never half a double tap",
  );
});

test("an InteractiveViewer reports one interaction for pan and for zoom", async () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = surface(dom, "InteractiveViewer", "map");
  const transport = mockTransport();
  installGestures(dom.root, transport);

  // One pointer: a pan, reported as the moving focus with the scale unchanged.
  pointer(dom, el, "pointerdown", { id: 1, x: 100, y: 100 });
  pointer(dom, el, "pointermove", { id: 1, x: 140, y: 130 });
  await flush();
  assert.deepEqual(transport.events[0], {
    type: "interaction",
    key: "map",
    payload: { scale: 1, focus_x: 140, focus_y: 130, rotation: 0 },
  });

  // Second pointer down: now it is a pinch, on the same event type.
  pointer(dom, el, "pointerdown", { id: 2, x: 240, y: 130 });
  pointer(dom, el, "pointermove", { id: 2, x: 340, y: 130 });
  await flush();
  const zoom = transport.events[transport.events.length - 1];
  assert.equal(zoom.type, "interaction");
  assert.equal(zoom.payload.scale, 2);
});

test("a cancelled pointer drops out of the pinch without reporting", async () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = surface(dom, "ScaleHandler");
  const transport = mockTransport();
  installGestures(dom.root, transport);

  pointer(dom, el, "pointerdown", { id: 1, x: 0, y: 0 });
  pointer(dom, el, "pointerdown", { id: 2, x: 100, y: 0 });
  pointer(dom, el, "pointercancel", { id: 2, x: 100, y: 0 });
  pointer(dom, el, "pointermove", { id: 1, x: 50, y: 0 });
  await flush();

  assert.deepEqual(transport.events, [], "one pointer left, and this surface has no pan");
});

test("dispose stops the recognizer", async () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = surface(dom, "PanHandler");
  const transport = mockTransport();
  const handle = installGestures(dom.root, transport);
  handle.dispose();

  pointer(dom, el, "pointerdown", { x: 0, y: 0 });
  pointer(dom, el, "pointermove", { x: 50, y: 0 });
  await flush();
  assert.deepEqual(transport.events, []);
});

test("the base sheet claims the pointer for pan and pinch surfaces only", () => {
  assert.match(
    BASE_THEME_CSS,
    /\[data-tw-type="PanHandler"\],\s*\[data-tw-type="ScaleHandler"\],\s*\[data-tw-type="InteractiveViewer"\] \{\s*touch-action: none/,
  );
  // A GestureDetector must keep page scrolling: it wraps rows of real lists.
  assert.ok(
    !/\[data-tw-type="GestureDetector"\][^{]*\{[^}]*touch-action/.test(BASE_THEME_CSS),
    "taking touch-action from a GestureDetector would break scrolling",
  );
});

test("lifting a pointer flushes the gesture's last position", async () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = surface(dom, "ScaleHandler", "photo");
  const transport = mockTransport();
  installGestures(dom.root, transport);

  // A 2x pinch whose last move lands in the same frame as the release. Without
  // the flush the app is left at the previous step: measured in Chrome, a
  // 100px -> 200px pinch settled at 1.5x.
  pointer(dom, el, "pointerdown", { id: 1, x: 100, y: 100 });
  pointer(dom, el, "pointerdown", { id: 2, x: 200, y: 100 });
  pointer(dom, el, "pointermove", { id: 1, x: 50, y: 100 });
  pointer(dom, el, "pointermove", { id: 2, x: 250, y: 100 });
  pointer(dom, el, "pointerup", { id: 2, x: 250, y: 100 });
  await flush();

  const last = transport.events[transport.events.length - 1];
  assert.equal(last.type, "scale");
  assert.equal(last.payload.scale, 2, "the final position is the one the app keeps");
});

test("a coalesced pan reports the latest deltas, not the first", async () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = surface(dom, "PanHandler");
  const transport = mockTransport();
  installGestures(dom.root, transport);

  pointer(dom, el, "pointerdown", { x: 0, y: 0 });
  pointer(dom, el, "pointermove", { x: 5, y: 0 });
  pointer(dom, el, "pointermove", { x: 40, y: 0 });
  await flush();

  assert.equal(transport.events.length, 1);
  assert.equal(transport.events[0].payload.dx, 35, "the step the finger actually just took");
});
