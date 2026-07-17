# QA Review — `fix/p2-offline-hardening`

**VERDICT: PASS-WITH-GAPS**

Claims 1–5 and 7 are implemented and backed by real, non-tautological tests.
Claim 6's drain *logic* is tested, but its *wiring* (dynamic-import path,
periodicsync producer, SW↔page double-send) is unverified and partly overclaimed.
The full gate is green.

---

## Gate output (clean run, worktree `.venv`/`node_modules`)

```
$ ruff check .
All checks passed!

$ ruff format --check .
263 files already formatted

$ mypy tempestweb
Success: no issues found in 112 source files

$ pytest -q
882 passed, 1 skipped in 11.01s
  (skip = tests/unit/test_server_sse.py:211, pre-existing T2 deadlock, unrelated)

$ node --test "tests/client/*.test.js"
ℹ tests 472  ℹ pass 472  ℹ fail 0  ℹ skipped 0

$ mkdocs build --strict ; echo EXIT $?
EXIT 0
  ("Currently unlicensed" is the mkdocs-material 2.0 banner, not a --strict
   warning; build exits 0. Info lines about roadmap/contract links are excluded
   pages, pre-existing.)
```

No `_core` (removed from repo). No files touched outside the P2 offline/PWA
surface. Python is double-quoted, fully typed, docstringed (mypy/ruff green).

---

## Done-when checklist (the 7 claims)

| # | Claim | Verdict | Proof / gap |
|---|-------|---------|-------------|
| 1 | Dead-letter poison; transient retry→maxAttempts(5)→`failed` & keep draining; permanent 4xx dead-letters first attempt; 408/425/429/5xx transient; pure `classifyReplayOutcome` | ✅ CONFIRMED | `tests/client/offline-sync.test.js:108-158` (all branches + exhaustion loop); off-by-one correct (5 network sends before dead-letter). Poison keeps draining: `:127-144`. |
| 2 | 409 conflict lane non-blocking; `conflicts()`/`failed()`; ReplayResult+failed/conflicts; caps through JS handlers+Mode C facade+contract+offline.py+`__init__` | ✅ CONFIRMED (minor gap) | Parity enforced by `tests/unit/test_native_contract.py:58-79` (HANDLERS==contract, facade==mode_c). `native-offline.test.js:85-110`, `offline-sync.test.js:160-185`. **Gap:** Python `offline.failed()`/`conflicts()` awaitables and `ReplayResult.failed/conflicts` fields have **no direct Python unit test** — `tests/unit/test_native_offline.py` still only exercises enqueue/pending/size/replay(sent,remaining). |
| 3 | `isCacheable` never caches 4xx/5xx/opaque/no-store in cache-first + SWR | ✅ CONFIRMED | `sw-strategies.test.js:56-71`; applied in both `handleFetch` branches (`sw.js:539-543,552-557`) and in `handleNavigation`. |
| 4 | `trimCache` cap (60) on runtime cache after SWR put | ✅ CONFIRMED (terminology) | `sw-strategies.test.js:73-92`. It evicts by **insertion order**, not true LRU (Cache API exposes no access time). Docstring correctly says "least-recently-added"; the commit/claim word "LRU" is imprecise but harmless. |
| 5 | `handleNavigation` offline fallback: exact cache → `/` → 503 doc | ✅ CONFIRMED | `sw-strategies.test.js:96-142`; wired for `request.mode === "navigate"` in the fetch listener (`sw.js:482-485`). |
| 6 | Worker drains IDB itself via dynamic import on `sync` AND `periodicsync`, every owner, shared policy; falls back to `REPLAY_OFFLINE_QUEUE`; `store.listAll()` added | 🔶 PARTIAL | Drain **logic** solid: `sw-offline-drain.test.js` (listAll, every-owner, 409/400 policy, empty no-op) + `store.js:listAll`. `sync` path auto-wired (`registerBackgroundSync()` on every enqueue, `offline.js:111`). **Gaps below (F1–F4).** |
| 7 | `persistStorage()` called on queue build | ✅ CONFIRMED | `native-offline.test.js:112-129` drives the real queue and asserts `navigator.storage.persist()` fires; guarded once by the `_queue` memo (`offline.js:42,50`). |

---

## Findings (prioritized)

**F1 — MEDIUM — `client/sw/sw.js:560-566` — `periodicsync` drain has no producer; QUEUE_PERIODIC_TAG is dead.**
The SW registers a `periodicsync` listener (`event.tag.startsWith("tw-offline")`),
but nothing in the shipped code ever calls `registration.periodicSync.register("tw-offline-…")`.
Only `registerBackgroundSync()` (the one-off `sync` tag) is auto-wired on enqueue.
`QUEUE_PERIODIC_TAG` (`sync.js:34,340`) is exported and referenced **only** by a
tautological test (`offline-sync.test.js:187-189`, asserts it differs from
`QUEUE_TAG`). So the "AND `periodicsync`" half of claim 6 does not fire
out-of-the-box; an app must manually register via `native.bgsync`. Suggested fix:
either auto-register a periodic sync with `QUEUE_PERIODIC_TAG` when supported, or
drop the "periodicsync" wording from the claim and mark the tag as app-opt-in.

