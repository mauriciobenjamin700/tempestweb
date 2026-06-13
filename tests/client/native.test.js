// Tests for the browser-side native capability glue (client/native/*).
//
// All Web APIs are injected as `deps`, so these run under node:test with no real
// browser. They verify the native_call -> native_result envelope shaping and each
// capability's success/failure behavior.

import { test } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";

import { dispatch, installNativeBridge, HANDLERS } from "../../client/native/index.js";

/** Build a native_call envelope. */
function call(capability, args = {}, callId = "c1") {
  return { kind: "native_call", call_id: callId, capability, args };
}

test("dispatch: unknown capability resolves a typed error result", async () => {
  const res = await dispatch(call("nope.thing"), {});
  assert.equal(res.ok, false);
  assert.equal(res.error, "unknown_capability");
  assert.equal(res.call_id, "c1");
});

test("dispatch: a thrown CapabilityError becomes ok:false with its code", async () => {
  const res = await dispatch(call("clipboard.read"), { navigator: {} });
  assert.equal(res.ok, false);
  assert.equal(res.error, "unavailable");
});

test("dispatch: success wraps the value and echoes call_id", async () => {
  const deps = {
    navigator: { clipboard: { readText: async () => "hi" } },
  };
  const res = await dispatch(call("clipboard.read", {}, "c42"), deps);
  assert.equal(res.ok, true);
  assert.equal(res.call_id, "c42");
  assert.deepEqual(res.value, { text: "hi" });
});

test("HANDLERS covers every documented capability name", () => {
  const expected = [
    "http.request",
    "http.upload",
    "audio.play",
    "audio.stop",
    "share.is_supported",
    "share.share",
    "geolocation.get",
    "clipboard.read",
    "clipboard.write",
    "storage.put",
    "storage.get",
    "storage.list",
    "storage.remove",
    "camera.capture",
    "onnx.load",
    "onnx.run",
    "file.save",
    "notifications.notify",
    "notifications.request_permission",
    "notifications.subscribe",
    "notifications.unsubscribe",
  ];
  for (const name of expected) assert.equal(typeof HANDLERS[name], "function", name);
});

test("installNativeBridge exposes window.__tempestweb_native__", async () => {
  const target = {};
  const deps = { navigator: { clipboard: { readText: async () => "x" } } };
  installNativeBridge(target, deps);
  const res = await target.__tempestweb_native__(call("clipboard.read"));
  assert.equal(res.ok, true);
  assert.deepEqual(res.value, { text: "x" });
});

// --- http -----------------------------------------------------------------

test("http.request: GET parses status/ok/json", async () => {
  const deps = {
    fetch: async (url, init) => {
      assert.equal(url, "/api/items");
      assert.equal(init.method, "GET");
      return {
        status: 200,
        ok: true,
        headers: { get: () => "application/json" },
        text: async () => JSON.stringify({ items: [1, 2] }),
      };
    },
  };
  const res = await dispatch(call("http.request", { method: "GET", url: "/api/items" }), deps);
  assert.equal(res.ok, true);
  assert.equal(res.value.status, 200);
  assert.deepEqual(res.value.json, { items: [1, 2] });
});

test("http.request: a rejected fetch becomes a network error", async () => {
  const deps = {
    fetch: async () => {
      throw new Error("offline");
    },
  };
  const res = await dispatch(call("http.request", { method: "GET", url: "/x" }), deps);
  assert.equal(res.ok, false);
  assert.equal(res.error, "network");
});

test("http.request: a JSON body is serialized with a content-type header", async () => {
  let seen;
  const deps = {
    fetch: async (_url, init) => {
      seen = init;
      return { status: 201, ok: true, headers: { get: () => "" }, text: async () => "" };
    },
  };
  await dispatch(
    call("http.request", { method: "POST", url: "/x", json: { a: 1 }, headers: {} }),
    deps,
  );
  assert.equal(seen.body, JSON.stringify({ a: 1 }));
  assert.equal(seen.headers["content-type"], "application/json");
});

// --- audio ----------------------------------------------------------------

test("audio.play: resolves played:true and sets volume", async () => {
  let madeVolume;
  class FakeAudio {
    constructor(src) {
      this.src = src;
    }
    set volume(v) {
      madeVolume = v;
    }
    play() {
      return Promise.resolve();
    }
    pause() {}
  }
  const res = await dispatch(
    call("audio.play", { src: "/a.wav", volume: 0.5, channel: "fx" }),
    { Audio: FakeAudio },
  );
  assert.equal(res.ok, true);
  assert.equal(res.value.played, true);
  assert.equal(madeVolume, 0.5);
});

