// Tests for nfc.scan — the streaming NFC read capability (T-EV).
//
// The Web NFC API is injected as `deps.window`, so these run under node:test
// with no real browser.

import { test } from "node:test";
import assert from "node:assert/strict";

import { CapabilityError } from "../../client/native/index.js";
import { nfcScan } from "../../client/native/nfc.js";

/** A fake NDEFReader whose scan() resolves and whose onreading can be fired. */
class FakeNDEFReader {
  constructor() {
    this.onreading = null;
    this.onreadingerror = null;
    this.aborted = false;
  }
  async scan({ signal }) {
    signal.addEventListener("abort", () => {
      this.aborted = true;
    });
  }
}

class FakeAbortController {
  constructor() {
    const listeners = new Set();
    this.signal = {
      addEventListener: (_type, fn) => listeners.add(fn),
    };
    this._listeners = listeners;
  }
  abort() {
    for (const fn of this._listeners) fn();
  }
}

function fakeData(text) {
  const bytes = [...text].map((c) => c.charCodeAt(0));
  return {
    byteLength: bytes.length,
    getUint8: (i) => bytes[i],
  };
}

test("nfc.scan emits shaped NDEF messages and aborts on teardown", () => {
  const reader = new FakeNDEFReader();
  const deps = {
    window: { NDEFReader: function () { return reader; } },
    AbortController: FakeAbortController,
  };
  const events = [];
  const stop = nfcScan({}, (p) => events.push(p), deps);

  reader.onreading({
    serialNumber: "04:a1",
    message: { records: [{ recordType: "text", mediaType: "", data: fakeData("hi") }] },
  });

  assert.equal(events.length, 1);
  assert.deepEqual(events[0].event.serial_number, "04:a1");
  assert.equal(events[0].event.records[0].record_type, "text");
  assert.equal(events[0].event.records[0].data_base64, "aGk=");

  stop();
  assert.equal(reader.aborted, true);
});

test("nfc.scan surfaces read errors as {error}", () => {
  const reader = new FakeNDEFReader();
  const deps = {
    window: { NDEFReader: function () { return reader; } },
    AbortController: FakeAbortController,
  };
  const events = [];
  nfcScan({}, (p) => events.push(p), deps);

  reader.onreadingerror(new Event("readingerror"));

  assert.equal(events[0].error, "read_error");
});

test("nfc.scan throws unavailable when Web NFC is absent", () => {
  const deps = { window: {}, AbortController: FakeAbortController };
  assert.throws(() => nfcScan({}, () => {}, deps), CapabilityError);
});
