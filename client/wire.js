// wire.js — decoding the text Python hands a transport.
//
// Every transport receives its frames as text: Mode A crosses `pyodide.ffi` as a
// JSON string on purpose (no proxy conversion), and Mode B reads
// `MessageEvent.data` off a WebSocket or an EventSource. Decoding that text is
// the transport's job, and it is the first place a frame can be lost.
//
// It used to be lost silently. Each transport called `JSON.parse` bare, so a
// frame Python could not encode (a non-finite float, which the encoder wrote as
// the bare token `NaN`) threw out of the message handler: the batch vanished
// before the renderer, before any diagnostic, and Python's baseline had already
// moved past it — so the next tick addressed nodes the client never received
// (`patch path out of range`, issue #160). This module gives the three
// transports one decode with one repair policy.

/**
 * Create the decoder a transport runs over every frame it receives.
 *
 * A frame that cannot be decoded is the same failure as a patch that cannot be
 * applied: the client's tree is now behind Python's, and the repair is the same
 * single resync (one root replace to start over from).
 *
 * The resync is requested **once per run of undecodable frames**, cleared by the
 * next frame that decodes. A payload Python cannot encode comes back identical
 * in the resync it triggers, so requesting one per failure would spin.
 *
 * @param {() => void} requestResync  The transport's repair request.
 * @param {string} label  Transport name, used in the console message.
 * @returns {(text: string) => {ok: boolean, value?: any}} The decoder. On
 *          success `{ok: true, value}`; on failure `{ok: false}`, already logged
 *          and repaired.
 */
export function createWireDecoder(requestResync, label) {
  let resyncPending = false;
  return (text) => {
    let value;
    try {
      value = JSON.parse(text);
    } catch (error) {
      if (typeof console !== "undefined" && console.error) {
        const size = typeof text === "string" ? `${text.length} chars` : typeof text;
        console.error(
          `tempestweb: ${label} could not decode a frame from Python (${size}); ` +
            "the batch it carried is lost. Asking for a resync.",
          error,
        );
      }
      if (!resyncPending) {
        resyncPending = true;
        requestResync();
      }
      return { ok: false };
    }
    resyncPending = false;
    return { ok: true, value };
  };
}
