// native/midi.js — Web MIDI glue for the Tier-3 seam.
//
// `navigator.requestMIDIAccess({sysex})` returns a `MIDIAccess` whose input and
// output ports are keyed by id. The access object is not JSON-able, so we hold
// it in a module-level var and expose only the {id, name} of each port. `send`
// looks the output port back up by id and writes the raw byte array.

import { CapabilityError } from "./index.js";

/**
 * The live MIDIAccess, kept between `request_access` and `send`.
 * @type {any}
 */
let _access = null;

/**
 * Whether the Web MIDI API is available.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{supported:boolean}>}
 */
export async function midiIsSupported(_args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  return { supported: !!(nav && typeof nav.requestMIDIAccess === "function") };
}

/**
 * Request MIDI access and list the input/output ports.
 * @param {{sysex?:boolean}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{inputs:Array<{id:string, name:string}>, outputs:Array<{id:string, name:string}>}>}
 * @throws {CapabilityError} unavailable / failed.
 */
export async function midiRequestAccess(args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  if (!nav || typeof nav.requestMIDIAccess !== "function") {
    throw new CapabilityError("unavailable", "the Web MIDI API is not available");
  }
  try {
    _access = await nav.requestMIDIAccess({ sysex: !!args.sysex });
  } catch (err) {
    throw new CapabilityError("failed", err && err.message);
  }
  const inputs = [..._access.inputs.values()].map((p) => ({ id: p.id, name: p.name || "" }));
  const outputs = [..._access.outputs.values()].map((p) => ({ id: p.id, name: p.name || "" }));
  return { inputs, outputs };
}

/**
 * Send a raw MIDI message to an output port by id.
 * @param {{output_id:string, data:Array<number>}} args
 * @param {import("./index.js").NativeDeps} _deps
 * @returns {Promise<Object>}
 * @throws {CapabilityError} not_found / failed.
 */
export async function midiSend(args, _deps) {
  if (!_access) {
    throw new CapabilityError("not_found", "no MIDI access; call request_access first");
  }
  const port = _access.outputs.get(args.output_id);
  if (!port) {
    throw new CapabilityError("not_found", `no MIDI output for id ${args.output_id}`);
  }
  try {
    port.send(args.data);
    return {};
  } catch (err) {
    throw new CapabilityError("failed", err && err.message);
  }
}
