// Tests for the Tier-3 native capabilities added to client/native/*.
//
// Web APIs are injected as `deps` (fake navigator/window/document/AudioContext),
// so these run under node:test with no real browser. Each capability is exercised
// for its success shape, its is_supported true/false paths (where present), and
// the CapabilityError code it raises when the API is absent, the id is unknown, or
// the picker is cancelled.

import { test } from "node:test";
import assert from "node:assert/strict";

import { dispatch } from "../../client/native/index.js";

/** Build a native_call envelope. */
function call(capability, args = {}, callId = "c1") {
  return { kind: "native_call", call_id: callId, capability, args };
}

/** An AbortError, as a picker throws on user-dismiss. */
function abortError() {
  const err = new Error("dismissed");
  err.name = "AbortError";
  return err;
}

// --- bluetooth -------------------------------------------------------------

test("bluetooth.is_supported: reflects navigator.bluetooth", async () => {
  const yes = await dispatch(call("bluetooth.is_supported"), { navigator: { bluetooth: {} } });
  assert.deepEqual(yes.value, { supported: true });
  const no = await dispatch(call("bluetooth.is_supported"), { navigator: {} });
  assert.deepEqual(no.value, { supported: false });
});

test("bluetooth.request then read/write round-trips through the registry", async () => {
  const written = [];
  const characteristic = {
    readValue: async () => new DataView(Uint8Array.from([65, 66, 67]).buffer),
    writeValue: async (bytes) => written.push(bytes),
  };
  const service = { getCharacteristic: async () => characteristic };
  const server = { getPrimaryService: async () => service };
  let acceptAll;
  const navigator = {
    bluetooth: {
      requestDevice: async (opts) => {
        acceptAll = opts.acceptAllDevices;
        return { name: "Sensor", gatt: { connect: async () => server } };
      },
    },
  };
  const deps = { navigator };

  const req = await dispatch(call("bluetooth.request", { filters: [], optional_services: ["s"] }), deps);
  assert.equal(req.ok, true);
  assert.equal(acceptAll, true);
  assert.equal(req.value.name, "Sensor");
  const id = req.value.id;

  const read = await dispatch(call("bluetooth.read", { id, service: "s", characteristic: "c" }), deps);
  assert.equal(read.ok, true);
  assert.equal(read.value.data_base64, "QUJD");

  const write = await dispatch(
    call("bluetooth.write", { id, service: "s", characteristic: "c", data_base64: "QUJD" }),
    deps,
  );
  assert.equal(write.ok, true);
  assert.deepEqual(write.value, {});
  assert.equal(written.length, 1);
});

test("bluetooth.request: uses filters when provided", async () => {
  let seen;
  const navigator = {
    bluetooth: {
      requestDevice: async (opts) => {
        seen = opts;
        return { name: "", gatt: { connect: async () => ({}) } };
      },
    },
  };
  await dispatch(call("bluetooth.request", { filters: [{ name: "X" }], optional_services: [] }), { navigator });
  assert.deepEqual(seen.filters, [{ name: "X" }]);
  assert.equal(seen.acceptAllDevices, undefined);
});

test("bluetooth.request: unavailable when the API is missing", async () => {
  const res = await dispatch(call("bluetooth.request", {}), { navigator: {} });
  assert.equal(res.error, "unavailable");
});

test("bluetooth.request: cancelled on AbortError", async () => {
  const navigator = { bluetooth: { requestDevice: async () => { throw abortError(); } } };
  const res = await dispatch(call("bluetooth.request", {}), { navigator });
  assert.equal(res.error, "cancelled");
});

test("bluetooth.read: not_found for an unknown id", async () => {
  const res = await dispatch(call("bluetooth.read", { id: 9999, service: "s", characteristic: "c" }), {});
  assert.equal(res.error, "not_found");
});

test("bluetooth.write: not_found for an unknown id", async () => {
  const res = await dispatch(
    call("bluetooth.write", { id: 9999, service: "s", characteristic: "c", data_base64: "QUJD" }),
    {},
  );
  assert.equal(res.error, "not_found");
});

// --- contacts --------------------------------------------------------------

