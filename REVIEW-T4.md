# REVIEW — Track T4 (`feat/native-web`)

**Reviewer:** tw-qa (adversarial)
**Date:** 2026-06-11
**Branch:** `feat/native-web` @ `7e143f3`
**Verdict: PASS**

The track delivers Trilho N (N0 http, N1 audio, N2 share, N3 geo/clipboard/storage,
N4 camera + notifications) as typed Python awaitables over a single bridge seam,
with pure-JS browser glue, all behind a contract-faithful
`native_call`/`native_result`/`call_id`/dotted-capability envelope. Gate is green
from a clean state. Done-when clauses each map to a real, assertion-rich test. No
overclaim beyond the items honestly flagged as manual in `NOTES-T4.md`.

## Gate output (clean run)

```
ruff check .            -> All checks passed!            (exit 0)
ruff format --check .    -> 28 files already formatted    (exit 0)
mypy tempestweb          -> Success: no issues found in 19 source files (--strict)
pytest tests/unit/test_native*.py -q -> 35 passed
pytest -q (full)         -> 39 passed
node --test tests/client/native.test.js -> 23 passed, 0 fail, 0 skipped, 0 todo
node --check client/native/*.js -> OK (all 9)
import tempestweb.native -> 43 exports, all resolve
```

## Done-when checklist (from MANIFEST.md)

| Clause | Status | Proof |
|---|---|---|
| Each capability is a typed Python awaitable + JS glue | PASS | `tempestweb/native/{http,audio,share,geolocation,clipboard,storage,camera,notifications}.py` each one `async def`; mypy --strict clean; `client/native/*.js` glue; `test_native_capabilities.py` drives every one through a fake bridge asserting dotted name + args + typed return |
| http retries with backoff | PASS | `test_request_retries_transient_status_then_succeeds`, `test_request_retries_network_error_then_succeeds`, `test_retry_options_backoff_is_exponential_and_capped` (verifies `min(base*factor**n, max)` cap) |
| http dedupes via idempotency key | PASS | `test_request_post_retried_with_idempotency_key` asserts both attempts carry the SAME `Idempotency-Key` header (`keys == {key}`); `test_request_post_not_retried_without_key` proves a bare POST is single-attempt |
| Mode A vs Mode B (proxied) split is documented | PASS | `dispatch.py` + `bridges.py` module docstrings; `NOTES-T4.md` (ASCII diagram + per-mode prose); `SUMMARY-T4.md`. `FFIBridge` (Mode A in-process) vs `ProxyBridge` (Mode B round-trip) is the entire seam; both tested |
| tests pass with mocked Web APIs | PASS | Python: fake `ScriptedBridge`/`RecordingBridge`, injected `sleep` — no network. JS: jsdom + injected `deps` (fetch/navigator/Notification/Audio/localStorage). 35 + 23 green |

## Findings

### Confirmed solid
- Contract alignment is real: `test_native_call_envelope_matches_contract` pins the
  exact `{kind,call_id,capability,args}` shape; the JS `HANDLERS covers every
  documented capability name` test pins the registry.
- ProxyBridge round-trip resolves by `call_id`, handles unknown id (`False`),
  cancels in-flight on close, and rejects calls after close — all tested.
- Collection convention honored: `storage.list_keys()` returns `[]` on empty
  (`test_storage_list_empty_returns_empty_list`), no `*NotFoundError`.
- "Blocked autoplay" and "unsupported share" are normal outcomes, not errors —
  tested both in Python and JS. Good domain modeling.
- Files strictly in-track: only `tempestweb/native/`, `client/native/`,
  `tests/unit/test_native*`, `tests/client/native.test.js`, T4 docs. **No edits to
  `tempestweb/_core`**, no other track touched.
- No TypeScript, no build step, all `.js`, JSDoc on public contracts. No
  `NotImplementedError`, no `skip`/`xfail`/`.todo`, no assert-less tests (51 JS
  assertions).

### Minor gaps (non-blocking; honestly flagged)
1. **Upload live progress ticks are not auto-tested.** `httpUpload` uses real
   `xhr.upload.onprogress`, but jsdom has no real upload progress, so the JS test
   only covers the `fetch` fallback path. The Python-side progress *forwarding*
   (`test_upload_reports_progress`) IS tested. Correctly listed as manual item #1 in
   `NOTES-T4.md`. Acceptable — genuinely browser-only.
2. **Live browser behaviors are manual-only** (audio autoplay gating, share sheet,
   geo/clipboard permission prompts, camera `getUserMedia`, Mode B end-to-end over a
   live WS). All listed in `NOTES-T4.md` §"Manual verification required". These are
   inherently browser/device-bound and the automatable surface (policy + glue with
   mocked APIs) is fully covered. Acceptable per the project's verification rule.
3. **Cross-track stubs** (`storage` IndexedDB via T9 `deps.store`; `ProxyBridge`
   transport wiring via T2; `FFIBridge` Pyodide dispatch via T3) are injected
   dependencies, tested with fakes, and documented as merge-time wiring. Not T4's
   scope per the MANIFEST. Acceptable.

### Note for the human reviewer
The agent rewrote a prior committed dispatch seam (`172b793`) because the earlier
WIP used a non-contract envelope (`kind:"native"`/`request_id`). The new shape
matches `docs/contract.md` exactly (verified against the contract doc). This is a
correct realignment, flagged transparently in the summary — confirm at merge that
no other track depended on the old shape (none in-tree does).

## Bottom line
PASS. Every done-when clause is backed by a passing, assertion-bearing automated
test. The only uncovered surface is genuinely browser-bound and honestly recorded
as manual. No convention violations, no out-of-track edits, no overclaim.
