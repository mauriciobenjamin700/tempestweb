// Tests for the Tier-2 native capabilities added to client/native/*.
//
// Web APIs are injected as `deps` (fake navigator/window/speechSynthesis/etc.), so
// these run under node:test with no real browser. Each capability is exercised for
// its success shape and for the CapabilityError code it raises when the API is
// absent (or the id is unknown, or the picker is cancelled). MediaRecorder and
// FileReader are mocked on globalThis where a handler reads them there.

import { test } from "node:test";
import assert from "node:assert/strict";

import { dispatch } from "../../client/native/index.js";

/** Build a native_call envelope. */
function call(capability, args = {}, callId = "c1") {
  return { kind: "native_call", call_id: callId, capability, args };
}

/**
 * Install a minimal FileReader on globalThis that emits a fixed base64 payload.
 * The data URL's base64 body is "QUJD" (bytes "ABC").
 */
function withFileReader(fn) {
  const prev = globalThis.FileReader;
  class FakeFileReader {
    readAsDataURL(_blob) {
      this.result = "data:application/octet-stream;base64,QUJD";
      if (this.onload) this.onload();
    }
  }
  globalThis.FileReader = FakeFileReader;
  return Promise.resolve()
    .then(fn)
    .finally(() => {
      globalThis.FileReader = prev;
    });
}

// --- speech ----------------------------------------------------------------

test("speech.speak: builds an utterance and speaks it (fire-and-forget)", async () => {
  const spoken = [];
  let built;
  const speechSynthesis = { speak: (u) => spoken.push(u) };
  function SpeechSynthesisUtterance(text) {
    this.text = text;
    built = this;
  }
  const res = await dispatch(
    call("speech.speak", { text: "hi", lang: "en-US", rate: 1.5, pitch: 0.9, volume: 0.5 }),
    { speechSynthesis, SpeechSynthesisUtterance },
  );
  assert.equal(res.ok, true);
  assert.deepEqual(res.value, {});
  assert.equal(spoken.length, 1);
  assert.equal(built.text, "hi");
  assert.equal(built.lang, "en-US");
  assert.equal(built.rate, 1.5);
  assert.equal(built.pitch, 0.9);
  assert.equal(built.volume, 0.5);
});

test("speech.speak: unavailable when speech synthesis is missing", async () => {
  const res = await dispatch(call("speech.speak", { text: "hi" }), {});
  assert.equal(res.ok, false);
  assert.equal(res.error, "unavailable");
});

test("speech.cancel: cancels queued speech", async () => {
  let cancelled = 0;
  const res = await dispatch(call("speech.cancel"), {
    speechSynthesis: { cancel: () => (cancelled += 1) },
  });
  assert.equal(res.ok, true);
  assert.equal(cancelled, 1);
});

test("speech.cancel: unavailable when speech synthesis is missing", async () => {
  const res = await dispatch(call("speech.cancel"), {});
  assert.equal(res.ok, false);
  assert.equal(res.error, "unavailable");
});

test("speech.voices: maps the voice list", async () => {
  const speechSynthesis = {
    getVoices: () => [
      { name: "Alex", lang: "en-US", default: true },
      { name: "Luciana", lang: "pt-BR" },
    ],
  };
  const res = await dispatch(call("speech.voices"), { speechSynthesis });
  assert.equal(res.ok, true);
  assert.deepEqual(res.value, {
    voices: [
      { name: "Alex", lang: "en-US", default: true },
      { name: "Luciana", lang: "pt-BR", default: false },
    ],
  });
});

test("speech.voices: unavailable when speech synthesis is missing", async () => {
  const res = await dispatch(call("speech.voices"), {});
  assert.equal(res.ok, false);
  assert.equal(res.error, "unavailable");
});

// --- recorder --------------------------------------------------------------

/** A fake MediaRecorder that captures a single chunk on stop. */
function makeMediaRecorder() {
  const stopped = [];
  class FakeMediaRecorder {
    constructor(stream, opts) {
      this.stream = stream;
      this.mimeType = (opts && opts.mimeType) || "";
    }
    start() {
      // Emit a chunk asynchronously to mimic dataavailable.
      if (this.ondataavailable) {
        this.ondataavailable({ data: new Blob([Uint8Array.from([65, 66, 67])], { type: "audio/webm" }) });
      }
    }
    stop() {
      if (this.onstop) this.onstop();
    }
  }
  return { FakeMediaRecorder, stopped };
}

