# REVIEW-T10 — adversarial QA of Track T10 (Trilho O — observability)

**Branch:** `feat/observability` · **Base:** `main` · **Reviewer stance:** skeptical QA, run-don't-trust.
**Round:** 2 (re-QA after fix round 1, commit `26af6a7`).

## VERDICT: PASS

The four done-when clauses are each backed by a real, passing automated test. The
full project gate is green from a clean checkout. The single substantive gap from
round 1 — `server_decode_jwt` being exported but untested on both branches — is now
**genuinely closed**: two real unit tests cover the success path (injected fake
`JWTUtils`, asserting forwarded args + `dict()` coercion off a dict subclass) and
the SDK-absent path (`RuntimeError` with the documented message), and the
`# pragma: no cover` was removed. No edits to `tempestweb/_core/`, nothing touched
outside the track, no TS/build introduced (Python-only track). The remaining items
(P2 vendor-SDK shapes, P3 live DOM effect) are honest, documented manual deferrals
that are out of the automatable scope of this track.

---

## Gate output (run from clean state, this worktree)

```
$ uv run ruff check .
All checks passed!                                   EXIT 0

$ uv run ruff format --check .
26 files already formatted                           EXIT 0

$ uv run mypy tempestweb
Success: no issues found in 15 source files          EXIT 0

$ uv run pytest -q
60 passed in 0.17s                                   EXIT 0

$ uv run pytest tests/unit/test_observability*.py -q
56 passed in 0.19s
  test_observability_auth.py            21 passed
  test_observability_error_boundary.py   7 passed
  test_observability_feature_flags.py   10 passed
  test_observability_logger.py           8 passed
  test_observability_telemetry.py       10 passed
```

The scope-target command from the MANIFEST (`pytest tests/unit/test_observability*.py`)
is **green** (56 tests, up from 54 — the 2 new JWT tests landed).

---

## Done-when checklist (each clause vs. an actual passing test)

| Clause | Status | Proof |
|--------|--------|-------|
| Each provider exposes a minimal interface + ≥1 working adapter | PASS | O0 `TelemetryAdapter` Protocol + Console/Sentry/PostHog; O1 `LoggerSink` + console sink; O2 `ErrorBoundary` + `default_fallback`; O3 `FeatureFlagsAdapter` Protocol + InMemory/GrowthBook/LaunchDarkly; O4 `AuthStore`/`RefreshQueue`. All exported names resolve (import-verified). |
| Swapping adapters changes no call sites | PASS | `test_swapping_adapter_changes_no_call_sites` in telemetry (line 91) and feature_flags (line 63): a single `emit(provider)` / `read(provider)` fn drives two **distinct** backends (Console vs Recording; InMemory vs GrowthBook-mock) unchanged, and asserts each backend's distinct effect. |
| Per-provider unit tests pass with third-party instances mocked | PASS | Sentry (`capture_message`/`set_user`), PostHog (`capture`/`identify`), GrowthBook (`get_feature_value`), LaunchDarkly (`variation`) all via `MagicMock` + `assert_called_once_with`/`assert_any_call` on real method names. Console/in-memory via injected sink. All 56 tests assert (the 2 AST "no-assert" hits are mock `assert_called_*` calls — real assertions). |
| Refresh queue serializes concurrent refresh into a single renewal | PASS | `test_concurrent_refreshes_collapse_into_single_renewal`: 5 real `asyncio.create_task` callers, an `Event` holds the renewal open so waiters pile up; asserts `refresh_calls == 1` and all 5 get the same token. Independently re-probed a **late-arriving** caller (joins after the renewal starts, before it settles) → still coalesced to 1 call. Reset-after-settle and failure-then-retry also covered. Not faked. |

---

## Round-1 gap closure (verified)

- **P1 — `server_decode_jwt` untested public surface → CLOSED.**
  - `test_server_decode_jwt_verifies_via_sdk_and_coerces_to_dict`: injects a fake
    `tempest_fastapi_sdk` module via `sys.modules`, returns a `dict` *subclass*,
    asserts `type(result) is dict` (coercion) and the exact forwarded
    `{token, secret, kwargs}`. Real success-path coverage.
  - `test_server_decode_jwt_raises_runtimeerror_when_sdk_absent`: blocks the SDK
    import via a patched `builtins.__import__`, asserts the `RuntimeError` message
    (`match="requires tempest-fastapi-sdk"`). Real error-path coverage.
  - `# pragma: no cover` removed from `auth.py:434` (confirmed: grep finds no
    `pragma: no cover` anywhere in the track). The branch is now actually exercised.

---

## Convention audit

- **No `tempestweb/_core/` edits** — `git diff --name-only main...HEAD -- tempestweb/_core/` is empty. ✅
- **No files touched outside the track** — diff confined to `tempestweb/observability/*`, `tests/unit/test_observability*.py`, `NOTES-T10.md`, `QUALITY-T10.md`, `SUMMARY-T10.md`, `REVIEW-T10.md`. ✅
- **No single-quote string literals** — all `'` hits are apostrophes/doctest output inside docstrings; flake8-quotes (Q) passes under ruff. ✅
- **Full typing / docstrings** — mypy `--strict` clean over 15 files; ruff `ANN`+`D` (google) clean. The `Any` params (`sink`, injected vendor clients, JWT kwargs) carry justified `# noqa: ANN401`. ✅
- **No skip/xfail/NotImplementedError/pragma behind green tests** — grep finds none. The only `...` are Protocol bodies + docstring examples. ✅
- **Empty-collection convention** — N/A (no collection-returning lookups). ✅
- **Client JS** — N/A (T10 is Python-only; no `.js`/`client/` files touched, no TS/build). ✅

---

## Findings (prioritized)

### P2 — Vendor adapters assume SDK method shapes, unverified against real versions (manual deferral, documented)
- Sentry/PostHog/GrowthBook/LaunchDarkly asserted only against mocks. A real-SDK
  signature mismatch is local to one adapter and never touches the provider Protocol
  or call sites. Concrete per-SDK verification steps are recorded in `NOTES-T10.md`
  (§P2). Acceptable for a night build; confirm against pinned versions before prod.
- **Not a blocker** — this is an inherent limit of mocking absent third-party SDKs,
  flagged honestly, with reproducible steps.

### P3 — Error boundary live DOM effect unverifiable here (manual deferral, documented)
- `ErrorBoundary.render()` Python behavior is fully tested (fallback returned, no
  raise, report hook fires with `error_type`/`message`/`stack`, custom fallback,
  decorator, telemetry reporter). The visual "broken subtree shows fallback while
  the rest renders" needs the T1 client patcher in a browser. Steps in `NOTES-T10.md`
  (§P3). No overclaim.
- **Not a blocker** — correctly out of this track's automatable scope.

---

## Bottom line
Round-1's only real gap is closed with honest tests and the `pragma` removed. The
done-when is genuinely met for all five client-side providers; the concurrent-refresh
guarantee survives an independent late-caller race probe; the gate is fully green from
clean. P2/P3 are documented manual deferrals, not unverified claims. **PASS** — ship
after honoring the P2/P3 manual checks before production.
