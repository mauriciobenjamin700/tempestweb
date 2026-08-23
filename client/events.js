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
// Pointer gestures live in client/gestures.js; `bindEvents` installs that
// recognizer so a mount still has a single entry point for input.
//
// Verify in tests/client/ with a mock transport (jsdom dispatchEvent).

import { installGestures } from "./gestures.js";
import {
  DRAG_DATA_ATTR,
  DROP_TARGET_ATTR,
  FIELD_ATTR,
  ITEM_ATTR,
  ITEM_VALUE_ATTR,
  KEY_ATTR,
  MASK_ATTR,
  PIN_LENGTH_ATTR,
  REORDER_ATTR,
  TYPE_ATTR,
} from "./dom.js";

// The DOM event names captured and their corresponding TWEvent `type`. Identity
// here, but kept explicit so the captured set is the contract, not "whatever fires".
const EVENT_TYPES = Object.freeze({
  click: "click",
  input: "input",
  change: "change",
  submit: "submit",
});

/** Widget types whose renderer-owned items report a selection. */
const MENU_TYPES = '[data-tw-type="Menu"],[data-tw-type="ActionSheet"]';

/** The overlay host, whose own surface is the scrim (a ::before on this element). */
const OVERLAY_HOST_ATTR = "data-tw-overlays";

/**
 * Overlay types a click outside — or Escape — dismisses.
 *
 * Modal overlays only: a Toast dismisses itself on a timer, and a Menu/Popover
 * has no scrim to click through, so neither belongs here.
 */
const DISMISSIBLE_TYPES =
  '[data-tw-type="Dialog"],[data-tw-type="BottomSheet"],[data-tw-type="ActionSheet"]';

/**
 * Whether this event target is the overlay host itself (i.e. the scrim).
 *
 * Duck-typed rather than `instanceof Element`: the client also runs under jsdom,
 * where the module scope has no browser `Element` to compare against.
 *
 * @param {EventTarget|null} target  The event's target.
 * @returns {boolean}                True when the target is the overlay host.
 */
function isOverlayHost(target) {
  const el = /** @type {HTMLElement|null} */ (target);
  return (
    el != null &&
    typeof el.hasAttribute === "function" &&
    el.hasAttribute(OVERLAY_HOST_ATTR)
  );
}

/**
 * Report a dismiss for the top-most modal overlay, if there is one.
 *
 * The scrim is the overlay host's own ::before, so a click on it lands on the
 * host itself — that is the signal that the user clicked *outside* the overlay.
 * Escape means the same thing. Both were inert: `on_dismiss` existed on Dialog
 * and BottomSheet and nothing ever fired it, so a scrim that looked dismissible
 * was not, and an app without its own close button trapped the user.
 *
 * The payload is empty: `DismissEvent.overlay_id` is the server's id for the
 * overlay, which the client never sees — the handler knows which overlay it is
 * on.
 *
 * @param {HTMLElement} root The delegation root.
 * @param {import("./transport.js").Transport} transport  The event sink.
 * @returns {boolean}        True when a dismiss was reported.
 */
function sendOverlayDismiss(root, transport) {
  const host = root.querySelector(`[${OVERLAY_HOST_ATTR}]`);
  if (host == null) {
    return false;
  }
  const modals = host.querySelectorAll(DISMISSIBLE_TYPES);
  const top = modals[modals.length - 1];
  const key = top == null ? null : top.getAttribute(KEY_ATTR);
  if (key == null) {
    return false;
  }
  transport.sendEvent({ type: "dismiss", key, payload: {} });
  return true;
}

/**
 * Report a click on a menu item as a `select` event, if that is what it was.
 *
 * A `Menu`/`ActionSheet` draws its `items` prop as renderer-owned buttons, so the
 * click lands on an element the IR knows nothing about. The event belongs to the
 * *menu* — that is where `on_select` lives — and carries the item's value and
 * label, which is the `MenuSelectEvent` the handler is declared against.
 *
 * @param {Event} event      The click event.
 * @param {HTMLElement} root The delegation root.
 * @param {import("./transport.js").Transport} transport  The event sink.
 * @returns {boolean}        True when the click was a menu selection.
 */