test("recorder.start then stop round-trips a recording by id", async () => {
  await withFileReader(async () => {
    const tracks = [{ stop() {} }];
    const stream = { getTracks: () => tracks };
    const { FakeMediaRecorder } = makeMediaRecorder();
    const navigator = {
      mediaDevices: { getUserMedia: async () => stream },
    };
    const deps = { navigator, MediaRecorder: FakeMediaRecorder };

    const start = await dispatch(call("recorder.start", { source: "microphone" }), deps);
    assert.equal(start.ok, true);
    assert.equal(typeof start.value.id, "string");

    const stop = await dispatch(call("recorder.stop", { id: start.value.id }), deps);
    assert.equal(stop.ok, true);
    assert.equal(stop.value.data_base64, "QUJD");
    assert.equal(stop.value.mime_type, "audio/webm");
    assert.ok(stop.value.size > 0);
  });
});

test("recorder.start: screen source uses getDisplayMedia", async () => {
  await withFileReader(async () => {
    let usedDisplay = false;
    const stream = { getTracks: () => [] };
    const { FakeMediaRecorder } = makeMediaRecorder();
    const navigator = {
      mediaDevices: {
        getDisplayMedia: async () => {
          usedDisplay = true;
          return stream;
        },
      },
    };
    const res = await dispatch(call("recorder.start", { source: "screen" }), {
      navigator,
      MediaRecorder: FakeMediaRecorder,
    });
    assert.equal(res.ok, true);
    assert.equal(usedDisplay, true);
  });
});

test("recorder.start: unavailable when MediaRecorder is missing", async () => {
  const res = await dispatch(call("recorder.start", { source: "microphone" }), {
    navigator: { mediaDevices: {} },
  });
  assert.equal(res.ok, false);
  assert.equal(res.error, "unavailable");
});

test("recorder.stop: not_found for an unknown id", async () => {
  const res = await dispatch(call("recorder.stop", { id: "recorder-nope" }), {});
  assert.equal(res.ok, false);
  assert.equal(res.error, "not_found");
});

// --- filesystem ------------------------------------------------------------

test("filesystem.open_file: reads picked files as base64", async () => {
  await withFileReader(async () => {
    const handle = {
      name: "a.txt",
      getFile: async () => ({ name: "a.txt", type: "text/plain" }),
    };
    const window = { showOpenFilePicker: async () => [handle] };
    const res = await dispatch(call("filesystem.open_file", { multiple: false }), { window });
    assert.equal(res.ok, true);
    assert.equal(res.value.files.length, 1);
    const f = res.value.files[0];
    assert.equal(typeof f.id, "string");
    assert.equal(f.name, "a.txt");
    assert.equal(f.mime_type, "text/plain");
    assert.equal(f.data_base64, "QUJD");
  });
});

test("filesystem.open_file: unavailable when the API is missing", async () => {
  const res = await dispatch(call("filesystem.open_file", {}), { window: {} });
  assert.equal(res.ok, false);
  assert.equal(res.error, "unavailable");
});

test("filesystem.open_file: cancelled on AbortError", async () => {
  const window = {
    showOpenFilePicker: async () => {
      const err = new Error("dismissed");
      err.name = "AbortError";
      throw err;
    },
  };
  const res = await dispatch(call("filesystem.open_file", {}), { window });
  assert.equal(res.ok, false);
  assert.equal(res.error, "cancelled");
});

test("filesystem.write_file: writes to a stored handle", async () => {
  await withFileReader(async () => {
    const written = [];
    const handle = {
      name: "a.txt",
      getFile: async () => ({ name: "a.txt", type: "text/plain" }),
      createWritable: async () => ({
        write: async (b) => written.push(b),
        close: async () => {},
      }),
    };
    const window = { showOpenFilePicker: async () => [handle] };
    const open = await dispatch(call("filesystem.open_file", {}), { window });
    const id = open.value.files[0].id;

    const res = await dispatch(call("filesystem.write_file", { id, data_base64: "QUJD" }), {});
    assert.equal(res.ok, true);
    assert.deepEqual(res.value, { written: true });
    assert.equal(written.length, 1);
    assert.ok(written[0] instanceof Blob);
  });
});

test("filesystem.write_file: not_found for an unknown id", async () => {
  const res = await dispatch(call("filesystem.write_file", { id: "filesystem-nope", data_base64: "QUJD" }), {});
  assert.equal(res.ok, false);
  assert.equal(res.error, "not_found");
});

test("filesystem.save_file: saves bytes and returns the handle id", async () => {
  let suggested;
  const handle = {
    name: "out.bin",
    createWritable: async () => ({ write: async () => {}, close: async () => {} }),
  };
  const window = {
    showSaveFilePicker: async (opts) => {
      suggested = opts.suggestedName;
      return handle;
    },
  };
  const res = await dispatch(
    call("filesystem.save_file", { filename: "out.bin", data_base64: "QUJD", mime_type: "application/octet-stream" }),
    { window },
  );
  assert.equal(res.ok, true);
  assert.equal(res.value.name, "out.bin");
  assert.equal(typeof res.value.id, "string");
  assert.equal(suggested, "out.bin");
});

