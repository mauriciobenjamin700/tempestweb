// transport-sse.test.js — Mode B SSE + POST client transport (jsdom).
//
// jsdom ships no EventSource, so we inject a FakeEventSource the test drives as
// the server's patch stream, and a fake fetch capturing the client's POSTs. The
// transport must carry the SAME wire shapes as the WebSocket transport.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fixture } from "./setup.js";
import { createSSETransport } from "../../client/transport-sse.js";

/** Minimal EventSource double the test drives as the SSE server. */
class FakeEventSource {
  constructor(url) {
    this.url = url;
    this.closed = false;
    this._listeners = {};
  }
  addEventListener(type, fn) {
    (this._listeners[type] ||= []).push(fn);
  }
  close() {
    this.closed = true;
  }
  /** Test helper: deliver one server->client envelope as a `message` event. */
  serverSend(envelope) {
    for (const fn of this._listeners.message || [])
      fn({ data: JSON.stringify(envelope) });
  }
  /** Test helper: deliver a named `ping` heartbeat event. */
  ping() {
    for (const fn of this._listeners.ping || []) fn({ data: "{}" });
  }
  /** Test helper: the stream opened (the server now holds the session). */
  open() {
    for (const fn of this._listeners.open || []) fn({});
  }
  /** Test helper: the stream dropped; the browser will reconnect. */
  fail() {
    for (const fn of this._listeners.error || []) fn({});
  }
}

/** A fetch double that records every POST body. */
function makeFetch(record) {
  return async (url, init) => {
    record.push({ url, body: JSON.parse(init.body) });
    return { ok: true, status: 204 };
  };
}

test("sse transport delivers patch batches to onPatches", () => {
  let source;
  const Impl = class extends FakeEventSource {
    constructor(url) {
      super(url);
      source = this;
    }
  };
  const transport = createSSETransport({
    session: "s1",
    EventSourceImpl: Impl,
    fetchImpl: makeFetch([]),
  });
  assert.equal(source.url, "/sse?session=s1");

  const batches = [];
  transport.onPatches((p) => batches.push(p));
  source.serverSend({ kind: "patches", data: fixture("patches_count_0_to_1.json") });

  assert.equal(batches.length, 1);
  assert.equal(batches[0][0].set_props.content, "Count: 1");
});

test("sse transport ignores ping heartbeats", () => {
  let source;
  const Impl = class extends FakeEventSource {
    constructor(url) {
      super(url);
      source = this;
    }
  };
  const transport = createSSETransport({
    session: "s1",
    EventSourceImpl: Impl,
    fetchImpl: makeFetch([]),
  });
  const batches = [];
  transport.onPatches((p) => batches.push(p));
  source.ping(); // must not throw or deliver a batch
  assert.equal(batches.length, 0);
});

test("sse transport routes a navigate envelope to onNavigate", () => {
  let source;
  const Impl = class extends FakeEventSource {
    constructor(url) {
      super(url);
      source = this;
    }
  };
  const transport = createSSETransport({
    session: "s1",
    EventSourceImpl: Impl,
    fetchImpl: makeFetch([]),
  });

  const paths = [];
  transport.onNavigate((p) => paths.push(p));
  source.serverSend({ kind: "navigate", path: "/about" });

  assert.deepEqual(paths, ["/about"]);
});

test("sse transport POSTs events to the per-session url", async () => {
  const posts = [];
  let source;
  const Impl = class extends FakeEventSource {
    constructor(url) {
      super(url);
      source = this;
    }
  };
  const transport = createSSETransport({
    session: "abc",
    EventSourceImpl: Impl,
    fetchImpl: makeFetch(posts),
  });
  source.open();

  transport.sendEvent({ type: "click", key: "inc", payload: {} });
  await new Promise((r) => setTimeout(r, 0));

  assert.equal(posts.length, 1);
  assert.equal(posts[0].url, "/sse/abc");
  assert.deepEqual(posts[0].body, {
    kind: "event",
    data: { type: "click", key: "inc", payload: {} },
  });
});

