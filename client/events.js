// events.js — capture DOM events and route them through a transport.  PHASE W3.
//
// bindEvents(root, transport) installs delegated listeners on `root` so that a
// click on a keyed element (e.g. a Button) calls
//   transport.sendEvent({ type: "click", key, payload })
// reading the widget key from the `data-tw-key` attribute set by dom.js. It maps
// the DOM events click/input/change/submit onto the TWEvent shape in transport.js.
// Delegation means a single listener per event type survives patch churn (children
// are added/removed/replaced without rebinding). The same delegation carries the
// HTML5 drag contract: a `Draggable`'s dragstart puts its payload on the
// dataTransfer and emits `drag`, and a `DragTarget`'s drop emits `drop` with the
// payload it received.
//
// Verify in tests/client/ with a mock transport (jsdom dispatchEvent).

import { GESTURE_TYPE, LONG_PRESS_MS, SWIPE_MIN_PX } from "./constants.js";
import { DRAG_DATA_ATTR, DROP_TARGET_ATTR, KEY_ATTR, TYPE_ATTR } from "./dom.js";

// The DOM event names captured and their corresponding TWEvent `type`. Identity
// here, but kept explicit so the captured set is the contract, not "whatever fires".
const EVENT_TYPES = Object.freeze({
  click: "click",
  input: "input",
  change: "change",
  submit: "submit",
});

/** The dataTransfer type carrying a `Draggable`'s payload across a drag. */
const DRAG_MIME = "text/plain";

/**
 * Find the nearest ancestor-or-self element carrying `attr`.
 *
 * The drag listeners need the element that declared the *role* (the `Draggable`
 * that owns the payload, the `DragTarget` that accepts the drop), which is
 * usually an ancestor of whatever the pointer was actually over.
 *
 * @param {EventTarget|null} target  The event's target node.
 * @param {HTMLElement} root         The delegation root (search stops above it).
 * @param {string} attr              The attribute to look for.
 * @returns {?HTMLElement}           The element, or null when none has it.
 */
function closestWithAttr(target, root, attr) {
  let node = /** @type {Node|null} */ (target);
  while (node != null && node.nodeType !== 1) {
    node = node.parentNode;
  }
  let el = /** @type {HTMLElement|null} */ (node);
  while (el != null) {
    if (el.hasAttribute && el.hasAttribute(attr)) {
      return el;
    }
    if (el === root) {
      break;
    }
    el = el.parentElement;
  }
  return null;
}

/**
 * Build the wire payload for a drag/drop event (a core `DragEvent`).
 *
 * @param {DragEvent} event  The DOM drag event.
 * @param {string} data      The `Draggable`'s payload string.
 * @returns {{data: string, x: number, y: number}}  The wire payload.
 */
function dragPayload(event, data) {
  return { data, x: event.clientX ?? 0, y: event.clientY ?? 0 };
}

/**
 * Find the nearest ancestor-or-self element carrying a widget key.
 *
 * Delegation fires on the deepest target; the keyed widget may be that element or
 * an ancestor (e.g. a click lands on text inside a keyed Button). Walks up until a
 * `data-tw-key` is found or the delegation root is passed.
 *
 * @param {EventTarget|null} target  The event's target node.
 * @param {HTMLElement} root         The delegation root (search stops above it).
 * @returns {?string}                The widget key, or null when none is keyed.
 */
function keyedAncestor(target, root) {
  let node = /** @type {Node|null} */ (target);
  while (node != null && node.nodeType !== 1) {
    node = node.parentNode;
  }
  let el = /** @type {HTMLElement|null} */ (node);
  while (el != null) {
    if (el.hasAttribute && el.hasAttribute(KEY_ATTR)) {
      return el.getAttribute(KEY_ATTR);
    }
    if (el === root) {
      break;
    }
    el = el.parentElement;
  }
  return null;
}

/**
 * Find the nearest ancestor-or-self GestureDetector element (keyed + typed).
 *
 * @param {EventTarget|null} target  The event's target node.
 * @param {HTMLElement} root         The delegation root.
 * @returns {?string}                The gesture widget's key, or null.
 */
function gestureAncestor(target, root) {
  let node = /** @type {Node|null} */ (target);
  while (node != null && node.nodeType !== 1) {
    node = node.parentNode;
  }
  let el = /** @type {HTMLElement|null} */ (node);
  while (el != null) {
    if (
      el.getAttribute &&
      el.getAttribute(TYPE_ATTR) === GESTURE_TYPE &&
      el.hasAttribute(KEY_ATTR)
    ) {
      return el.getAttribute(KEY_ATTR);
    }
    if (el === root) {
      break;
    }
    el = el.parentElement;
  }
  return null;
}

/**
 * Classify a completed pointer interaction into a gesture TWEvent.
 *
 * Swipe wins when travel crosses `SWIPE_MIN_PX` (direction from the dominant
 * axis); otherwise a hold past `LONG_PRESS_MS` is a long press, and a quick
 * release is a tap. Coordinates are the press origin.
 *
 * @param {{x:number, y:number, t:number}} start  The pointerdown origin.
 * @param {{x:number, y:number, t:number}} end    The pointerup point.
 * @returns {{type:string, payload:Object}}        The gesture type + payload.
 */