test("contacts.is_supported: reflects navigator.contacts", async () => {
  const yes = await dispatch(call("contacts.is_supported"), { navigator: { contacts: {} } });
  assert.deepEqual(yes.value, { supported: true });
  const no = await dispatch(call("contacts.is_supported"), { navigator: {} });
  assert.deepEqual(no.value, { supported: false });
});

test("contacts.select: returns the picked contacts", async () => {
  let seen;
  const navigator = {
    contacts: {
      select: async (props, opts) => {
        seen = { props, opts };
        return [{ name: ["Ada"] }];
      },
    },
  };
  const res = await dispatch(call("contacts.select", { properties: ["name"], multiple: true }), { navigator });
  assert.equal(res.ok, true);
  assert.deepEqual(res.value, { contacts: [{ name: ["Ada"] }] });
  assert.deepEqual(seen.props, ["name"]);
  assert.deepEqual(seen.opts, { multiple: true });
});

test("contacts.select: unavailable when the API is missing", async () => {
  const res = await dispatch(call("contacts.select", { properties: [] }), { navigator: {} });
  assert.equal(res.error, "unavailable");
});

test("contacts.select: cancelled on AbortError", async () => {
  const navigator = { contacts: { select: async () => { throw abortError(); } } };
  const res = await dispatch(call("contacts.select", { properties: [] }), { navigator });
  assert.equal(res.error, "cancelled");
});

// --- eyedropper ------------------------------------------------------------

test("eyedropper.open: returns the picked sRGB hex", async () => {
  class EyeDropper {
    open() {
      return Promise.resolve({ sRGBHex: "#ff0000" });
    }
  }
  const res = await dispatch(call("eyedropper.open"), { window: { EyeDropper } });
  assert.equal(res.ok, true);
  assert.deepEqual(res.value, { srgb_hex: "#ff0000" });
});

test("eyedropper.open: unavailable when the API is missing", async () => {
  const res = await dispatch(call("eyedropper.open"), { window: {} });
  assert.equal(res.error, "unavailable");
});

test("eyedropper.open: cancelled on AbortError", async () => {
  class EyeDropper {
    open() {
      return Promise.reject(abortError());
    }
  }
  const res = await dispatch(call("eyedropper.open"), { window: { EyeDropper } });
  assert.equal(res.error, "cancelled");
});

// --- gamepad ---------------------------------------------------------------

test("gamepad.state: serializes pads, dropping empty slots", async () => {
  const pad = {
    index: 0,
    id: "Pad",
    buttons: [{ pressed: true, value: 1 }, { pressed: false, value: 0 }],
    axes: [0.5, -0.5],
  };
  const navigator = { getGamepads: () => [pad, null] };
  const res = await dispatch(call("gamepad.state"), { navigator });
  assert.equal(res.ok, true);
  assert.deepEqual(res.value, {
    gamepads: [
      {
        index: 0,
        id: "Pad",
        buttons: [{ pressed: true, value: 1 }, { pressed: false, value: 0 }],
        axes: [0.5, -0.5],
      },
    ],
  });
});

test("gamepad.state: unavailable when getGamepads is missing", async () => {
  const res = await dispatch(call("gamepad.state"), { navigator: {} });
  assert.equal(res.error, "unavailable");
});

// --- hid -------------------------------------------------------------------

test("hid.is_supported: reflects navigator.hid", async () => {
  const yes = await dispatch(call("hid.is_supported"), { navigator: { hid: {} } });
  assert.deepEqual(yes.value, { supported: true });
  const no = await dispatch(call("hid.is_supported"), { navigator: {} });
  assert.deepEqual(no.value, { supported: false });
});

test("hid.request: maps the granted devices", async () => {
  const navigator = {
    hid: {
      requestDevice: async () => [{ productName: "Keeb", vendorId: 1, productId: 2 }],
    },
  };
  const res = await dispatch(call("hid.request", { filters: [] }), { navigator });
  assert.equal(res.ok, true);
  assert.deepEqual(res.value, {
    devices: [{ product_name: "Keeb", vendor_id: 1, product_id: 2 }],
  });
});

test("hid.request: unavailable when the API is missing", async () => {
  const res = await dispatch(call("hid.request", {}), { navigator: {} });
  assert.equal(res.error, "unavailable");
});