function sendMenuSelection(event, root, transport) {
  const item = closestWithAttr(event.target, root, ITEM_ATTR);
  if (item == null || item.getAttribute(ITEM_ATTR) !== "item") {
    return false;
  }
  const menu = item.closest(MENU_TYPES);
  const key = menu == null ? null : menu.getAttribute(KEY_ATTR);
  if (key == null) {
    return false;
  }
  const labelEl = item.querySelector(`[${ITEM_ATTR}="item-label"]`);
  transport.sendEvent({
    type: "select",
    key,
    payload: {
      value: item.getAttribute(ITEM_VALUE_ATTR) ?? "",
      label: (labelEl ?? item).textContent ?? "",
    },
  });
  return true;
}

/**
 * Report a filled-in `PinInput` as a `complete` event, if it just filled up.
 *
 * `on_complete` is what a code screen wants: it submits the moment the last digit
 * lands, without a button. The widget declares it and it never fired, because a
 * PinInput used to render as an empty div — there was nothing to type into.
 *
 * Reported alongside the ordinary `change`, not instead of it: the app still
 * wants each keystroke (that is what holds the value in state), and the extra
 * event is the "and now it is complete" signal. It fires only on the transition
 * *to* full — a keystroke inside an already-full field (a paste replacing it, a
 * digit typed after the cap) does not report again.
 *
 * @param {EventTarget|null} target  The input that changed.
 * @param {import("./transport.js").Transport} transport  The event sink.
 * @returns {void}
 */
function reportPinComplete(target, transport) {
  const el = /** @type {HTMLInputElement|null} */ (target);
  if (el == null || typeof el.getAttribute !== "function") {
    return;
  }
  if (el.getAttribute(TYPE_ATTR) !== "PinInput") {
    return;
  }
  const key = el.getAttribute(KEY_ATTR);
  const length = Number.parseInt(el.getAttribute(PIN_LENGTH_ATTR) ?? "", 10);
  const value = typeof el.value === "string" ? el.value : "";
  if (key == null || !Number.isFinite(length) || length <= 0) {
    return;
  }
  const full = value.length >= length;
  const wasFull = el.__twPinFull === true;
  el.__twPinFull = full;
  if (!full || wasFull) {
    return;
  }
  transport.sendEvent({ type: "complete", key, payload: { values: { value } } });
}

/**
 * Report that a `FormField` should be validated, when its control loses focus.
 *
 * `on_validate` was declared and inert: the app could only validate on submit,
 * so a form told the reader about a bad email after they had filled in six more
 * fields. The client cannot validate by itself — a field's `validators` are
 * Python callables that never cross the wire — so what it reports is the
 * *occasion*: this field, this value, please check it. The handler runs the real
 * validators and puts the message on the field's `error`.
 *
 * `focusout` and not `blur`, because only the former bubbles to the delegation
 * root; and leaving a field is the moment that does not interrupt typing.
 *
 * @param {EventTarget|null} target  The control that lost focus.
 * @param {HTMLElement} root         The delegation root.
 * @param {import("./transport.js").Transport} transport  The event sink.
 * @returns {void}
 */
function reportFieldValidation(target, root, transport) {
  const field = closestWithAttr(target, root, FIELD_ATTR);
  if (field == null) {
    return;
  }
  const key = field.getAttribute(KEY_ATTR);
  const name = field.getAttribute(FIELD_ATTR);
  if (key == null || name == null || name === "") {
    return;
  }
  const control = /** @type {HTMLInputElement|null} */ (target);
  const value = control != null && typeof control.value === "string" ? control.value : "";
  transport.sendEvent({
    type: "validate",
    key,
    payload: { field: name, value },
  });
}

/** The dataTransfer type carrying the dragged item's position within its list. */
const REORDER_MIME = "text/x-tw-reorder";

