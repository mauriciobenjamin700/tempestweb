// native/webauthn.js — Credential Management (WebAuthn) + Web OTP glue.
//
// WebAuthn traffics in ArrayBuffers (challenge, credential ids, attestation blobs)
// which are not JSON-able, while the wire contract carries base64url strings. So
// this module converts base64url -> ArrayBuffer on the way into `credentials.create`
// / `.get`, and ArrayBuffer -> base64url on the way back out. `get_otp` reads a
// one-time code delivered by SMS via the Web OTP API.

import { CapabilityError } from "./index.js";

/**
 * Decode a base64url string into an ArrayBuffer.
 * @param {string} b64url
 * @returns {ArrayBuffer}
 */
function base64urlToBuffer(b64url) {
  const b64 = (b64url || "").replace(/-/g, "+").replace(/_/g, "/");
  const pad = b64.length % 4 === 0 ? "" : "=".repeat(4 - (b64.length % 4));
  const binary = atob(b64 + pad);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}

/**
 * Encode an ArrayBuffer (or ArrayBufferView) as a base64url string.
 * @param {ArrayBuffer|ArrayBufferView} buffer
 * @returns {string}
 */
function bufferToBase64url(buffer) {
  const bytes = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer.buffer || buffer);
  let binary = "";
  for (let i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i]);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/**
 * Create a WebAuthn credential (registration).
 * @param {{options:Object}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{credential:Object}>}
 * @throws {CapabilityError} unavailable / failed.
 */
export async function webauthnCreate(args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  if (!nav || !nav.credentials || typeof nav.credentials.create !== "function") {
    throw new CapabilityError("unavailable", "the Credential Management API is not available");
  }
  const options = args.options || {};
  if (options.challenge) options.challenge = base64urlToBuffer(options.challenge);
  if (options.user && options.user.id) options.user.id = base64urlToBuffer(options.user.id);
  if (Array.isArray(options.excludeCredentials)) {
    options.excludeCredentials = options.excludeCredentials.map((c) => ({
      ...c,
      id: base64urlToBuffer(c.id),
    }));
  }
  let cred;
  try {
    cred = await nav.credentials.create({ publicKey: options });
  } catch (err) {
    throw new CapabilityError("failed", err && err.message);
  }
  const response = cred.response || {};
  return {
    credential: {
      id: cred.id,
      type: cred.type,
      rawId: bufferToBase64url(cred.rawId),
      response: {
        clientDataJSON: bufferToBase64url(response.clientDataJSON),
        attestationObject: bufferToBase64url(response.attestationObject),
      },
    },
  };
}

/**
 * Get a WebAuthn assertion (authentication).
 * @param {{options:Object}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{credential:Object}>}
 * @throws {CapabilityError} unavailable / failed.
 */
export async function webauthnGet(args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  if (!nav || !nav.credentials || typeof nav.credentials.get !== "function") {
    throw new CapabilityError("unavailable", "the Credential Management API is not available");
  }
  const options = args.options || {};
  if (options.challenge) options.challenge = base64urlToBuffer(options.challenge);
  if (Array.isArray(options.allowCredentials)) {
    options.allowCredentials = options.allowCredentials.map((c) => ({
      ...c,
      id: base64urlToBuffer(c.id),
    }));
  }
  let cred;
  try {
    cred = await nav.credentials.get({ publicKey: options });
  } catch (err) {
    throw new CapabilityError("failed", err && err.message);
  }
  const response = cred.response || {};
  const serialized = {
    clientDataJSON: bufferToBase64url(response.clientDataJSON),
    authenticatorData: bufferToBase64url(response.authenticatorData),
    signature: bufferToBase64url(response.signature),
  };
  if (response.userHandle) serialized.userHandle = bufferToBase64url(response.userHandle);
  return {
    credential: {
      id: cred.id,
      type: cred.type,
      rawId: bufferToBase64url(cred.rawId),
      response: serialized,
    },
  };
}

/**
 * Read a one-time code delivered over SMS via the Web OTP API.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{code:string}>}
 * @throws {CapabilityError} unavailable / failed.
 */
export async function webauthnGetOtp(_args, deps) {
  const nav = deps.navigator || /** @type {any} */ (globalThis).navigator;
  if (!nav || !nav.credentials || typeof nav.credentials.get !== "function") {
    throw new CapabilityError("unavailable", "the Web OTP API is not available");
  }
  let cred;
  try {
    cred = await nav.credentials.get({ otp: { transport: ["sms"] } });
  } catch (err) {
    throw new CapabilityError("failed", err && err.message);
  }
  return { code: cred.code };
}