test("hid.request: cancelled on AbortError", async () => {
  const navigator = { hid: { requestDevice: async () => { throw abortError(); } } };
  const res = await dispatch(call("hid.request", {}), { navigator });
  assert.equal(res.error, "cancelled");
});

// --- midi ------------------------------------------------------------------

test("midi.is_supported: reflects navigator.requestMIDIAccess", async () => {
  const yes = await dispatch(call("midi.is_supported"), { navigator: { requestMIDIAccess: () => {} } });
  assert.deepEqual(yes.value, { supported: true });
  const no = await dispatch(call("midi.is_supported"), { navigator: {} });
  assert.deepEqual(no.value, { supported: false });
});

test("midi.request_access then send round-trips through the access object", async () => {
  const sent = [];
  const outputPort = { id: "out-1", name: "Synth", send: (data) => sent.push(data) };
  const access = {
    inputs: new Map([["in-1", { id: "in-1", name: "Pad" }]]),
    outputs: new Map([["out-1", outputPort]]),
  };
  let sysexSeen;
  const navigator = {
    requestMIDIAccess: async (opts) => {
      sysexSeen = opts.sysex;
      return access;
    },
  };
  const deps = { navigator };

  const req = await dispatch(call("midi.request_access", { sysex: true }), deps);
  assert.equal(req.ok, true);
  assert.equal(sysexSeen, true);
  assert.deepEqual(req.value.inputs, [{ id: "in-1", name: "Pad" }]);
  assert.deepEqual(req.value.outputs, [{ id: "out-1", name: "Synth" }]);

  const send = await dispatch(call("midi.send", { output_id: "out-1", data: [144, 60, 127] }), deps);
  assert.equal(send.ok, true);
  assert.deepEqual(sent, [[144, 60, 127]]);
});

test("midi.request_access: unavailable when the API is missing", async () => {
  const res = await dispatch(call("midi.request_access", {}), { navigator: {} });
  assert.equal(res.error, "unavailable");
});

test("midi.send: not_found for an unknown output id", async () => {
  const access = { inputs: new Map(), outputs: new Map() };
  const navigator = { requestMIDIAccess: async () => access };
  await dispatch(call("midi.request_access", {}), { navigator });
  const res = await dispatch(call("midi.send", { output_id: "nope", data: [] }), {});
  assert.equal(res.error, "not_found");
});

// --- nfc -------------------------------------------------------------------

test("nfc.is_supported: reflects NDEFReader on window", async () => {
  const yes = await dispatch(call("nfc.is_supported"), { window: { NDEFReader: function () {} } });
  assert.deepEqual(yes.value, { supported: true });
  const no = await dispatch(call("nfc.is_supported"), { window: {} });
  assert.deepEqual(no.value, { supported: false });
});

test("nfc.write: writes the NDEF records", async () => {
  let written;
  class NDEFReader {
    write(msg) {
      written = msg;
      return Promise.resolve();
    }
  }
  const res = await dispatch(call("nfc.write", { records: [{ recordType: "text", data: "hi" }] }), {
    window: { NDEFReader },
  });
  assert.equal(res.ok, true);
  assert.deepEqual(written, { records: [{ recordType: "text", data: "hi" }] });
});

test("nfc.write: unavailable when the API is missing", async () => {
  const res = await dispatch(call("nfc.write", { records: [] }), { window: {} });
  assert.equal(res.error, "unavailable");
});

test("nfc.write: cancelled on AbortError", async () => {
  class NDEFReader {
    write() {
      return Promise.reject(abortError());
    }
  }
  const res = await dispatch(call("nfc.write", { records: [] }), { window: { NDEFReader } });
  assert.equal(res.error, "cancelled");
});

// --- payment ---------------------------------------------------------------

test("payment.is_supported: reflects window.PaymentRequest", async () => {
  const yes = await dispatch(call("payment.is_supported"), { window: { PaymentRequest: function () {} } });
  assert.deepEqual(yes.value, { supported: true });
  const no = await dispatch(call("payment.is_supported"), { window: {} });
  assert.deepEqual(no.value, { supported: false });
});