test("audio.play: a blocked autoplay resolves blocked:true (not an error)", async () => {
  class BlockedAudio {
    constructor() {}
    set volume(_v) {}
    play() {
      return Promise.reject(new Error("NotAllowedError"));
    }
    pause() {}
  }
  const res = await dispatch(call("audio.play", { src: "/a.wav" }), { Audio: BlockedAudio });
  assert.equal(res.ok, true);
  assert.equal(res.value.played, false);
  assert.equal(res.value.blocked, true);
});

// --- share ----------------------------------------------------------------

test("share.is_supported: false when navigator.share is missing", async () => {
  const res = await dispatch(call("share.is_supported"), { navigator: {} });
  assert.equal(res.value.supported, false);
});

test("share.share: unsupported is a normal outcome, not an error", async () => {
  const res = await dispatch(call("share.share", { text: "x" }), { navigator: {} });
  assert.equal(res.ok, true);
  assert.equal(res.value.outcome, "unsupported");
});

test("share.share: cancelled when the user aborts", async () => {
  const navigator = {
    share: async () => {
      const e = new Error("abort");
      e.name = "AbortError";
      throw e;
    },
  };
  const res = await dispatch(call("share.share", { url: "https://x" }), { navigator });
  assert.equal(res.value.outcome, "cancelled");
});

test("share.share: shared on success", async () => {
  const navigator = { share: async () => undefined };
  const res = await dispatch(call("share.share", { title: "Hi" }), { navigator });
  assert.equal(res.value.outcome, "shared");
});

// --- geolocation ----------------------------------------------------------

test("geolocation.get: resolves a Position-shaped value", async () => {
  const navigator = {
    geolocation: {
      getCurrentPosition: (ok) =>
        ok({ coords: { latitude: -23.5, longitude: -46.6, accuracy: 12, altitude: null } }),
    },
  };
  const res = await dispatch(call("geolocation.get", { high_accuracy: true }), { navigator });
  assert.equal(res.ok, true);
  assert.equal(res.value.latitude, -23.5);
  assert.equal(res.value.altitude, null);
});

test("geolocation.get: permission denied maps to permission_denied", async () => {
  const navigator = {
    geolocation: { getCurrentPosition: (_ok, err) => err({ code: 1, message: "denied" }) },
  };
  const res = await dispatch(call("geolocation.get"), { navigator });
  assert.equal(res.ok, false);
  assert.equal(res.error, "permission_denied");
});

// --- storage (localStorage fallback) --------------------------------------

function fakeLocalStorage() {
  const map = new Map();
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    removeItem: (k) => map.delete(k),
    key: (i) => [...map.keys()][i] ?? null,
    get length() {
      return map.size;
    },
  };
}

test("storage: put/get/list/remove over the localStorage fallback", async () => {
  const localStorage = fakeLocalStorage();
  const deps = { localStorage };

  await dispatch(call("storage.put", { name: "a", content: "1" }), deps);
  await dispatch(call("storage.put", { name: "b", content: "2" }), deps);

  const got = await dispatch(call("storage.get", { name: "a" }), deps);
  assert.deepEqual(got.value, { content: "1" });

  const list = await dispatch(call("storage.list"), deps);
  assert.deepEqual(list.value.keys.sort(), ["a", "b"]);

  await dispatch(call("storage.remove", { name: "a" }), deps);
  const missing = await dispatch(call("storage.get", { name: "a" }), deps);
  assert.equal(missing.ok, false);
  assert.equal(missing.error, "not_found");
});

test("storage.list: empty store returns an empty array", async () => {
  const res = await dispatch(call("storage.list"), { localStorage: fakeLocalStorage() });
  assert.deepEqual(res.value.keys, []);
});

test("storage: prefers an injected owner-scoped IndexedDB store", async () => {
  const map = new Map();
  const store = {
    get: async (n) => (map.has(n) ? map.get(n) : null),
    put: async (n, c) => map.set(n, c),
    remove: async (n) => map.delete(n),
    keys: async () => [...map.keys()],
  };
  const deps = { store };
  await dispatch(call("storage.put", { name: "k", content: "v" }), deps);
  const got = await dispatch(call("storage.get", { name: "k" }), deps);
  assert.deepEqual(got.value, { content: "v" });
});

// --- notifications --------------------------------------------------------

test("notifications.request_permission: returns the prompted state", async () => {
  const Notification = {
    permission: "default",
    requestPermission: async () => "granted",
  };
  const res = await dispatch(call("notifications.request_permission"), { Notification });
  assert.equal(res.value.permission, "granted");
});

test("notifications.notify: constructs a Notification only when granted", async () => {
  let constructed = 0;
  function Notification(title, opts) {
    constructed += 1;
    this.title = title;
    this.opts = opts;
  }
  Notification.permission = "granted";
  const res = await dispatch(call("notifications.notify", { title: "Hi", body: "yo" }), {
    Notification,
  });
  assert.equal(res.ok, true);
  assert.equal(constructed, 1);
});

