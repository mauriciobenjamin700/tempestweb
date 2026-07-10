// Tests for client/transpile/nav.js — Route/NavStack + routesFromPath parity.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fixture } from "./setup.js";
import { NavStack, Route, routesFromPath } from "../../client/transpile/nav.js";

test("routesFromPath matches the core for every fixture path", () => {
  for (const { path, names } of fixture("transpile_route_cases.json")) {
    assert.deepEqual(routesFromPath(path).map((r) => r.name), names, path);
  }
});

test("Route mirrors the core: name + params only", () => {
  const r = new Route({ name: "/about", params: { id: "1" } });
  assert.equal(r.name, "/about");
  assert.deepEqual(r.params, { id: "1" });
  assert.deepEqual(new Route({ name: "/x" }).params, {});
});

test("NavStack.top is the last route; defaults to root", () => {
  assert.equal(new NavStack().top.name, "/");
  const stack = [new Route({ name: "/" }), new Route({ name: "/a" })];
  assert.equal(new NavStack({ stack }).top.name, "/a");
});