/**
 * Read a drag between a `ReorderableList`'s children as a reorder, if it is one.
 *
 * `on_reorder` was declared by the core and never fired: the HTML5 drag contract
 * existed for `Draggable`/`DragTarget`, but a reorderable list's children are
 * plain items — the list, not the item, is what declares the handler, and the
 * event it wants is a pair of positions.
 *
 * Positions are computed from the DOM at event time rather than stamped onto the
 * children: items arrive and leave through Insert/Remove patches, so any index
 * written onto a child goes stale the moment the list changes.
 *
 * @param {DragEvent} event  The dragstart / drop event.
 * @param {HTMLElement} root The delegation root.
 * @param {import("./transport.js").Transport} transport  The event sink.
 * @param {"start"|"drop"} phase  Which half of the gesture this is.
 * @returns {boolean}        True when the event belonged to a reorderable list.
 */
function handleReorder(event, root, transport, phase) {
  const item = closestChildOfReorderable(event.target, root);
  if (item == null) {
    return false;
  }
  const list = /** @type {HTMLElement} */ (item.parentElement);
  const index = Array.prototype.indexOf.call(list.children, item);
  if (phase === "start") {
    if (event.dataTransfer) {
      event.dataTransfer.setData(REORDER_MIME, String(index));
      event.dataTransfer.effectAllowed = "move";
    }
    return true;
  }
  event.preventDefault();
  const raw = event.dataTransfer ? event.dataTransfer.getData(REORDER_MIME) : "";
  const from = Number.parseInt(raw, 10);
  const key = list.getAttribute(KEY_ATTR);
  if (key == null || !Number.isFinite(from) || from === index) {
    return true;
  }
  transport.sendEvent({
    type: "reorder",
    key,
    payload: { from_index: from, to_index: index },
  });
  return true;
}

/**
 * Find the direct child of a `ReorderableList` containing `target`.
 *
 * The pointer is usually over something nested inside the item, and the item is
 * whatever child of the list that subtree hangs from.
 *
 * @param {EventTarget|null} target  The event's target.
 * @param {HTMLElement} root         The delegation root.
 * @returns {?HTMLElement}           The list item, or null.
 */
function closestChildOfReorderable(target, root) {
  let node = /** @type {Node|null} */ (target);
  while (node != null && node.nodeType !== 1) {
    node = node.parentNode;
  }
  let el = /** @type {HTMLElement|null} */ (node);
  while (el != null && el !== root) {
    const parent = el.parentElement;
    if (parent != null && parent.hasAttribute?.(REORDER_ATTR)) {
      return el;
    }
    el = parent;
  }
  return null;
}

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
 * Build the TWEvent payload for a captured DOM event.
 *
 * `input`/`change` carry the control's current `value`; other event types carry an
 * empty payload (the key alone identifies the action server-side).
 *
 * @param {string} domType   The DOM event type ("click", "input", ...).
 * @param {EventTarget|null} target  The event target.
 * @returns {{value?: string}}  The TWEvent `payload` ({ value } for input/change, else {}).
 */
/**
 * Format `raw` against a `MaskedInput`'s mask.
 *
 * The core's notation: `9` is a required digit, `A` a required letter, and every
 * other character is a fixed literal (`"999.999.999-99"`). Input characters that
 * cannot fill the next slot are dropped, and a trailing literal is only emitted
 * while there is more input to place — so a half-typed CPF reads `123.4`, not
 * `123.4..-`.
 *
 * @param {string} mask  The mask pattern.
 * @param {string} raw   What the field currently holds.
 * @returns {string}     The masked text.
 */
export function applyMask(mask, raw) {
  if (!mask) {
    return String(raw ?? "");
  }
  const chars = [...String(raw ?? "")];
  let out = "";
  let index = 0;
  for (const slot of mask) {
    if (index >= chars.length) {
      break;
    }
    if (slot === "9" || slot === "A") {
      const wanted = slot === "9" ? /[0-9]/ : /[A-Za-z]/;
      while (index < chars.length && !wanted.test(chars[index])) {
        index += 1;
      }
      if (index >= chars.length) {
        break;
      }
      out += chars[index];
      index += 1;
    } else {
      out += slot;
      if (chars[index] === slot) {
        index += 1;
      }
    }
  }
  return out;
}