// --- notifications: WebPush subscribe/unsubscribe (P3) --------------------

/** A fake PushSubscription returning a JSON shape. */
function fakeSubscription(endpoint = "https://push.example/abc") {
  return {
    endpoint,
    toJSON: () => ({ endpoint, keys: { p256dh: "p", auth: "a" } }),
    unsubscribe: async () => true,
  };
}

test("notifications.subscribe: runs the push flow and returns the subscription", async () => {
  let current = null;
  const registration = {
    pushManager: {
      getSubscription: async () => current,
      subscribe: async () => {
        current = fakeSubscription();
        return current;
      },
    },
  };
  const deps = {
    navigator: { serviceWorker: {} },
    Notification: { permission: "granted", requestPermission: async () => "granted" },
    registration,
  };
  const res = await dispatch(
    call("notifications.subscribe", { vapid_public_key: "KEY" }),
    deps,
  );
  assert.equal(res.ok, true);
  assert.equal(res.value.endpoint, "https://push.example/abc");
  assert.deepEqual(res.value.keys, { p256dh: "p", auth: "a" });
});

test("notifications.subscribe: missing vapid_public_key is invalid_argument", async () => {
  const res = await dispatch(call("notifications.subscribe", {}), {
    navigator: { serviceWorker: {} },
    Notification: { permission: "granted" },
    registration: { pushManager: {} },
  });
  assert.equal(res.ok, false);
  assert.equal(res.error, "invalid_argument");
});

test("notifications.subscribe: denied permission maps to permission_denied", async () => {
  const deps = {
    navigator: { serviceWorker: {} },
    Notification: { permission: "denied", requestPermission: async () => "denied" },
    registration: { pushManager: { getSubscription: async () => null } },
  };
  const res = await dispatch(
    call("notifications.subscribe", { vapid_public_key: "KEY" }),
    deps,
  );
  assert.equal(res.ok, false);
  assert.equal(res.error, "permission_denied");
});

test("notifications.unsubscribe: cancels an existing subscription", async () => {
  const sub = fakeSubscription();
  const deps = {
    navigator: { serviceWorker: {} },
    Notification: { permission: "granted" },
    registration: { pushManager: { getSubscription: async () => sub } },
  };
  const res = await dispatch(call("notifications.unsubscribe"), deps);
  assert.equal(res.ok, true);
  assert.equal(res.value.unsubscribed, true);
});

test("notifications.unsubscribe: false when there is no subscription", async () => {
  const deps = {
    navigator: { serviceWorker: {} },
    Notification: { permission: "granted" },
    registration: { pushManager: { getSubscription: async () => null } },
  };
  const res = await dispatch(call("notifications.unsubscribe"), deps);
  assert.equal(res.ok, true);
  assert.equal(res.value.unsubscribed, false);
});

// --- camera (jsdom canvas stub) -------------------------------------------

test("camera.capture: returns base64 frame and stops tracks", async () => {
  const dom = new JSDOM("<!doctype html><html><body></body></html>");
  const doc = dom.window.document;
  // jsdom lacks canvas encoding; stub the elements the handler touches.
  const origCreate = doc.createElement.bind(doc);
  doc.createElement = (tag) => {
    if (tag === "video") {
      return { srcObject: null, play: async () => {}, videoWidth: 2, videoHeight: 2 };
    }
    if (tag === "canvas") {
      return {
        width: 0,
        height: 0,
        getContext: () => ({ drawImage: () => {} }),
        toDataURL: () => "data:image/jpeg;base64,QUJD",
      };
    }
    return origCreate(tag);
  };
  let stopped = 0;
  const navigator = {
    mediaDevices: {
      getUserMedia: async () => ({
        getTracks: () => [{ stop: () => (stopped += 1) }],
      }),
    },
  };
  const res = await dispatch(call("camera.capture", { facing: "user", quality: 0.5 }), {
    navigator,
    document: doc,
  });
  assert.equal(res.ok, true);
  assert.equal(res.value.data_base64, "QUJD");
  assert.equal(res.value.mime_type, "image/jpeg");
  assert.equal(stopped, 1);
});

test("camera.capture: permission denied maps to permission_denied", async () => {
  const navigator = {
    mediaDevices: {
      getUserMedia: async () => {
        const e = new Error("no");
        e.name = "NotAllowedError";
        throw e;
      },
    },
  };
  const res = await dispatch(call("camera.capture"), { navigator, document: {} });
  assert.equal(res.ok, false);
  assert.equal(res.error, "permission_denied");
});
