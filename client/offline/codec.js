// codec.js — optional compression for values stored in IndexedDB.  PHASE R4.
//
// Pure JS, no build step, no dependency: `CompressionStream` is a browser API.
//
// WHY THIS IS OPT-IN, WITH THE NUMBERS THAT DECIDED IT (Chrome 150, measured):
//
// IndexedDB already compresses what it stores. A 977 KB catalogue lands as
// 222 KB on disk without any codec — the storage layer squeezed it 4.4x on its
// own. So a codec here is not competing with raw text, it is competing with
// LevelDB, and the real saving is what is left after that:
//
//   catalogue, 5.000 rows   222.1 KB -> 122.1 KB   -45.0%
//   very repetitive history  64.1 KB ->  22.6 KB   -64.8%
//   random base64 noise     126.5 KB ->  95.0 KB   -24.9%
//
// The cost, with the CPU throttled 6x to approximate a weak device, is the whole
// round trip an app pays (stringify + encode + deflate, and back):
//
//   ~1 MB payload    read +12.4 ms    write +75.8 ms
//   ~4 MB payload    read +33.8 ms    write +295.1 ms
//
// Reading is cheap enough to be worth it; writing 4 MB on a weak device drops a
// frame you can see. Hence: default off, on by an explicit call, and the numbers
// in the docs so nobody turns it on by reflex.
//
// DECODING IS ALWAYS ON. Only encoding is opt-in. A record written while the
// codec was active stays readable after it is turned off, and a record written
// before it was ever turned on stays readable after — otherwise enabling the
// option would wipe the cache of everyone already in the field.

/** The codec that stores values as they are. Always available. */
export const CODEC_JSON = "json";

/** The codec that deflates values. Needs `CompressionStream`. */
export const CODEC_DEFLATE = "deflate";

/** Every codec name this module accepts. */
export const CODECS = [CODEC_JSON, CODEC_DEFLATE];

/**
 * The marker naming an encoded envelope.
 *
 * Deliberately unlikely to collide with an application field, because the
 * decoder decides whether a stored value is an envelope by looking for it.
 */
export const CODEC_MARKER = "$twcodec";

/**
 * Report whether a codec can actually run here.
 *
 * `CompressionStream` shipped in Safari 16.4; a device below that is a real
 * device an app has to keep working on. Asking rather than assuming is what
 * turns "the store is empty now" into "the codec stayed off".
 *
 * @param {string} codec  The codec name.
 * @returns {boolean} Whether it is usable in this runtime.
 */
export function isCodecSupported(codec) {
  if (codec === CODEC_JSON) return true;
  if (codec !== CODEC_DEFLATE) return false;
  return (
    typeof CompressionStream !== "undefined" &&
    typeof DecompressionStream !== "undefined"
  );
}

/**
 * Resolve the codec that will actually be used.
 *
 * @param {string} requested  What the app asked for.
 * @returns {string} The requested codec when it is supported, otherwise
 *          {@link CODEC_JSON} — never a throw, because falling back to storing
 *          plain text is a working store and an exception is a dead screen.
 */
export function resolveCodec(requested) {
  if (!CODECS.includes(requested)) return CODEC_JSON;
  return isCodecSupported(requested) ? requested : CODEC_JSON;
}

/**
 * Report whether a stored value is an encoded envelope.
 *
 * @param {*} value  Whatever came out of the store.
 * @returns {boolean} Whether it needs decoding.
 */
export function isEncoded(value) {
  return (
    value !== null &&
    typeof value === "object" &&
    typeof value[CODEC_MARKER] === "string"
  );
}

/**
 * Encode a string for storage under a codec.
 *
 * @param {string} content  The value to store.
 * @param {string} codec    The codec name.
 * @returns {Promise<*>} The value to hand IndexedDB: the string itself under
 *          {@link CODEC_JSON}, an envelope otherwise. A compression failure
 *          falls back to the plain string rather than losing the write.
 */
export async function encodeValue(content, codec) {
  if (codec !== CODEC_DEFLATE || !isCodecSupported(CODEC_DEFLATE)) {
    return content;
  }
  try {
    const bytes = new TextEncoder().encode(content);
    const packed = await through(bytes, new CompressionStream(CODEC_DEFLATE));
    return { [CODEC_MARKER]: CODEC_DEFLATE, bytes: packed };
  } catch {
    return content;
  }
}

/**
 * Decode a stored value, whatever codec wrote it.
 *
 * Always called, never gated on the configured codec: that is what makes the
 * read path compatible in both directions.
 *
 * @param {*} value  Whatever came out of the store.
 * @returns {Promise<?string>} The original string, or null when the envelope
 *          names a codec this runtime cannot read — a caller treats that as a
 *          cache miss, which is recoverable, rather than as a crash.
 */
export async function decodeValue(value) {
  if (value === undefined || value === null) return null;
  if (!isEncoded(value)) return typeof value === "string" ? value : String(value);
  if (value[CODEC_MARKER] !== CODEC_DEFLATE) return null;
  if (!isCodecSupported(CODEC_DEFLATE)) return null;
  try {
    const bytes = await through(
      value.bytes,
      new DecompressionStream(CODEC_DEFLATE),
    );
    return new TextDecoder().decode(bytes);
  } catch {
    return null;
  }
}

/**
 * Push bytes through a transform stream and collect the result.
 *
 * @param {Uint8Array|ArrayBuffer} bytes  The input.
 * @param {TransformStream} transform     The compression or decompression stream.
 * @returns {Promise<Uint8Array>} The transformed bytes.
 */
async function through(bytes, transform) {
  const stream = new Blob([bytes]).stream().pipeThrough(transform);
  return new Uint8Array(await new Response(stream).arrayBuffer());
}