test("filesystem.save_file: cancelled on AbortError", async () => {
  const window = {
    showSaveFilePicker: async () => {
      const err = new Error("dismissed");
      err.name = "AbortError";
      throw err;
    },
  };
  const res = await dispatch(call("filesystem.save_file", { filename: "x", data_base64: "QUJD" }), { window });
  assert.equal(res.ok, false);
  assert.equal(res.error, "cancelled");
});

// --- bgsync ----------------------------------------------------------------

test("bgsync.register: registers a one-off sync tag", async () => {
  let tag;
  const navigator = {
    serviceWorker: { ready: Promise.resolve({ sync: { register: async (t) => (tag = t) } }) },
  };
  const res = await dispatch(call("bgsync.register", { tag: "outbox" }), { navigator });
  assert.equal(res.ok, true);
  assert.deepEqual(res.value, { registered: true });
  assert.equal(tag, "outbox");
});

test("bgsync.register: unavailable without a service worker", async () => {
  const res = await dispatch(call("bgsync.register", { tag: "x" }), { navigator: {} });
  assert.equal(res.ok, false);
  assert.equal(res.error, "unavailable");
});

test("bgsync.register: unavailable when reg.sync is missing", async () => {
  const navigator = { serviceWorker: { ready: Promise.resolve({}) } };
  const res = await dispatch(call("bgsync.register", { tag: "x" }), { navigator });
  assert.equal(res.ok, false);
  assert.equal(res.error, "unavailable");
});

test("bgsync.register_periodic: registers with a min interval", async () => {
  let seen;
  const navigator = {
    serviceWorker: {
      ready: Promise.resolve({
        periodicSync: { register: async (t, o) => (seen = { t, o }) },
      }),
    },
  };
  const res = await dispatch(
    call("bgsync.register_periodic", { tag: "refresh", min_interval_ms: 43200000 }),
    { navigator },
  );
  assert.equal(res.ok, true);
  assert.deepEqual(res.value, { registered: true });
  assert.equal(seen.t, "refresh");
  assert.deepEqual(seen.o, { minInterval: 43200000 });
});

test("bgsync.register_periodic: unavailable when periodicSync is missing", async () => {
  const navigator = { serviceWorker: { ready: Promise.resolve({}) } };
  const res = await dispatch(call("bgsync.register_periodic", { tag: "x", min_interval_ms: 1 }), {
    navigator,
  });
  assert.equal(res.ok, false);
  assert.equal(res.error, "unavailable");
});

// --- tabs ------------------------------------------------------------------

test("tabs.broadcast: posts a message and closes the channel", async () => {
  const posted = [];
  let closed = false;
  class FakeBroadcastChannel {
    constructor(name) {
      this.name = name;
    }
    postMessage(m) {
      posted.push({ name: this.name, m });
    }
    close() {
      closed = true;
    }
  }
  const res = await dispatch(call("tabs.broadcast", { channel: "sync", message: { n: 1 } }), {
    BroadcastChannel: FakeBroadcastChannel,
  });
  assert.equal(res.ok, true);
  assert.deepEqual(res.value, {});
  assert.deepEqual(posted, [{ name: "sync", m: { n: 1 } }]);
  assert.equal(closed, true);
});

test("tabs.broadcast: unavailable when BroadcastChannel is missing", async () => {
  // Node ships a global BroadcastChannel, so mask it to simulate absence.
  const prev = globalThis.BroadcastChannel;
  globalThis.BroadcastChannel = undefined;
  try {
    const res = await dispatch(call("tabs.broadcast", { channel: "x", message: 1 }), {});
    assert.equal(res.ok, false);
    assert.equal(res.error, "unavailable");
  } finally {
    globalThis.BroadcastChannel = prev;
  }
});

test("tabs.lock then unlock acquires and releases a Web Lock", async () => {
  let released = false;
  const navigator = {
    locks: {
      request: (name, opts, cb) => {
        // The callback holds the lock for the lifetime of its returned promise.
        const held = cb();
        held.then(() => (released = true));
        return held;
      },
    },
  };
  const lock = await dispatch(call("tabs.lock", { name: "job", mode: "exclusive" }), { navigator });
  assert.equal(lock.ok, true);
  assert.deepEqual(lock.value, { acquired: true });
  assert.equal(released, false);

  const unlock = await dispatch(call("tabs.unlock", { name: "job" }), {});
  assert.equal(unlock.ok, true);
  assert.deepEqual(unlock.value, {});
  await Promise.resolve();
  assert.equal(released, true);
});

test("tabs.lock: unavailable when the Web Locks API is missing", async () => {
  const res = await dispatch(call("tabs.lock", { name: "x" }), { navigator: {} });
  assert.equal(res.ok, false);
  assert.equal(res.error, "unavailable");
});

