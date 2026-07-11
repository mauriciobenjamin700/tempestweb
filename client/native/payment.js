// native/payment.js — Payment Request API glue for the Tier-3 seam.
//
// `new PaymentRequest(methods, details, options).show()` opens the browser's
// payment sheet. On success we complete the request and serialize the response
// fields Python cares about. A user-dismiss surfaces as an AbortError, mapped to
// `cancelled`.

import { CapabilityError } from "./index.js";

/**
 * Whether the Payment Request API is available.
 * @param {Object} _args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{supported:boolean}>}
 */
export async function paymentIsSupported(_args, deps) {
  const win = deps.window || /** @type {any} */ (globalThis);
  return { supported: !!(win && win.PaymentRequest) };
}

/**
 * Open the payment sheet and return the completed response.
 * @param {{methods:Array<Object>, details:Object, options?:Object}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{response:Object}>}
 * @throws {CapabilityError} unavailable / cancelled / failed.
 */
export async function paymentRequest(args, deps) {
  const win = deps.window || /** @type {any} */ (globalThis);
  const PaymentRequestCtor = win && win.PaymentRequest;
  if (typeof PaymentRequestCtor !== "function") {
    throw new CapabilityError("unavailable", "the Payment Request API is not available");
  }
  try {
    const pr = new PaymentRequestCtor(args.methods, args.details, args.options || {});
    const resp = await pr.show();
    await resp.complete("success");
    return {
      response: {
        method_name: resp.methodName,
        details: resp.details,
        payer_name: resp.payerName || "",
        payer_email: resp.payerEmail || "",
        shipping_address: resp.shippingAddress || null,
      },
    };
  } catch (err) {
    if (err && err.name === "AbortError") {
      throw new CapabilityError("cancelled", err.message);
    }
    throw new CapabilityError("failed", err && err.message);
  }
}
