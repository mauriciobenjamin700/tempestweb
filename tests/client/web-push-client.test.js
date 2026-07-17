// Tests for client/push/web-push-client.js — P3 browser subscription flow.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  WebPushClient,
  isPushSupported,
  getPermission,
  urlBase64ToUint8Array,
  getActivePushEndpoint,
  setActivePushEndpoint,
} from "../../client/push/web-push-client.js";

const VAPID =
  "N1TyATA5i_5V6M2NWQgNhb2bzMskKIwze0sYaov_8gZP4duwEs-iGPlqE99PjyVXWW5fqjH0giO94g8g0K1uklM";

/** A fake PushSubscription. */
function fakeSubscription(endpoint = "https://push.example/abc") {
  return {
    endpoint,
    toJSON: () => ({ endpoint, keys: { p256dh: "p", auth: "a" } }),
    unsubscribe: async () => true,
  };
}

/** A fake SW registration with a controllable pushManager. */
function fakeRegistration({ existing = null } = {}) {
  let current = existing;
  return {
    pushManager: {
      getSubscription: async () => current,
      subscribe: async () => {
        current = fakeSubscription();
        return current;
      },
    },
    _set(sub) {
      current = sub;
    },
  };
}

/** A fake Notification with a settable permission and a request stub. */
function fakeNotification(permission, requestResult) {
  return {
    permission,
    requestPermission: async () => requestResult ?? "granted",
  };
}

test("urlBase64ToUint8Array decodes a key to bytes", () => {
  const out = urlBase64ToUint8Array(VAPID);
  assert.ok(out instanceof Uint8Array);
  assert.ok(out.length > 0);
});

test("isPushSupported: false without SW / Notification", () => {
  assert.equal(isPushSupported({ navigator: {}, notification: null }), false);
  assert.equal(
    isPushSupported({ navigator: { serviceWorker: {} }, notification: null }),
    false,
  );
});

test("isPushSupported: true with SW + pushManager + Notification", () => {
  const ok = isPushSupported({
    navigator: { serviceWorker: {} },
    notification: fakeNotification("default"),
    registration: { pushManager: {} },
  });
  assert.equal(ok, true);
});

test("getPermission returns unsupported without Notification", () => {
  assert.equal(getPermission({ notification: null }), "unsupported");
  assert.equal(getPermission({ notification: fakeNotification("granted") }), "granted");
});

test("constructor requires a vapidPublicKey", () => {
  assert.throws(() => new WebPushClient({}), /vapidPublicKey/);
});

test("isSubscribed reflects the pushManager state", async () => {
  const reg = fakeRegistration();
  const client = new WebPushClient({
    vapidPublicKey: VAPID,
    deps: { registration: reg, notification: fakeNotification("granted") },
  });
  assert.equal(await client.isSubscribed(), false);
  reg._set(fakeSubscription());
  assert.equal(await client.isSubscribed(), true);
});

test("subscribe creates a subscription and hands it to onSubscribe", async () => {
  let handed = null;
  const reg = fakeRegistration();
  const client = new WebPushClient({
    vapidPublicKey: VAPID,
    onSubscribe: (sub) => {
      handed = sub;
    },
    deps: {
      registration: reg,
      navigator: { serviceWorker: {} },
      notification: fakeNotification("granted"),
    },
  });
  const json = await client.subscribe();
  assert.ok(json.endpoint);
  assert.deepEqual(handed, json, "server callback received the subscription");
});

test("subscribe rejects when permission is denied", async () => {
  const client = new WebPushClient({
    vapidPublicKey: VAPID,
    deps: {
      registration: fakeRegistration(),
      navigator: { serviceWorker: {} },
      notification: fakeNotification("denied"),
    },
  });
  await assert.rejects(() => client.subscribe(), /permission denied/);
});

test("subscribe rejects when unsupported", async () => {
  const client = new WebPushClient({
    vapidPublicKey: VAPID,
    deps: { navigator: {}, notification: null },
  });
  await assert.rejects(() => client.subscribe(), /not supported/);
});

test("subscribe reuses an existing subscription", async () => {
  const existing = fakeSubscription("https://push.example/existing");
  const reg = fakeRegistration({ existing });
  let subscribeCalled = false;
  reg.pushManager.subscribe = async () => {
    subscribeCalled = true;
    return fakeSubscription();
  };
  const client = new WebPushClient({
    vapidPublicKey: VAPID,
    deps: {
      registration: reg,
      navigator: { serviceWorker: {} },
      notification: fakeNotification("granted"),
    },
  });
  const json = await client.subscribe();
  assert.equal(json.endpoint, "https://push.example/existing");
  assert.equal(subscribeCalled, false, "did not create a new subscription");
});

test("unsubscribe cancels and notifies the server", async () => {
  let removed = null;
  const existing = fakeSubscription();
  const reg = fakeRegistration({ existing });
  const client = new WebPushClient({
    vapidPublicKey: VAPID,
    onUnsubscribe: (sub) => {
      removed = sub;
    },
    deps: { registration: reg, notification: fakeNotification("granted") },
  });
  assert.equal(await client.unsubscribe(), true);
  assert.ok(removed && removed.endpoint);
});

test("unsubscribe is a no-op (false) when not subscribed", async () => {
  const client = new WebPushClient({
    vapidPublicKey: VAPID,
    deps: { registration: fakeRegistration(), notification: fakeNotification("granted") },
  });
  assert.equal(await client.unsubscribe(), false);
});

test("requestPermission short-circuits a decided permission", async () => {
  let asked = false;
  const notif = {
    permission: "granted",
    requestPermission: async () => {
      asked = true;
      return "granted";
    },
  };
  const client = new WebPushClient({ vapidPublicKey: VAPID, deps: { notification: notif } });
  assert.equal(await client.requestPermission(), "granted");
  assert.equal(asked, false);
});

test("subscribe records the active push endpoint; unsubscribe clears it", async () => {
  setActivePushEndpoint(null);
  const reg = fakeRegistration();
  const client = new WebPushClient({
    vapidPublicKey: VAPID,
    deps: {
      registration: reg,
      navigator: { serviceWorker: {} },
      notification: fakeNotification("granted"),
    },
  });
  const json = await client.subscribe();
  assert.equal(getActivePushEndpoint(), json.endpoint, "endpoint recorded on subscribe");
  await client.unsubscribe();
  assert.equal(getActivePushEndpoint(), null, "endpoint cleared on unsubscribe");
});