function classifyGesture(start, end) {
  const dx = Math.round(end.x - start.x);
  const dy = Math.round(end.y - start.y);
  const dist = Math.hypot(dx, dy);
  if (dist >= SWIPE_MIN_PX) {
    const horizontal = Math.abs(dx) >= Math.abs(dy);
    const direction = horizontal
      ? dx > 0
        ? "right"
        : "left"
      : dy > 0
        ? "down"
        : "up";
    return { type: "swipe", payload: { direction, dx, dy } };
  }
  if (end.t - start.t >= LONG_PRESS_MS) {
    return { type: "long_press", payload: { x: Math.round(start.x), y: Math.round(start.y) } };
  }
  return { type: "tap", payload: { x: Math.round(start.x), y: Math.round(start.y) } };
}

/**
 * Build the TWEvent payload for a captured DOM event.
 *
 * `input`/`change` carry the control's current `value`; other event types carry an
 * empty payload (the key alone identifies the action server-side).
 *
 * @param {string} domType   The DOM event type ("click", "input", ...).
 * @param {EventTarget|null} target  The event target.
 * @returns {{value?: string}}  The TWEvent `payload` ({ value } for input/change, else {}).
 */
function payloadFor(domType, target) {
  if (domType === "input" || domType === "change") {
    const value = target && "value" in target ? target.value : undefined;
    if (value !== undefined) {
      return { value };
    }
  }
  return {};
}

/**
 * Bind delegated DOM event listeners on `root` that forward to the transport.
 *
 * One listener per captured event type is attached to `root`; each resolves the
 * originating widget key by walking up to the nearest `data-tw-key`, and — when a
 * keyed widget owns the event — calls `transport.sendEvent` with the TWEvent.
 * Events on unkeyed elements are ignored (no key = nothing for Python to resolve).
 *
 * Gesture recognition pairs a pointerdown over a GestureDetector with its
 * pointerup to emit tap / swipe / long_press, tracked per pointerId so overlapping
 * pointers don't clobber each other.
 *
 * @param {HTMLElement} root  The mounted root element to delegate from.
 * @param {import("./transport.js").Transport} transport  The event sink.
 * @returns {() => void}      An unbind function that removes every listener.
 */
export function bindEvents(root, transport) {
  /** @type {Array<[string, (event: Event) => void]>} */
  const bound = [];
  for (const domType of Object.keys(EVENT_TYPES)) {
    /** @param {Event} event */
    const handler = (event) => {
      const key = keyedAncestor(event.target, root);
      if (key == null) {
        return;
      }
      transport.sendEvent({
        type: EVENT_TYPES[domType],
        key,
        payload: payloadFor(domType, event.target),
      });
    };
    root.addEventListener(domType, handler);
    bound.push([domType, handler]);
  }

  const bindDrag = () => {
    /** @param {DragEvent} event */
    const onDragStart = (event) => {
      const source = closestWithAttr(event.target, root, DRAG_DATA_ATTR);
      if (source == null) {
        return;
      }
      const data = source.getAttribute(DRAG_DATA_ATTR) ?? "";
      if (event.dataTransfer) {
        event.dataTransfer.setData(DRAG_MIME, data);
        event.dataTransfer.effectAllowed = "move";
      }
      const key = source.getAttribute(KEY_ATTR);
      if (key != null) {
        transport.sendEvent({ type: "drag", key, payload: dragPayload(event, data) });
      }
    };

    /** @param {DragEvent} event */
    const onDragOver = (event) => {
      if (closestWithAttr(event.target, root, DROP_TARGET_ATTR) == null) {
        return;
      }
      // Without this the browser refuses the drop and no `drop` ever fires.
      event.preventDefault();
      if (event.dataTransfer) {
        event.dataTransfer.dropEffect = "move";
      }
    };

    /** @param {DragEvent} event */
    const onDrop = (event) => {
      const target = closestWithAttr(event.target, root, DROP_TARGET_ATTR);
      if (target == null) {
        return;
      }
      event.preventDefault();
      const data = event.dataTransfer ? event.dataTransfer.getData(DRAG_MIME) : "";
      const key = target.getAttribute(KEY_ATTR);
      if (key != null) {
        transport.sendEvent({ type: "drop", key, payload: dragPayload(event, data) });
      }
    };

    root.addEventListener("dragstart", onDragStart);
    root.addEventListener("dragover", onDragOver);
    root.addEventListener("drop", onDrop);
    bound.push(
      ["dragstart", onDragStart],
      ["dragover", onDragOver],
      ["drop", onDrop],
    );
  };
  bindDrag();

  /** @type {Map<number, {key: string, x: number, y: number, t: number}>} */
  const pending = new Map();
  const now = () => (globalThis.performance?.now?.() ?? 0);

  /** @param {PointerEvent} event */
  const onPointerDown = (event) => {
    const key = gestureAncestor(event.target, root);
    if (key == null) {
      return;
    }
    pending.set(event.pointerId, { key, x: event.clientX, y: event.clientY, t: now() });
  };
  /** @param {PointerEvent} event */
  const onPointerUp = (event) => {
    const start = pending.get(event.pointerId);
    if (start === undefined) {
      return;
    }
    pending.delete(event.pointerId);
    const { type, payload } = classifyGesture(start, {
      x: event.clientX,
      y: event.clientY,
      t: now(),
    });
    transport.sendEvent({ type, key: start.key, payload });
  };
  root.addEventListener("pointerdown", onPointerDown);
  root.addEventListener("pointerup", onPointerUp);
  bound.push(["pointerdown", onPointerDown], ["pointerup", onPointerUp]);

  return () => {
    for (const [domType, handler] of bound) {
      root.removeEventListener(domType, handler);
    }
  };
}
