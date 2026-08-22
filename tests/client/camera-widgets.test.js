// CameraPreview and QrScanner: the widgets that hold a camera open.
//
// Both declared handlers the client could never fire, because both rendered as
// empty boxes: no stream, no preview, nothing to sample or decode. jsdom has
// neither a camera nor a canvas, so the browser seams are injected — which is
// what `installCameras(root, transport, deps)` takes them for.
import { test } from "node:test";
import assert from "node:assert/strict";
import { freshDom } from "./setup.js";
import { buildElement } from "../../client/dom.js";
import { installCameras } from "../../client/camera-widgets.js";

/** A mock Transport that records every sendEvent call. */
function mockTransport() {
  /** @type {import("../../client/transport.js").TWEvent[]} */
  const events = [];
  return { events, onPatches() {}, sendEvent: (e) => events.push(e), async close() {} };
}

/** A fake MediaStream whose tracks record being stopped. */
function fakeStream() {
  const track = { stopped: false, stop() { this.stopped = true; } };
  return { track, getTracks: () => [track] };
}

/**
 * A jsdom-friendly browser stand-in.
 *
 * The video reports a size (jsdom's never would) and the canvas returns a data
 * URL, so the sampling path can be asserted end to end.
 */
function fakeDeps(dom, { stream = fakeStream(), fail = null, codes = null } = {}) {
  const created = [];
  const doc = {
    createElement(tag) {
      const el = dom.document.createElement(tag);
      created.push(el);
      if (tag === "video") {
        Object.defineProperty(el, "videoWidth", { value: 640, configurable: true });
        Object.defineProperty(el, "videoHeight", { value: 480, configurable: true });
        el.play = async () => {};
      }
      if (tag === "canvas") {
        el.getContext = () => ({ drawImage() {} });
        el.toDataURL = () => "data:image/jpeg;base64,QUJD";
      }
      return el;
    },
  };
  const navigator = {
    mediaDevices: {
      calls: [],
      async getUserMedia(constraints) {
        this.calls.push(constraints);
        if (fail) {
          throw new Error(fail);
        }
        return stream;
      },
    },
  };
  const detector =
    codes === null
      ? undefined
      : class {
          constructor(options) {
            this.options = options;
          }

          async detect() {
            return codes.shift() ?? [];
          }
        };
  return { doc, navigator, detector, stream, created };
}

/** Mount a camera widget of `type` under the dom root. */
function widget(dom, type, props = {}, key = "cam") {
  const el = buildElement({ type, key, props, children: [] });
  dom.root.appendChild(el);
  return el;
}

/** Let the setup's awaits settle. */
function settle(ms = 10) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

test("a CameraPreview is marked with the camera it asked for", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = widget(dom, "CameraPreview", { facing: "front", frame_interval_ms: 500 });

  assert.equal(el.getAttribute("data-tw-camera"), "preview");
  assert.equal(el.getAttribute("data-tw-facing"), "front");
  assert.equal(el.getAttribute("data-tw-frame-interval"), "500");
});

test("a QrScanner is marked as a scanner", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = widget(dom, "QrScanner", {});

  assert.equal(el.getAttribute("data-tw-camera"), "scanner");
});

test("mounting a preview opens the stream and shows it", async () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = widget(dom, "CameraPreview", { facing: "back", frame_interval_ms: 5 });
  const deps = fakeDeps(dom);
  const cameras = installCameras(dom.root, mockTransport(), {
    document: deps.doc,
    navigator: deps.navigator,
  });

  cameras.sync();
  await settle();

  assert.deepEqual(deps.navigator.mediaDevices.calls, [
    { video: { facingMode: "environment" }, audio: false },
  ]);
  const video = el.querySelector('[data-tw-part="preview"]');
  assert.ok(video, "the renderer owns a <video> inside the leaf");
  assert.equal(video.srcObject, deps.stream);
  cameras.dispose();
});

test("a front-facing preview asks for the user-facing camera", async () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  widget(dom, "CameraPreview", { facing: "front", frame_interval_ms: 5 });
  const deps = fakeDeps(dom);
  const cameras = installCameras(dom.root, mockTransport(), {
    document: deps.doc,
    navigator: deps.navigator,
  });

  cameras.sync();
  await settle();

  assert.equal(deps.navigator.mediaDevices.calls[0].video.facingMode, "user");
  cameras.dispose();
});

