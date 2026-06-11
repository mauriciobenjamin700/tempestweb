// events.js — capture DOM events and route them through a transport.  PHASE W3.
//
// bindEvents(root, transport) installs delegated listeners on `root` so that a
// click on a keyed element (e.g. a Button) calls
//   transport.sendEvent({ type: "click", key, payload })
// reading the widget key from the `data-tw-key` attribute set by dom.js. It maps
// the DOM events click/input/change/submit onto the TWEvent shape in transport.js.
// Delegation means a single listener per event type survives patch churn (children
// are added/removed/replaced without rebinding).
//
// Verify in tests/client/ with a mock transport (jsdom dispatchEvent).

import { KEY_ATTR } from "./dom.js";

// The DOM event names captured and their corresponding TWEvent `type`. Identity
// here, but kept explicit so the captured set is the contract, not "whatever fires".
const EVENT_TYPES = Object.freeze({
  click: "click",
  input: "input",
  change: "change",
  submit: "submit",
});

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
  return () => {
    for (const [domType, handler] of bound) {
      root.removeEventListener(domType, handler);
    }
  };
}