test("tabs.unlock: idempotent for an unknown name", async () => {
  const res = await dispatch(call("tabs.unlock", { name: "never-locked" }), {});
  assert.equal(res.ok, true);
  assert.deepEqual(res.value, {});
});

// --- webauthn --------------------------------------------------------------

test("webauthn.create: converts fields and serializes the credential", async () => {
  let seenPublicKey;
  const cred = {
    id: "cred-id",
    type: "public-key",
    rawId: Uint8Array.from([1, 2, 3]).buffer,
    response: {
      clientDataJSON: Uint8Array.from([4, 5]).buffer,
      attestationObject: Uint8Array.from([6, 7]).buffer,
    },
  };
  const navigator = {
    credentials: {
      create: async (opts) => {
        seenPublicKey = opts.publicKey;
        return cred;
      },
    },
  };
  const options = {
    challenge: "QUJD",
    user: { id: "QUJD", name: "u" },
    excludeCredentials: [{ id: "QUJD", type: "public-key" }],
  };
  const res = await dispatch(call("webauthn.create", { options }), { navigator });
  assert.equal(res.ok, true);
  // challenge / user.id / excludeCredentials[].id became ArrayBuffers.
  assert.ok(seenPublicKey.challenge instanceof ArrayBuffer);
  assert.ok(seenPublicKey.user.id instanceof ArrayBuffer);
  assert.ok(seenPublicKey.excludeCredentials[0].id instanceof ArrayBuffer);
  const c = res.value.credential;
  assert.equal(c.id, "cred-id");
  assert.equal(c.type, "public-key");
  assert.equal(typeof c.rawId, "string");
  assert.equal(typeof c.response.clientDataJSON, "string");
  assert.equal(typeof c.response.attestationObject, "string");
});

test("webauthn.create: unavailable when credentials API is missing", async () => {
  const res = await dispatch(call("webauthn.create", { options: {} }), { navigator: {} });
  assert.equal(res.ok, false);
  assert.equal(res.error, "unavailable");
});

test("webauthn.create: failed when the request rejects", async () => {
  const navigator = { credentials: { create: async () => { throw new Error("nope"); } } };
  const res = await dispatch(call("webauthn.create", { options: { challenge: "QUJD" } }), { navigator });
  assert.equal(res.ok, false);
  assert.equal(res.error, "failed");
});

test("webauthn.get: converts fields and serializes the assertion", async () => {
  let seenPublicKey;
  const cred = {
    id: "cred-id",
    type: "public-key",
    rawId: Uint8Array.from([1]).buffer,
    response: {
      clientDataJSON: Uint8Array.from([2]).buffer,
      authenticatorData: Uint8Array.from([3]).buffer,
      signature: Uint8Array.from([4]).buffer,
      userHandle: Uint8Array.from([5]).buffer,
    },
  };
  const navigator = {
    credentials: {
      get: async (opts) => {
        seenPublicKey = opts.publicKey;
        return cred;
      },
    },
  };
  const options = { challenge: "QUJD", allowCredentials: [{ id: "QUJD", type: "public-key" }] };
  const res = await dispatch(call("webauthn.get", { options }), { navigator });
  assert.equal(res.ok, true);
  assert.ok(seenPublicKey.challenge instanceof ArrayBuffer);
  assert.ok(seenPublicKey.allowCredentials[0].id instanceof ArrayBuffer);
  const c = res.value.credential;
  assert.equal(c.id, "cred-id");
  assert.equal(typeof c.response.clientDataJSON, "string");
  assert.equal(typeof c.response.authenticatorData, "string");
  assert.equal(typeof c.response.signature, "string");
  assert.equal(typeof c.response.userHandle, "string");
});

test("webauthn.get: unavailable when credentials API is missing", async () => {
  const res = await dispatch(call("webauthn.get", { options: {} }), { navigator: {} });
  assert.equal(res.ok, false);
  assert.equal(res.error, "unavailable");
});

test("webauthn.get_otp: reads an SMS one-time code", async () => {
  let seen;
  const navigator = {
    credentials: {
      get: async (opts) => {
        seen = opts;
        return { code: "123456" };
      },
    },
  };
  const res = await dispatch(call("webauthn.get_otp"), { navigator });
  assert.equal(res.ok, true);
  assert.deepEqual(res.value, { code: "123456" });
  assert.deepEqual(seen.otp, { transport: ["sms"] });
});

test("webauthn.get_otp: unavailable when credentials API is missing", async () => {
  const res = await dispatch(call("webauthn.get_otp"), { navigator: {} });
  assert.equal(res.ok, false);
  assert.equal(res.error, "unavailable");
});