test("a preview reports frames with their size and bytes", async () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  widget(dom, "CameraPreview", { frame_interval_ms: 5 });
  const transport = mockTransport();
  const deps = fakeDeps(dom);
  const cameras = installCameras(dom.root, transport, {
    document: deps.doc,
    navigator: deps.navigator,
  });

  cameras.sync();
  await settle(40);
  cameras.dispose();

  const frames = transport.events.filter((event) => event.type === "frame");
  assert.ok(frames.length >= 1, "the interval sampled at least one frame");
  assert.deepEqual(frames[0], {
    type: "frame",
    key: "cam",
    // The base64 payload only: the `data:` prefix is the transport's business,
    // not the core's field.
    payload: { width: 640, height: 480, data: "QUJD", rotation: 0 },
  });
});

test("removing a preview stops the camera", async () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = widget(dom, "CameraPreview", { frame_interval_ms: 5 });
  const deps = fakeDeps(dom);
  const cameras = installCameras(dom.root, mockTransport(), {
    document: deps.doc,
    navigator: deps.navigator,
  });
  cameras.sync();
  await settle();

  el.remove();
  cameras.sync();

  // A camera left open is a light left on, on someone's phone.
  assert.equal(deps.stream.track.stopped, true);
  cameras.dispose();
});

test("dispose stops every open camera", async () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  widget(dom, "CameraPreview", { frame_interval_ms: 5 });
  const deps = fakeDeps(dom);
  const cameras = installCameras(dom.root, mockTransport(), {
    document: deps.doc,
    navigator: deps.navigator,
  });
  cameras.sync();
  await settle();

  cameras.dispose();
  assert.equal(deps.stream.track.stopped, true);
});

test("a scanner reports a code it reads, once", async () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  widget(dom, "QrScanner", {}, "scan");
  const transport = mockTransport();
  const deps = fakeDeps(dom, {
    codes: [
      [{ rawValue: "https://example.test/1", format: "qr_code" }],
      [{ rawValue: "https://example.test/1", format: "qr_code" }],
      [{ rawValue: "https://example.test/2", format: "qr_code" }],
    ],
  });
  const cameras = installCameras(dom.root, transport, {
    document: deps.doc,
    navigator: deps.navigator,
    detector: deps.detector,
  });

  cameras.sync();
  await settle(900);
  cameras.dispose();

  const scans = transport.events.filter((event) => event.type === "scan");
  assert.deepEqual(
    scans.map((event) => event.payload.data),
    ["https://example.test/1", "https://example.test/2"],
    "a code held in frame is one scan, not one per tick",
  );
  assert.equal(scans[0].key, "scan");
  assert.equal(scans[0].payload.format, "qr_code");
});

test("a scanner without BarcodeDetector says so, once, and still previews", async () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = widget(dom, "QrScanner", {}, "scan");
  const transport = mockTransport();
  const deps = fakeDeps(dom);
  const warnings = [];
  const realWarn = console.warn;
  console.warn = (message) => warnings.push(String(message));
  try {
    const cameras = installCameras(dom.root, transport, {
      document: deps.doc,
      navigator: deps.navigator,
      detector: undefined,
    });
    cameras.sync();
    await settle();
    cameras.dispose();
  } finally {
    console.warn = realWarn;
  }

  assert.equal(transport.events.length, 0, "no scan without a decoder");
  assert.ok(
    warnings.some((line) => line.includes("BarcodeDetector")),
    "the failure is said out loud, not swallowed",
  );
  assert.ok(el.querySelector('[data-tw-part="preview"]'), "the camera still shows");
});

test("a refused camera warns and leaves no video behind", async () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const el = widget(dom, "CameraPreview", { frame_interval_ms: 5 });
  const transport = mockTransport();
  const deps = fakeDeps(dom, { fail: "Permission denied" });
  const warnings = [];
  const realWarn = console.warn;
  console.warn = (message) => warnings.push(String(message));
  try {
    const cameras = installCameras(dom.root, transport, {
      document: deps.doc,
      navigator: deps.navigator,
    });
    cameras.sync();
    await settle();
    cameras.dispose();
  } finally {
    console.warn = realWarn;
  }

  assert.equal(transport.events.length, 0);
  assert.ok(warnings.some((line) => line.includes("Permission denied")));
  assert.equal(el.querySelector('[data-tw-part="preview"]'), null);
});

test("no camera API at all warns once and reports nothing", async () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  widget(dom, "CameraPreview", { frame_interval_ms: 5 });
  widget(dom, "QrScanner", {}, "scan");
  const transport = mockTransport();
  const warnings = [];
  const realWarn = console.warn;
  console.warn = (message) => warnings.push(String(message));
  try {
    const cameras = installCameras(dom.root, transport, {
      document: dom.document,
      navigator: {},
    });
    cameras.sync();
    await settle();
    cameras.dispose();
  } finally {
    console.warn = realWarn;
  }

  assert.equal(transport.events.length, 0);
  assert.equal(
    warnings.filter((line) => line.includes("no camera API")).length,
    1,
    "one warning for the page, not one per widget",
  );
});
