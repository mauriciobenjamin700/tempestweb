// offline-codec.test.js — the optional storage codec, and the compatibility
// that makes turning it on safe.
//
// The case that matters is not "deflate round-trips" — it is that DECODING IS
// ALWAYS ON while encoding is opt-in. A record written before the codec existed
// must stay readable after it is switched on, and a record written while it was
// on must stay readable after it is switched off. Without both, flipping the
// option wipes the cache of everyone already in the field, silently.

import assert from "node:assert/strict";
import test from "node:test";
import "./setup.js";

import {
  CODEC_DEFLATE,
  CODEC_JSON,
  CODEC_MARKER,
  decodeValue,
  encodeValue,
  isCodecSupported,
  isEncoded,
  resolveCodec,
} from "../../client/offline/codec.js";

const CATALOGUE = JSON.stringify(
  Array.from({ length: 400 }, (_, i) => ({
    id: i,
    sku: `SKU-${String(i).padStart(6, "0")}`,
    nome: "camiseta algodao preto",
    preco: 79.9,
    ativo: true,
  })),
);

test("json stores the string as it is", async () => {
  assert.equal(await encodeValue("olá", CODEC_JSON), "olá");
  assert.equal(isEncoded("olá"), false);
});

test("deflate round-trips, accents included", async () => {
  const packed = await encodeValue("São Paulo — ação", CODEC_DEFLATE);
  assert.equal(isEncoded(packed), true);
  assert.equal(packed[CODEC_MARKER], CODEC_DEFLATE);
  assert.equal(await decodeValue(packed), "São Paulo — ação");
});

test("deflate actually shrinks a repetitive payload", async () => {
  const packed = await encodeValue(CATALOGUE, CODEC_DEFLATE);
  const raw = new TextEncoder().encode(CATALOGUE).length;
  assert.ok(
    packed.bytes.length < raw / 4,
    `expected < ${raw / 4} bytes, got ${packed.bytes.length}`,
  );
  assert.equal(await decodeValue(packed), CATALOGUE);
});

test("a value written before the codec existed stays readable", async () => {
  // exactly what an old record looks like: a bare string
  assert.equal(await decodeValue("escrito sem codec"), "escrito sem codec");
});

test("a value written under the codec stays readable after it is turned off", async () => {
  const packed = await encodeValue("escrito com codec", CODEC_DEFLATE);
  // the reader never consults the configured codec — the envelope names it
  assert.equal(await decodeValue(packed), "escrito com codec");
});

test("an absent key decodes to null, not to a crash", async () => {
  assert.equal(await decodeValue(undefined), null);
  assert.equal(await decodeValue(null), null);
});

test("an envelope naming an unknown codec reads as a miss, not a throw", async () => {
  const alien = { [CODEC_MARKER]: "brotli-from-the-future", bytes: new Uint8Array([1]) };
  assert.equal(await decodeValue(alien), null);
});

test("corrupt bytes read as a miss, not a throw", async () => {
  const corrupt = { [CODEC_MARKER]: CODEC_DEFLATE, bytes: new Uint8Array([1, 2, 3]) };
  assert.equal(await decodeValue(corrupt), null);
});

test("json is always supported and deflate is asked about, never assumed", () => {
  assert.equal(isCodecSupported(CODEC_JSON), true);
  assert.equal(
    isCodecSupported(CODEC_DEFLATE),
    typeof CompressionStream !== "undefined",
  );
  assert.equal(isCodecSupported("brotli"), false);
});

test("an unsupported codec resolves to json instead of throwing", () => {
  assert.equal(resolveCodec("brotli"), CODEC_JSON);
  assert.equal(resolveCodec(""), CODEC_JSON);
  assert.equal(resolveCodec(CODEC_JSON), CODEC_JSON);
});

test("encoding falls back to the plain string when compression is impossible", async () => {
  const saved = globalThis.CompressionStream;
  delete globalThis.CompressionStream;
  try {
    assert.equal(await encodeValue("sem stream", CODEC_DEFLATE), "sem stream");
    assert.equal(resolveCodec(CODEC_DEFLATE), CODEC_JSON);
  } finally {
    globalThis.CompressionStream = saved;
  }
});
