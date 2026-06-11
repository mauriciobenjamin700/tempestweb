// Tests for the pure helpers in client/sw/sw.js — P1/P2/P3 logic.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  chooseStrategy,
  stalecaches,
  buildNotification,
  resolveClickUrl,
  applyBadge,
} from "../../client/sw/sw.js";

const ORIGIN = "https://app.example";
const SHELL = ["/", "/index.html", "/client/tempestweb.js", "/client/dom.js"];

test("chooseStrategy: app-shell is cache-first", () => {
  assert.equal(chooseStrategy(`${ORIGIN}/index.html`, ORIGIN, SHELL), "cache-first");
  assert.equal(chooseStrategy(`${ORIGIN}/client/dom.js`, ORIGIN, SHELL), "cache-first");
  assert.equal(chooseStrategy(`${ORIGIN}/`, ORIGIN, SHELL), "cache-first");
});

test("chooseStrategy: api/ws/sse/webpush are network-first", () => {
  for (const p of ["/api/users", "/ws", "/sse/abc", "/webpush/subscribe"]) {
    assert.equal(chooseStrategy(`${ORIGIN}${p}`, ORIGIN, SHELL), "network-first");
  }
});

test("chooseStrategy: other same-origin is stale-while-revalidate", () => {
  assert.equal(chooseStrategy(`${ORIGIN}/data.json`, ORIGIN, SHELL), "stale-while-revalidate");
});

test("chooseStrategy: cross-origin is network-only", () => {
  assert.equal(chooseStrategy("https://cdn.other/x.js", ORIGIN, SHELL), "network-only");
});

test("stalecaches: keeps current, drops the rest", () => {
  const existing = ["v1-precache", "v1-runtime", "v2-precache", "v2-runtime"];
  const keep = ["v2-precache", "v2-runtime"];
  assert.deepEqual(stalecaches(existing, keep), ["v1-precache", "v1-runtime"]);
});

test("buildNotification: defaults title/icon and copies fields", () => {
  const n = buildNotification({ body: "hi", tag: "t", actions: [{ action: "a", title: "A" }] });
  assert.equal(n.title, "tempestweb");
  assert.equal(n.options.body, "hi");
  assert.equal(n.options.icon, "/icons/icon-192.png");
  assert.equal(n.options.tag, "t");
  assert.deepEqual(n.options.actions, [{ action: "a", title: "A" }]);
});

test("buildNotification: respects payload title and data", () => {
  const n = buildNotification({ title: "Order", body: "shipped", data: { url: "/orders/1" } });
  assert.equal(n.title, "Order");
  assert.deepEqual(n.options.data, { url: "/orders/1" });
});

test("buildNotification: transform can drop a silent push", () => {
  const dropped = buildNotification({ silent: true }, { transform: () => null });
  assert.equal(dropped, null);
  const shaped = buildNotification(
    { n: 1 },
    { transform: (d) => ({ title: `n=${d.n}`, options: {} }) },
  );
  assert.equal(shaped.title, "n=1");
});

test("resolveClickUrl: deep link from data.url", () => {
  assert.equal(resolveClickUrl({ url: "/orders/9" }, null, "/"), "/orders/9");
});

test("resolveClickUrl: action url wins over data.url", () => {
  const data = { url: "/home", actions: { open: "/deep" } };
  assert.equal(resolveClickUrl(data, "open", "/"), "/deep");
});

test("resolveClickUrl: falls back when nothing matches", () => {
  assert.equal(resolveClickUrl({}, null, "/fallback"), "/fallback");
  assert.equal(resolveClickUrl(null, "x", "/fallback"), "/fallback");
});

test("applyBadge: sets a positive count via the Badging API", async () => {
  let set = null;
  let cleared = false;
  const nav = {
    setAppBadge: async (n) => {
      set = n;
    },
    clearAppBadge: async () => {
      cleared = true;
    },
  };
  await applyBadge({ badge_count: 3 }, nav);
  assert.equal(set, 3);
  assert.equal(cleared, false);
});

test("applyBadge: clears the badge on zero/negative", async () => {
  let cleared = false;
  const nav = {
    setAppBadge: async () => {},
    clearAppBadge: async () => {
      cleared = true;
    },
  };
  await applyBadge({ badge_count: 0 }, nav);
  assert.equal(cleared, true);
});

test("applyBadge: reads badge_count nested under data", async () => {
  let set = null;
  await applyBadge({ data: { badge_count: 7 } }, { setAppBadge: async (n) => (set = n) });
  assert.equal(set, 7);
});

test("applyBadge: no-op when no count or unsupported (no throw)", async () => {
  await applyBadge({ title: "hi" }, { setAppBadge: async () => assert.fail("should not set") });
  await applyBadge({ badge_count: 2 }, {}); // unsupported nav: must not throw
});