**F2 — MEDIUM — `client/sw/sw.js:605-611` (`replayFromSync`) — dynamic-import path + fallback are entirely untested and the path↔layout coupling is unguarded.**
`import("/client/offline/store.js")` / `/client/offline/sync.js` is hardcoded.
It is correct for the two modes that actually ship a SW (wasm `_build_wasm` and
transpile `_build_transpile` both put offline modules under `out/client/offline/`);
Mode B (`_build_server`) ships **no** SW at all and serves those modules under
`/static/offline/`, so the mismatch never bites — but nothing tests this. No test
ties the SW's literal import string to the artifact layout, so a future move of
the offline modules (or shipping the SW in Mode B) would silently break the
tab-closed drain and fall to the client-ping path. The `catch` fallback branch,
`notifyClients`, and `OFFLINE_QUEUE_DRAINED`/`REPLAY_OFFLINE_QUEUE` messages have
no automated coverage (worker-only; acknowledged in-code and in the roadmap as
manual verification). Suggested fix: add a build test asserting
`/client/offline/store.js` resolves in the wasm/transpile artifacts, and a jsdom
test of `replayFromSync`'s import-failure → `REPLAY_OFFLINE_QUEUE` fallback with
injected `import`.

**F3 — MEDIUM — SW drain vs page `replayOnReconnect` double-send; idempotency is the *only* guard and it is not stated explicitly.**
On reconnect the page (`replayOnReconnect` → `queue.replay()`, `sync.js:325-329`)
and the worker (`sync` event → `drainOfflineQueue`, separate `OfflineQueue`
instance over the *same* IndexedDB) can drain concurrently. The single-flight
`_replaying` guard is **per-instance**, so it does not prevent cross-context
double-send; the same row can be sent twice and `attempts` can lose an update
(both read 0, both write 1). Only the server-side `Idempotency-Key` dedup saves
it. The docstrings assert "a re-sent mutation never double-applies server-side"
(true) but never call out the specific page+worker concurrent-drain race. No test
exercises cross-context concurrency (fake-indexeddb is single-context).
Suggested fix: document the race explicitly in `drainOfflineQueue`/offline-sync
docs ("idempotency is the sole cross-context guard"); no code change required if
idempotency is truly relied upon.

**F4 — LOW — Python `offline.failed()`/`offline.conflicts()` and `ReplayResult.failed/conflicts` lack direct unit tests.**
`tests/unit/test_native_offline.py:91-98` still asserts only `sent`/`remaining`.
The new awaitables and fields are proven only indirectly (name parity +
mypy + the JS side). Suggested fix: add a `ScriptedBridge` case for
`offline.failed`/`offline.conflicts` and a `replay` returning
`{sent,remaining,failed,conflicts}`.

**F5 — LOW — inline comments inside function/wiring bodies violate the project no-inline-comment rule.**
New/modified inline comments: `sync.js:317` (`break; // transient…`),
`sw.js:552-553,560-561` (Background/Periodic Sync notes in the listener block).
Per CLAUDE.md these belong in the surrounding docstring. Consistent with the
file's pre-existing (non-conforming) style, so cosmetic. Suggested fix: migrate
into the nearest docstring.

**F6 — LOW/INFO — `Mutation.status` still advertises `"done"` but the code never sets it** (`offline.py:41`, `sync.js` deletes on success instead). Pre-existing; the added `"conflict"` value is wired everywhere. No action required beyond awareness.

---

## Not-a-bug (contested and cleared)

- **Import path for Mode B (concern c):** Mode B ships no service worker
  (`SERVER_ARTIFACT_FILES` has no `sw.js`/`register.js`/manifest; `_build_server`
  never calls `_build_pwa`), so the `/client/` hardcode cannot break Mode B. See
  F2 for the residual (untested coupling).
- **listAll mishandling failed/conflict rows (concern f):** `drainOfflineQueue`
  filters `status === "pending"` for both the owner set and (inside `replay`) the
  rows, so parked failed/conflict rows are correctly ignored; an owner with only
  parked rows is excluded. Verified by `sw-offline-drain.test.js:69-93`.
- **Off-by-one on transient dead-letter (concern e):** `attempts+1 >= maxAttempts`
  with increment-then-break yields exactly 5 network sends before dead-letter;
  proven by the exhaustion loop `offline-sync.test.js:146-158`.
- **mkdocs --strict (concern h):** clean, exit 0.
