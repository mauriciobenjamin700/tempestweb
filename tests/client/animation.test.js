// Tests for client/transpile/animation.js — controller, curves, Tween, spring.
import { test } from "node:test";
import assert from "node:assert/strict";
import { AnimationController, Spring, Tween, applyCurve } from "../../client/transpile/animation.js";
import { Curve } from "../../client/transpile/motion.js";

test("applyCurve mirrors the core easing math", () => {
  assert.equal(applyCurve(Curve.LINEAR, 0.5), 0.5);
  assert.equal(applyCurve(Curve.EASE_IN, 0.5), 0.25);
  assert.equal(applyCurve(Curve.EASE_OUT, 0.5), 0.75);
  assert.equal(applyCurve(Curve.EASE_IN_OUT, 0.0), 0.0);
  assert.equal(applyCurve(Curve.EASE_IN_OUT, 1.0), 1.0);
  assert.ok(applyCurve(Curve.BOUNCE, 1.0) > 0.99);
});

test("AnimationController ramps 0->1 over its duration and settles", () => {
  const c = new AnimationController(1.0, { curve: Curve.LINEAR });
  assert.equal(c.value, 0);
  c.forward();
  assert.equal(c._advance(0.5), false); // mid-ramp
  assert.ok(c.value > 0.4 && c.value < 0.6);
  assert.equal(c._advance(0.6), true); // past 1.0 -> settled
  assert.equal(c.value, 1.0);
  assert.equal(c.has_animations ?? undefined, undefined); // no such prop on ctrl
});

test("reverse walks back toward 0", () => {
  const c = new AnimationController(1.0, { curve: Curve.LINEAR });
  c.value = 1.0;
  c.reverse();
  c._advance(0.25);
  assert.ok(c.value > 0.7 && c.value < 0.8);
});

test("Tween interpolates float, Color and Edge", () => {
  assert.equal(new Tween({ begin: 100, end: 300 }).at(0.5), 200);
  const col = new Tween({ begin: { r: 0, g: 0, b: 0, a: 1 }, end: { r: 100, g: 200, b: 50, a: 1 } }).at(0.5);
  assert.deepEqual(col, { r: 50, g: 100, b: 25, a: 1 });
  const edge = new Tween({ begin: { top: 0, right: 0, bottom: 0, left: 0 }, end: { top: 10, right: 10, bottom: 10, left: 10 } }).at(0.5);
  assert.equal(edge.top, 5);
});

test("a spring integrates toward its target and settles", () => {
  const c = new AnimationController(0, { spring: new Spring({}) });
  c.forward();
  let done = false;
  for (let i = 0; i < 2000 && !done; i += 1) done = c._advance(1 / 60);
  assert.equal(done, true);
  assert.equal(c.value, 1.0);
});
