// Tests for the pure helpers in client/sw/sw.js — P1/P2/P3 logic.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  chooseStrategy,
  stalecaches,
  isCacheable,
  trimCache,
  buildNotification,
  resolveClickUrl,
  applyBadge,
  installPushHandler,
  installNotificationClickHandler,
} from "../../client/sw/sw.js";

/** Build a Response-like object for isCacheable tests (no real fetch). */
function resp({ ok = true, type = "basic", cacheControl = null } = {}) {
  return {
    ok,
    type,
    headers: { get: (h) => (h.toLowerCase() === "cache-control" ? cacheControl : null) },
  };
}

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

test("isCacheable: accepts a successful same-origin response", () => {
  assert.equal(isCacheable(resp({ ok: true, type: "basic" })), true);
  assert.equal(isCacheable(resp({ ok: true, type: "default" })), true);
});

test("isCacheable: rejects error, opaque and no-store responses", () => {
  assert.equal(isCacheable(resp({ ok: false, type: "basic" })), false, "4xx/5xx");
  assert.equal(isCacheable(resp({ ok: true, type: "opaque" })), false, "opaque");
  assert.equal(isCacheable(resp({ ok: true, cacheControl: "no-store" })), false);
  assert.equal(isCacheable(resp({ ok: true, cacheControl: "private, no-store" })), false);
  assert.equal(isCacheable(null), false);
});

test("isCacheable: a plain cache-control still caches", () => {
  assert.equal(isCacheable(resp({ ok: true, cacheControl: "max-age=3600" })), true);
});

test("trimCache: evicts the oldest entries beyond the cap (FIFO)", async () => {
  let keys = ["/a", "/b", "/c", "/d", "/e"];
  const cache = {
    keys: async () => keys.slice(),
    delete: async (k) => {
      keys = keys.filter((x) => x !== k);
    },
  };
  const evicted = await trimCache(cache, 3);
  assert.equal(evicted, 2);
  assert.deepEqual(keys, ["/c", "/d", "/e"], "oldest two removed");
});

test("trimCache: no-op when within the cap", async () => {
  const cache = {
    keys: async () => ["/a", "/b"],
    delete: async () => assert.fail("should not delete"),
  };
  assert.equal(await trimCache(cache, 5), 0);
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

// --- installPushHandler / installNotificationClickHandler (P3) ------------

test("installPushHandler: shows the notification and applies the badge", async () => {
  let shown = null;
  let badge = null;
  const registration = {
    showNotification: async (title, options) => {
      shown = { title, options };
    },
  };
  const navigator = { setAppBadge: async (n) => (badge = n) };
  const onPush = installPushHandler({ registration, navigator });
  const event = {
    data: { json: () => ({ title: "Hi", body: "yo", badge_count: 2 }) },
  };
  await onPush(event);
  assert.equal(shown.title, "Hi");
  assert.equal(shown.options.body, "yo");
  assert.equal(badge, 2);
});

test("installPushHandler: a transform returning null suppresses the notification", async () => {
  let shown = false;
  const registration = { showNotification: async () => (shown = true) };
  const onPush = installPushHandler({ registration, transform: () => null });
  await onPush({ data: { json: () => ({ silent: true }) } });
  assert.equal(shown, false);
});

test("installPushHandler: malformed payload falls back to text body (no throw)", async () => {
  let shown = null;
  const registration = {
    showNotification: async (title, options) => (shown = { title, options }),
  };
  const onPush = installPushHandler({ registration });
  const event = {
    data: {
      json: () => {
        throw new Error("bad json");
      },
      text: () => "plain",
    },
  };
  await onPush(event);
  assert.equal(shown.options.body, "plain");
});

test("installNotificationClickHandler: closes and routes to the deep link", async () => {
  let closed = false;
  let opened = null;
  const onClick = installNotificationClickHandler({
    focusOrOpen: async (url) => (opened = url),
  });
  const event = {
    action: null,
    notification: { data: { url: "/orders/9" }, close: () => (closed = true) },
  };
  await onClick(event);
  assert.equal(closed, true);
  assert.equal(opened, "/orders/9");
});

test("installNotificationClickHandler: action url wins, falls back otherwise", async () => {
  let opened = null;
  const open = async (url) => (opened = url);
  const onClick = installNotificationClickHandler({ focusOrOpen: open, fallbackUrl: "/home" });
  await onClick({
    action: "open",
    notification: { data: { url: "/x", actions: { open: "/deep" } }, close: () => {} },
  });
  assert.equal(opened, "/deep");
  await onClick({ action: null, notification: { data: {}, close: () => {} } });
  assert.equal(opened, "/home");
});