// Regression: the server only registers the session while handling the GET /sse
// that opens the stream, so an event POSTed first — the router's initial
// `navigate` — was answered 404 and silently lost.
test("sse transport buffers events raised before the stream opens", async () => {
  const posts = [];
  let source;
  const Impl = class extends FakeEventSource {
    constructor(url) {
      super(url);
      source = this;
    }
  };
  const transport = createSSETransport({
    session: "abc",
    EventSourceImpl: Impl,
    fetchImpl: makeFetch(posts),
  });

  transport.sendEvent({ type: "navigate", key: "", payload: { path: "/" } });
  await new Promise((r) => setTimeout(r, 0));
  assert.equal(posts.length, 0, "nothing may be POSTed before the stream opens");

  source.open();
  await new Promise((r) => setTimeout(r, 0));

  assert.equal(posts.length, 1);
  assert.deepEqual(posts[0].body, {
    kind: "event",
    data: { type: "navigate", key: "", payload: { path: "/" } },
  });
});

test("sse transport re-buffers events while the stream is down", async () => {
  const posts = [];
  let source;
  const Impl = class extends FakeEventSource {
    constructor(url) {
      super(url);
      source = this;
    }
  };
  const transport = createSSETransport({
    session: "abc",
    EventSourceImpl: Impl,
    fetchImpl: makeFetch(posts),
  });
  source.open();
  source.fail();

  transport.sendEvent({ type: "click", key: "inc", payload: {} });
  await new Promise((r) => setTimeout(r, 0));
  assert.equal(posts.length, 0);

  source.open();
  await new Promise((r) => setTimeout(r, 0));
  assert.equal(posts.length, 1);
  assert.equal(posts[0].body.data.key, "inc");
});

test("sse transport warns when a POST is rejected", async () => {
  const warnings = [];
  const realWarn = console.warn;
  console.warn = (...args) => warnings.push(args);
  let source;
  const Impl = class extends FakeEventSource {
    constructor(url) {
      super(url);
      source = this;
    }
  };
  const transport = createSSETransport({
    session: "abc",
    EventSourceImpl: Impl,
    fetchImpl: async () => ({ ok: false, status: 404 }),
  });
  source.open();

  try {
    transport.sendEvent({ type: "click", key: "inc", payload: {} });
    await new Promise((r) => setTimeout(r, 0));
  } finally {
    console.warn = realWarn;
  }

  assert.equal(warnings.length, 1);
  assert.match(warnings[0][0], /rejected \(404\)/);
});

test("sse transport POSTs native_result for a native_call", async () => {
  const posts = [];
  let source;
  const Impl = class extends FakeEventSource {
    constructor(url) {
      super(url);
      source = this;
    }
  };
  const transport = createSSETransport({
    session: "abc",
    EventSourceImpl: Impl,
    fetchImpl: makeFetch(posts),
    onNativeCall: async () => ({ ok: 1 }),
  });

  source.serverSend({ kind: "native_call", call_id: "c9", capability: "clipboard.read" });
  await new Promise((r) => setTimeout(r, 0));

  assert.equal(posts[0].url, "/sse/abc");
  assert.deepEqual(posts[0].body, {
    kind: "native_result",
    call_id: "c9",
    ok: true,
    value: { ok: 1 },
  });
});

test("sse transport runs a native_call through the built-in bridge", async () => {
  const posts = [];
  let source;
  const Impl = class extends FakeEventSource {
    constructor(url) {
      super(url);
      source = this;
    }
  };
  createSSETransport({
    session: "abc",
    EventSourceImpl: Impl,
    fetchImpl: makeFetch(posts),
  });

  source.serverSend({
    kind: "native_call",
    call_id: "c10",
    capability: "network.state",
    args: {},
  });
  await new Promise((r) => setTimeout(r, 0));

  assert.equal(posts[0].body.kind, "native_result");
  assert.equal(posts[0].body.call_id, "c10");
  assert.equal(posts[0].body.ok, true);
  assert.equal(typeof posts[0].body.value.online, "boolean");
});