test("payment.request: shows the sheet and serializes the response", async () => {
  let completed;
  class PaymentRequest {
    constructor(methods, details, options) {
      this.methods = methods;
      this.details = details;
      this.options = options;
    }
    show() {
      return Promise.resolve({
        methodName: "basic-card",
        details: { token: "tok" },
        payerName: "Ada",
        payerEmail: "ada@x.dev",
        shippingAddress: null,
        complete: (status) => {
          completed = status;
          return Promise.resolve();
        },
      });
    }
  }
  const res = await dispatch(
    call("payment.request", { methods: [{ supportedMethods: "basic-card" }], details: { total: {} } }),
    { window: { PaymentRequest } },
  );
  assert.equal(res.ok, true);
  assert.equal(completed, "success");
  assert.deepEqual(res.value.response, {
    method_name: "basic-card",
    details: { token: "tok" },
    payer_name: "Ada",
    payer_email: "ada@x.dev",
    shipping_address: null,
  });
});

test("payment.request: unavailable when the API is missing", async () => {
  const res = await dispatch(call("payment.request", { methods: [], details: {} }), { window: {} });
  assert.equal(res.error, "unavailable");
});

test("payment.request: cancelled on AbortError", async () => {
  class PaymentRequest {
    show() {
      return Promise.reject(abortError());
    }
  }
  const res = await dispatch(call("payment.request", { methods: [], details: {} }), {
    window: { PaymentRequest },
  });
  assert.equal(res.error, "cancelled");
});

// --- pip -------------------------------------------------------------------

test("pip.request: enters PiP on the matched video", async () => {
  let entered = false;
  const video = { requestPictureInPicture: async () => (entered = true) };
  const document = { querySelector: (sel) => (sel === "video" ? video : null) };
  const res = await dispatch(call("pip.request", { selector: "video" }), { document });
  assert.equal(res.ok, true);
  assert.deepEqual(res.value, { active: true });
  assert.equal(entered, true);
});

test("pip.request: not_found when no video matches", async () => {
  const document = { querySelector: () => null };
  const res = await dispatch(call("pip.request", { selector: "#missing" }), { document });
  assert.equal(res.error, "not_found");
});

test("pip.request: unavailable when the API is missing", async () => {
  const video = {};
  const document = { querySelector: () => video };
  const res = await dispatch(call("pip.request", {}), { document });
  assert.equal(res.error, "unavailable");
});

test("pip.exit: exits PiP", async () => {
  let exited = false;
  const document = { exitPictureInPicture: async () => (exited = true) };
  const res = await dispatch(call("pip.exit"), { document });
  assert.equal(res.ok, true);
  assert.deepEqual(res.value, { active: false });
  assert.equal(exited, true);
});

test("pip.exit: unavailable when the API is missing", async () => {
  const res = await dispatch(call("pip.exit"), { document: {} });
  assert.equal(res.error, "unavailable");
});

// --- pointerlock -----------------------------------------------------------

test("pointerlock.request: locks the selected element", async () => {
  let locked = false;
  const el = { requestPointerLock: () => (locked = true) };
  const document = { querySelector: () => el };
  const res = await dispatch(call("pointerlock.request", { selector: "#stage" }), { document });
  assert.equal(res.ok, true);
  assert.equal(locked, true);
});

test("pointerlock.request: falls back to documentElement without a selector", async () => {
  let locked = false;
  const docEl = { requestPointerLock: () => (locked = true) };
  const document = { documentElement: docEl, querySelector: () => null };
  const res = await dispatch(call("pointerlock.request", { selector: null }), { document });
  assert.equal(res.ok, true);
  assert.equal(locked, true);
});

test("pointerlock.request: not_found when the selector matches nothing", async () => {
  const document = { querySelector: () => null };
  const res = await dispatch(call("pointerlock.request", { selector: "#gone" }), { document });
  assert.equal(res.error, "not_found");
});

test("pointerlock.request: unavailable when the API is missing", async () => {
  const document = { querySelector: () => ({}) };
  const res = await dispatch(call("pointerlock.request", { selector: "#x" }), { document });
  assert.equal(res.error, "unavailable");
});

test("pointerlock.exit: exits the lock", async () => {
  let exited = false;
  const document = { exitPointerLock: () => (exited = true) };
  const res = await dispatch(call("pointerlock.exit"), { document });
  assert.equal(res.ok, true);
  assert.equal(exited, true);
});

