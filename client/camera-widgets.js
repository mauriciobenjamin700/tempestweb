// camera-widgets.js — the two widgets that need a live camera.
//
// Named apart from client/native/camera.js on purpose: that one is the *capability*
// (`await native.camera.capture()`, one photo on demand), this one is the pair of
// widgets that hold a stream open while they are on screen.
//
// `CameraPreview` declares `facing`, `frame_interval_ms` and `on_frame`;
// `QrScanner` declares `on_scan`. Both rendered as empty boxes: no stream, no
// preview, and two handlers the core declared that could never fire.
//
// Both widgets are IR leaves, so the renderer owns what goes inside them — a
// `<video>` playing the stream, exactly like a ProgressBar owns its fill. The
// stream is opened when the widget appears and stopped when it goes away, which
// matters more here than for most resources: a camera left open is a light left
// on, on someone's phone.
//
// What each one reports:
//
//   * a preview samples the video into an offscreen canvas every
//     `frame_interval_ms` and sends `{width, height, data, rotation}` with the
//     frame as a base64 JPEG — the `CameraFrameEvent` the core declares;
//   * a scanner runs the platform's own `BarcodeDetector` over the same video and
//     sends `{data, format}` when it reads a code, skipping repeats of the code
//     it just read.
//
// `BarcodeDetector` is Chrome/Android only. There is no fallback, deliberately:
// the alternative is bundling a decoder, and this client ships no runtime
// dependencies. Where it is missing the scanner says so once, in the console, and
// stays a preview — which is the honest failure, not a silent one.
//
// Everything the browser provides arrives through `deps`, so the pipeline is
// testable in jsdom (which has neither a camera nor a canvas).

/** Attribute marking a widget whose stream this module owns. */
const CAMERA_ATTR = "data-tw-camera";

/** Attribute holding a preview's sampling interval, in milliseconds. */
const INTERVAL_ATTR = "data-tw-frame-interval";

/** Attribute holding which camera a preview asked for (`front` / `back`). */
const FACING_ATTR = "data-tw-facing";

/** How often a scanner looks for a code, in milliseconds. */
const SCAN_INTERVAL_MS = 250;

/** The JPEG quality frames are encoded at: small enough to send, good enough to read. */
const FRAME_QUALITY = 0.7;

/**
 * Map the core's `facing` value onto a getUserMedia constraint.
 *
 * @param {?string} facing  The widget's `facing` prop (`front` / `back`).
 * @returns {string}        The `facingMode` constraint.
 */
function facingMode(facing) {
  return facing === "front" ? "user" : "environment";
}

/**
 * Install camera plumbing for every preview and scanner under `root`.
 *
 * `sync()` reconciles streams with the widgets a patch batch left mounted: a new
 * widget gets a stream, a removed one has its tracks stopped. It is called from
 * mount's post-layout pass, for the same reason the focus trap is: the mount
 * already knows when the tree changed.
 *
 * @param {HTMLElement} root  The mount root.
 * @param {import("./transport.js").Transport} transport  The event sink.
 * @param {{navigator?: Navigator, document?: Document, detector?: Function}} [deps]
 *        Browser seams, injectable for tests.
 * @returns {{sync: () => void, dispose: () => void}}
 */
