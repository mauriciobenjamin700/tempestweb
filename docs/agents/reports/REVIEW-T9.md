# REVIEW-T9 — adversarial QA (Track P: PWA / offline / WebPush)

**Branch:** `feat/pwa-offline-webpush`
**Reviewer:** tw-qa (skeptical, run-it-don't-trust-it)
**Date:** 2026-06-11

## VERDICT: PASS

Every done-when clause maps to a real, asserting, passing automated test. The full
project gate is green from a clean tree. No `_core` edits, no files touched outside
the track scope (beyond the expected quality-stage doc and the flagged coordination
edit to `tempestweb/server/__init__.py`). No skipped/xfail/assert-free tests, no
`NotImplementedError` behind green tests, no TypeScript and no build step in the
client. Live install/push are correctly deferred to `NOTES-T9.md` and the
browser-dependent CI jobs are honestly marked `continue-on-error`.

## Gate output (clean run)

```
ruff check .             -> All checks passed!
ruff format --check .    -> 23 files already formatted
mypy tempestweb          -> Success: no issues found in 13 source files
pytest -q                -> 38 passed in 0.35s
pytest tests/unit/test_pwa*.py -q -> 34 passed
node --check client/sw/sw.js       -> sw.js OK
node --test tests/client/**.test.js -> 82 passed, 0 fail, 0 skipped, 0 todo
node scripts/pwa-gate.mjs           -> PWA gate OK
node scripts/pwa-gate.mjs --push-smoke -> push-smoke OK
```

## Done-when checklist

| Clause | Proof | Status |
|---|---|---|
| manifest is valid JSON + installable-shaped | `test_default_manifest_is_valid_json_and_installable`, `test_manifest_has_required_install_fields` (Node emits, Python parses + `validate_installable`) | PASS |
| sw.js passes `node --check` | gate run + `test_*` / CI `unit` step | PASS |
| sw.js has precache + fetch strategy + update lifecycle | `sw.js`: `install`→`caches.open(PRECACHE)`, `fetch` handler + `chooseStrategy` (cache-first/network-first/SWR/network-only), `activate`+`clients.claim`, `SKIP_WAITING` message; tests `sw-strategies.test.js` (14 asserts) + `register.js` updatefound→onUpdate→reload-once, `sw-register.test.js` | PASS |
| webpush VAPID subscribe/send unit-tested, pywebpush mocked | `test_pwa_webpush.py` (10 tests): from_env, dedup store, signed payload, 410 prune, transient keep, disabled no-op, fan-out, subscribe/unsubscribe — sender injected/mocked, dep lazy | PASS |
| offline queue replay unit-tested | `offline-sync.test.js`: FIFO drain, stop-at-first-failure + attempts++, thrown send stays queued, re-entry guard (single in-flight), idempotency keys, Background Sync register, replayOnReconnect online/offline | PASS |
| CI PWA gate job present | `.github/workflows/pwa.yml` — hard `unit` job runs node --check + client tests + python pwa tests; `lighthouse`/`push-e2e` soft | PASS |
| manifest extras present | `test_overrides_pass_through` (shortcuts, share_target POST, id), `validateExtras`/`validate_extras` mirrored | PASS |
| live install/push documented | `NOTES-T9.md` (80 lines): P0 install, P1 offline+update, P2 queue replay, P3 push/410/iOS, P4 CI, P5 Android extras | PASS |

## Adversarial findings

Hunted for the usual overclaim vectors — none material:

- **No `_core` edits.** `git diff --name-only main...HEAD | grep _core` → empty.
- **No out-of-track code files.** All changes confined to `client/{pwa,sw,offline,push}`,
  `tempestweb/pwa`, `tempestweb/server/webpush.py`, `scripts/`, `.github/workflows/pwa.yml`,
  `tests/`. Plus `QUALITY-T9.md`/`NOTES-T9.md`/`REVIEW-T9.md` (docs) and the
  pyproject/package.json/lock bumps for the `[webpush]` extra and `fake-indexeddb`
  **devDependency** (correctly dev-only, not a runtime client dep — honors the
  "no client runtime deps" rule).
- **Coordination edit is honest.** `tempestweb/server/__init__.py` only adds the
  webpush re-exports; the report flags the T2 union-on-merge need. Not an overreach.
- **No TypeScript / build step.** The `: string` grep hits are all inside JSDoc
  `@param`/`@returns`, not TS. Client is pure ESM, double-quoted, JSDoc'd.
- **No skip leakage.** The two `pytest.skip("node required")` guards did NOT fire
  (node present — all 4 manifest/gate tests show PASSED, not SKIPPED).
- **No assert-free / todo / xfail tests** in JS or Python; every test file carries
  real assertions (min 3, most 16–39).
- **No tracked `__pycache__`**, no `console.log`/`debugger` in client production code.

## Honestly-deferred (not gaps — correctly scoped out and marked)

- Lighthouse + Playwright push e2e are `continue-on-error` until Trilho C serves a
  built static app and CI provisions a VAPID pair. The gate script provides a
  browserless installable + push-contract smoke in the meantime. This matches the
  manifest rule "browser/device-live → automate what you can, mark the rest manual."
- Static-build wiring (SW precache manifest, `<link rel=manifest>` injection,
  dist emission) and the `native.*` round-trip bridge depend on Trilhos C/N — out
  of T9's file scope by design.

## Gaps to close

None blocking. The track meets its done-when.