test("pointerlock.exit: unavailable when the API is missing", async () => {
  const res = await dispatch(call("pointerlock.exit"), { document: {} });
  assert.equal(res.error, "unavailable");
});

// --- serial ----------------------------------------------------------------

test("serial.is_supported: reflects navigator.serial", async () => {
  const yes = await dispatch(call("serial.is_supported"), { navigator: { serial: {} } });
  assert.deepEqual(yes.value, { supported: true });
  const no = await dispatch(call("serial.is_supported"), { navigator: {} });
  assert.deepEqual(no.value, { supported: false });
});

test("serial.request: registers a port and returns its id", async () => {
  const navigator = { serial: { requestPort: async () => ({ open: async () => {} }) } };
  const res = await dispatch(call("serial.request", { filters: [] }), { navigator });
  assert.equal(res.ok, true);
  assert.equal(typeof res.value.id, "number");
});

test("serial.request: passes filters when provided", async () => {
  let seen;
  const navigator = {
    serial: {
      requestPort: async (opts) => {
        seen = opts;
        return {};
      },
    },
  };
  await dispatch(call("serial.request", { filters: [{ usbVendorId: 1 }] }), { navigator });
  assert.deepEqual(seen, { filters: [{ usbVendorId: 1 }] });
});

test("serial.request: unavailable when the API is missing", async () => {
  const res = await dispatch(call("serial.request", {}), { navigator: {} });
  assert.equal(res.error, "unavailable");
});

test("serial.request: cancelled on AbortError", async () => {
  const navigator = { serial: { requestPort: async () => { throw abortError(); } } };
  const res = await dispatch(call("serial.request", {}), { navigator });
  assert.equal(res.error, "cancelled");
});

// --- usb -------------------------------------------------------------------

test("usb.is_supported: reflects navigator.usb", async () => {
  const yes = await dispatch(call("usb.is_supported"), { navigator: { usb: {} } });
  assert.deepEqual(yes.value, { supported: true });
  const no = await dispatch(call("usb.is_supported"), { navigator: {} });
  assert.deepEqual(no.value, { supported: false });
});

test("usb.request: registers a device and returns its fields", async () => {
  const navigator = {
    usb: {
      requestDevice: async () => ({ vendorId: 4617, productId: 21827, productName: "DevBoard" }),
    },
  };
  const res = await dispatch(call("usb.request", { filters: [] }), { navigator });
  assert.equal(res.ok, true);
  assert.equal(typeof res.value.id, "number");
  assert.equal(res.value.vendor_id, 4617);
  assert.equal(res.value.product_id, 21827);
  assert.equal(res.value.product_name, "DevBoard");
});

test("usb.request: unavailable when the API is missing", async () => {
  const res = await dispatch(call("usb.request", {}), { navigator: {} });
  assert.equal(res.error, "unavailable");
});

test("usb.request: cancelled on AbortError", async () => {
  const navigator = { usb: { requestDevice: async () => { throw abortError(); } } };
  const res = await dispatch(call("usb.request", {}), { navigator });
  assert.equal(res.error, "cancelled");
});

// --- webaudio --------------------------------------------------------------

test("webaudio.tone: schedules a tone and returns immediately", async () => {
  const events = [];
  class FakeAudioContext {
    constructor() {
      this.currentTime = 0;
      this.destination = { kind: "destination" };
    }
    createOscillator() {
      return {
        frequency: {},
        connect: () => events.push("osc.connect"),
        start: () => events.push("start"),
        stop: (t) => events.push(`stop:${t}`),
      };
    }
    createGain() {
      return { gain: {}, connect: () => events.push("gain.connect") };
    }
    close() {
      events.push("close");
    }
  }
  const res = await dispatch(
    call("webaudio.tone", { frequency: 440, duration_ms: 200, type: "square", volume: 0.5 }),
    { AudioContext: FakeAudioContext },
  );
  assert.equal(res.ok, true);
  assert.deepEqual(res.value, {});
  assert.ok(events.includes("start"));
  assert.ok(events.includes("stop:0.2"));
});

test("webaudio.tone: unavailable when AudioContext is missing", async () => {
  const res = await dispatch(call("webaudio.tone", { frequency: 440 }), {});
  assert.equal(res.error, "unavailable");
});
