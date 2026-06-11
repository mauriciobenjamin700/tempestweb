# NOTES-T9 — manual verification (Track P: PWA / offline / WebPush)

Everything that can be automated is covered by `pytest tests/unit/test_pwa*.py`
and `node --test "tests/client/**/*.test.js"` (all green). The items below need a
real browser / device / push service and **must be verified by a human** before
the PWA story is declared production-ready. None of them block the unit gate.

## Prerequisites not yet in this repo

- **Static build (Trilho C / A3 / B0).** The service worker precache manifest,
  `<link rel="manifest">` injection into `index.html`, and the icon/manifest file
  emission all assume a `tempestweb build` step that writes `dist/`. Until that
  lands, `sw.js` runs with its dev-default precache list and the Lighthouse job is
  `continue-on-error` (soft). Wire `staticDistDir: "./dist"` in
  `.lighthouserc.json` once the build exists.
- **VAPID key pair.** Generate with any web-push tool (e.g.
  `npx web-push generate-vapid-keys`). Put the **public** key in the client
  (`new WebPushClient({ vapidPublicKey })`) and the **private** key in the server
  env (`VAPID_PRIVATE_KEY`, `VAPID_SUBJECT=mailto:you@host`). **Never commit them.**

## P0 — install

1. Build + serve over HTTPS (or `http://localhost`).
2. Chromium desktop/Android: confirm the install icon / "Add to Home Screen"
   appears and the manifest shows **installable** in DevTools > Application >
   Manifest. Lighthouse "installable-manifest" audit must be green.
3. The soft prompt (`createInstallPrompt().promptInstall()`) must only fire after
   a real user gesture — confirm no cold prompt on first paint.
4. Installed app opens in a **standalone** window (no browser chrome).
5. Inspect a generated maskable icon in the Android "safe zone" preview — confirm
   the 10% inset keeps the art uncropped.

## P1 — offline + update lifecycle

1. Load once online, then go offline (DevTools > Network > Offline) and reload —
   the app shell must load from cache.
2. Publish a new build (bump `__CACHE_VERSION__`), reload — the page should fire
   `onUpdate`; confirming posts `SKIP_WAITING` and reloads exactly once (no reload
   loop). Old caches must be gone after `activate` (check Application > Cache
   Storage).

## P2 — offline data + queue replay

1. Offline: read previously-cached data from IndexedDB (Application > IndexedDB).
2. Offline: perform a mutation — confirm it lands in the durable queue.
3. Go back online — the queue must replay automatically (Background Sync where
   supported; on **Safari**, on the `online` event with the tab open) and the
   server must **not** double-apply (idempotency key dedup).
4. Confirm `navigator.storage.persist()` returns true once granted.

## P3 — WebPush

1. Subscribe via `WebPushClient.subscribe()` — grant permission, confirm the
   server receives + stores the subscription (`POST /webpush/subscribe`).
2. Send from the server (`WebPushService.send_to_owner(...)`) with the tab
   **closed** — the notification must appear.
3. Click the notification — it must focus/open the app at the deep-link URL
   (`resolveClickUrl` -> `DEEP_LINK` postMessage -> core `DeepLinkEvent`). Test a
   custom **action** button too.
4. Confirm the **Badging API** count updates (`applyBadge`) on a payload carrying
   `badge_count` (desktop installed PWA).
5. Unsubscribe (`DELETE /webpush/my`) — sending must stop.
6. **iOS/Safari 16.4+:** push only works when the PWA is **installed**
   (standalone). Verify graceful degradation (`isPushSupported`) when not.
7. Kill a subscription server-side and confirm a `410 Gone` prunes it on next send.

## P4 — CI gate

- `.github/workflows/pwa.yml` runs the `unit` job as the hard gate. The
  `lighthouse` and `push-e2e` jobs are wired but `continue-on-error` until the
  static build + CI VAPID secret exist. Flip them to hard once those land and pin
  the Chromium version used by `@lhci/cli` / the Playwright action.

## P5 — manifest extras (manual, Android)

- Installed-icon long-press must show the **shortcuts** menu.
- Sharing content from another app to ours must deliver the payload to the
  `share_target` route (`/share-target`, POST multipart) — pair with `native.share`
  (Trilho N2).
- Opening a `.csv` with the app must hit the `file_handlers` route (`/open`).
