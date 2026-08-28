// Tests for the compact (`.tmc`) model fetch capability.
//
// The capability moves bytes and nothing else — the reader is Python — so what
// these check is the part that can go wrong silently: that the bytes arrive
// intact as base64, that the shared asset cache is used when it is there, and
// that a runtime without Cache Storage still gets its model instead of an error.

import { test } from "node:test";
import assert from "node:assert/strict";

import { dispatch } from "../../client/native/index.js";

/** Build a native_call envelope. */
function call(capability, args = {}, callId = "c1") {
  return { kind: "native_call", call_id: callId, capability, args };
}

/** The bytes a tiny compact file would carry: the magic, then a payload. */
function modelBytes() {
  const bytes = new Uint8Array(16);
  bytes.set([0x54, 0x4d, 0x43, 0x31], 0);
  for (let i = 4; i < bytes.length; i += 1) bytes[i] = i * 7;
  return bytes;
}

/** A Response-alike carrying those bytes. */
function response(bytes, ok = true) {
  return {
    ok,
    status: ok ? 200 : 404,
    async arrayBuffer() {
      return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
    },
    clone() {
      return response(bytes, ok);
    },
  };
}

/** A Cache Storage double that records what it was asked to store. */
function fakeCaches(stored = null) {
  const puts = [];
  return {
    puts,
    async open() {
      return {
        async match() {
          return stored;
        },
        async put(request, value) {
          puts.push({ request, value });
        },
      };
    },
  };
}

test("compact.load: hands the model over as base64", async () => {
  const bytes = modelBytes();
  const res = await dispatch(call("compact.load", { model_url: "/models/risk.tmc" }), {
    caches: fakeCaches(),
    fetch: async () => response(bytes),
  });

  assert.equal(res.ok, true);
  assert.deepEqual(
    Array.from(Buffer.from(res.value.data_base64, "base64")),
    Array.from(bytes),
  );
});

test("compact.load: names its payload data_base64, like every binary payload here", async () => {
  const res = await dispatch(call("compact.load", { model_url: "/models/risk.tmc" }), {
    caches: fakeCaches(),
    fetch: async () => response(modelBytes()),
  });

  assert.deepEqual(Object.keys(res.value), ["data_base64"]);
});

test("compact.load: serves a cached model without fetching again", async () => {
  const bytes = modelBytes();
  let fetched = 0;
  const res = await dispatch(call("compact.load", { model_url: "/models/risk.tmc" }), {
    caches: fakeCaches(response(bytes)),
    fetch: async () => {
      fetched += 1;
      return response(bytes);
    },
  });

  assert.equal(res.ok, true);
  assert.equal(fetched, 0);
  assert.equal(Buffer.from(res.value.data_base64, "base64").length, bytes.length);
});

test("compact.load: a runtime with no Cache Storage still gets the model", async () => {
  const bytes = modelBytes();
  const res = await dispatch(call("compact.load", { model_url: "/models/risk.tmc" }), {
    caches: undefined,
    fetch: async () => response(bytes),
  });

  assert.equal(res.ok, true);
  assert.equal(Buffer.from(res.value.data_base64, "base64").length, bytes.length);
});

test("compact.load: a failed download reports model_load, not a blank model", async () => {
  const res = await dispatch(call("compact.load", { model_url: "/models/gone.tmc" }), {
    caches: fakeCaches(),
    fetch: async () => response(modelBytes(), false),
  });

  assert.equal(res.ok, false);
  assert.equal(res.error, "model_load");
  assert.match(res.message, /gone\.tmc/);
});

test("compact.load: no model_url is an error, not an empty fetch", async () => {
  const res = await dispatch(call("compact.load", {}), {
    fetch: async () => response(modelBytes()),
  });

  assert.equal(res.ok, false);
  assert.equal(res.error, "model_load");
});