export function installCameras(root, transport, deps = {}) {
  const nav = deps.navigator ?? globalThis.navigator;
  const doc = deps.document ?? globalThis.document;
  const Detector = deps.detector ?? globalThis.BarcodeDetector;

  /** Live per-element state. @type {Map<HTMLElement, Object>} */
  const live = new Map();
  let warnedNoDetector = false;
  let warnedNoCamera = false;

  /**
   * Complain once about a missing browser capability.
   *
   * A camera widget that silently shows nothing is the worst outcome: the app
   * looks broken and the reason (no permission, no API, not HTTPS) is invisible.
   *
   * @param {string} message  What is missing.
   * @returns {void}
   */
  const warnOnce = (message) => {
    if (typeof console !== "undefined" && console.warn) {
      console.warn(`tempestweb: ${message}`);
    }
  };

  /**
   * Stop a widget's stream and timers, and forget it.
   *
   * @param {HTMLElement} el  The camera widget.
   * @returns {void}
   */
  const teardown = (el) => {
    const state = live.get(el);
    if (state === undefined) {
      return;
    }
    live.delete(el);
    if (state.timer !== null) {
      clearInterval(state.timer);
    }
    for (const track of state.stream?.getTracks?.() ?? []) {
      track.stop();
    }
  };

  /**
   * Sample the current video frame and report it.
   *
   * @param {HTMLElement} el  The preview widget.
   * @returns {void}
   */
  const reportFrame = (el) => {
    const state = live.get(el);
    if (state == null || state.video == null) {
      return;
    }
    const width = state.video.videoWidth || 0;
    const height = state.video.videoHeight || 0;
    if (width === 0 || height === 0) {
      return;
    }
    const canvas = state.canvas;
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext?.("2d");
    if (context == null) {
      return;
    }
    context.drawImage(state.video, 0, 0, width, height);
    const url = canvas.toDataURL("image/jpeg", FRAME_QUALITY);
    transport.sendEvent({
      type: "frame",
      key: state.key,
      payload: {
        width,
        height,
        // The base64 payload only, without the `data:` prefix: the core's field
        // is the frame's bytes, and the mime type is already fixed here.
        data: String(url).split(",")[1] ?? "",
        rotation: 0,
      },
    });
  };

  /**
   * Look for a code in the current video frame and report a new one.
   *
   * @param {HTMLElement} el  The scanner widget.
   * @returns {Promise<void>}
   */
  const scanOnce = async (el) => {
    const state = live.get(el);
    if (state == null || state.detector == null || state.video == null) {
      return;
    }
    let codes = [];
    try {
      codes = await state.detector.detect(state.video);
    } catch {
      // A detect() that throws mid-stream (a frame the decoder cannot use) is
      // normal; the next tick tries again.
      return;
    }
    const first = codes?.[0];
    const value = first?.rawValue;
    if (typeof value !== "string" || value === "") {
      return;
    }
    if (value === state.lastCode) {
      // The same code stays in frame for many ticks; reporting it every 250ms
      // would turn one scan into dozens of handler calls.
      return;
    }
    state.lastCode = value;
    transport.sendEvent({
      type: "scan",
      key: state.key,
      payload: { data: value, format: first?.format ?? "qr_code" },
    });
  };

  /**
   * Open a stream for a newly mounted camera widget.
   *
   * @param {HTMLElement} el  The camera widget.
   * @param {boolean} scanner Whether this widget is a QrScanner.
   * @returns {Promise<void>}
   */
  const setup = async (el, scanner) => {
    const key = el.getAttribute("data-tw-key");
    if (key == null) {
      return;
    }
    if (nav?.mediaDevices?.getUserMedia == null) {
      if (!warnedNoCamera) {
        warnedNoCamera = true;
        warnOnce("no camera API available (needs a secure context)");
      }
      return;
    }
    const video = doc.createElement("video");
    video.setAttribute("data-tw-part", "preview");
    video.muted = true;
    video.autoplay = true;
    video.playsInline = true;
    el.appendChild(video);

    const state = {
      key,
      video,
      canvas: doc.createElement("canvas"),
      stream: null,
      timer: null,
      detector: null,
      lastCode: null,
    };
    live.set(el, state);

    let stream;
    try {
      stream = await nav.mediaDevices.getUserMedia({
        video: { facingMode: facingMode(el.getAttribute(FACING_ATTR)) },
        audio: false,
      });
    } catch (error) {
      warnOnce(`camera unavailable: ${error?.message ?? error}`);
      teardown(el);
      video.remove();
      return;
    }
    // The widget may have been removed while permission was being decided.
    if (!live.has(el)) {
      for (const track of stream.getTracks()) {
        track.stop();
      }
      return;
    }
    state.stream = stream;
    video.srcObject = stream;
    await video.play?.().catch(() => {});

    if (scanner) {
      if (typeof Detector !== "function") {
        if (!warnedNoDetector) {
          warnedNoDetector = true;
          warnOnce(
            "BarcodeDetector is unavailable in this browser, so QrScanner shows " +
              "the camera but cannot read codes",
          );
        }
        return;
      }
      state.detector = new Detector({ formats: ["qr_code"] });
      state.timer = setInterval(() => void scanOnce(el), SCAN_INTERVAL_MS);
      return;
    }
    const declared = Number.parseInt(el.getAttribute(INTERVAL_ATTR) ?? "", 10);
    const interval = Number.isFinite(declared) && declared > 0 ? declared : 300;
    state.timer = setInterval(() => reportFrame(el), interval);
  };

  /** Reconcile open streams with the widgets currently mounted. */
  const sync = () => {
    const mounted = new Set();
    for (const node of root.querySelectorAll(`[${CAMERA_ATTR}]`)) {
      const el = /** @type {HTMLElement} */ (node);
      mounted.add(el);
      if (!live.has(el)) {
        void setup(el, el.getAttribute(CAMERA_ATTR) === "scanner");
      }
    }
    for (const el of [...live.keys()]) {
      if (!mounted.has(el)) {
        teardown(el);
      }
    }
  };

  return {
    sync,
    dispose() {
      for (const el of [...live.keys()]) {
        teardown(el);
      }
    },
  };
}