/**
 * Rewrite a masked field in place, keeping the caret where the reader left it.
 *
 * The caret is re-placed by counting how many *fillable* characters precede it,
 * because the mask inserts literals: typing the sixth digit of a CPF must leave
 * the caret after `123.456`, not three characters back where the raw offset would
 * put it. A caret at the end stays at the end.
 *
 * @param {HTMLInputElement} target  The field being edited.
 * @returns {void}
 */
function reformatMasked(target) {
  const mask = target.getAttribute?.(MASK_ATTR);
  if (!mask) {
    return;
  }
  const before = String(target.value ?? "");
  const caret = target.selectionStart ?? before.length;
  const fillable = [...before.slice(0, caret)].filter((c) => /[0-9A-Za-z]/.test(c)).length;
  const masked = applyMask(mask, before);
  if (masked === before) {
    return;
  }
  target.value = masked;
  let seen = 0;
  let position = masked.length;
  for (let i = 0; i < masked.length; i += 1) {
    if (/[0-9A-Za-z]/.test(masked[i])) {
      seen += 1;
      if (seen === fillable) {
        position = i + 1;
        break;
      }
    }
  }
  target.setSelectionRange?.(position, position);
}

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
      if (domType === "click" && sendMenuSelection(event, root, transport)) {
        return;
      }
      if (domType === "click" && isOverlayHost(event.target)) {
        if (sendOverlayDismiss(root, transport)) {
          return;
        }
      }
      const key = keyedAncestor(event.target, root);
      if (key == null) {
        return;
      }
      if (domType === "input") {
        // The mask is applied before the value is read, so the app's state and
        // the field agree on what the reader sees.
        reformatMasked(event.target);
      }
      transport.sendEvent({
        type: EVENT_TYPES[domType],
        key,
        payload: payloadFor(domType, event.target),
      });
      if (domType === "input" || domType === "change") {
        reportPinComplete(event.target, transport);
      }
    };
    root.addEventListener(domType, handler);
    bound.push([domType, handler]);
  }

  /** @param {FocusEvent} event */
  const onFocusOut = (event) => {
    reportFieldValidation(event.target, root, transport);
  };
  root.addEventListener("focusout", onFocusOut);
  bound.push(["focusout", onFocusOut]);

  const bindDrag = () => {
    /** @param {DragEvent} event */
    const onDragStart = (event) => {
      if (handleReorder(event, root, transport, "start")) {
        return;
      }
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
      const overItem = closestChildOfReorderable(event.target, root) != null;
      if (!overItem && closestWithAttr(event.target, root, DROP_TARGET_ATTR) == null) {
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
      if (handleReorder(event, root, transport, "drop")) {
        return;
      }
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

  // Pointer gestures — tap / swipe / long press / double tap / pan / pinch — are
  // one recognizer in client/gestures.js, because they share one state machine:
  // the same pointerdown may become any of them, and only the pointers still
  // down decide which. Installed from here so `bindEvents` stays the single
  // entry point a mount needs.
  const gestures = installGestures(root, transport);

  /**
   * Dismiss the top-most modal overlay on Escape.
   *
   * Listened for on the document, not the mount root: an overlay rarely holds
   * focus, so the key event would never reach the root.
   * @param {KeyboardEvent} event
   */
  const onKeyDown = (event) => {
    if (event.key === "Escape") {
      sendOverlayDismiss(root, transport);
    }
  };
  const doc = root.ownerDocument;
  if (doc != null) {
    doc.addEventListener("keydown", onKeyDown);
  }

  return () => {
    for (const [domType, handler] of bound) {
      root.removeEventListener(domType, handler);
    }
    gestures.dispose();
    if (doc != null) {
      doc.removeEventListener("keydown", onKeyDown);
    }
  };
}
