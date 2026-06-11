# QUALITY-T9 — code-quality pass (branch `feat/pwa-offline-webpush`)

Stage `quality` for Track T9 (Trilho P: PWA / offline / WebPush). Goal: raise the
branch to the tempest-fastapi-sdk / tempestroid bar **without changing behavior or
public signatures** (only adding types), keeping the branch green.

## Baseline (before the pass)

The branch already met the gate on entry:

- `ruff check tempestweb` — All checks passed (E,W,F,I,N,UP,B,C4,SIM,Q,ANN,D).
- `ruff format --check tempestweb` — 13 files already formatted.
- `mypy tempestweb` (`--strict`) — no issues in 13 source files.
- `pytest tests/unit/test_pwa*.py` — 34 passed.
- `node --check client/sw/sw.js` — clean.
- `node --test "tests/client/**/*.test.js"` — 82 passed.

The Python and JS sources were already fully typed / JSDoc'd, idiomatic, double-quoted,
free of dead code and leftover `console.*` / `TODO`/`FIXME`. The pass was therefore
narrow: three behavior-neutral nits the linters do not catch.

## Fixes applied (no behavior change, no signature change)

1. **`tempestweb/server/webpush.py`** — hoisted `import json` from inside
   `WebPushService.send()` to the module-level import block. PEP 8 / project idiom
   (module-level imports); `json` is stdlib and side-effect-free, so behavior is
   identical. Ruff's `PLC0415` (import-outside-top-level) is not in the project
   `select` set, so this was not flagged automatically.

2. **`client/pwa/manifest.js`** (line 177) — converted the lone single-quoted
   string literal `'share_target with method POST requires an enctype'` to double
   quotes, matching the project's double-quote rule. The two other single-quoted
   literals in the file (`'...standalone...'`, `'...purpose "any"'`) legitimately
   embed double quotes and were left as-is.

3. **`client/sw/sw.js`** (`replayFromSync` docstring) — corrected a doc drift: the
   JSDoc referenced `client/pwa/sync.js`, but the offline queue actually lives in
   `client/offline/sync.js`. Comment-only change.

## Verification (after the pass) — all green

```
ruff check tempestweb            -> All checks passed!
ruff format --check tempestweb   -> 13 files already formatted
mypy tempestweb                  -> Success: no issues found in 13 source files
pytest tests/unit/test_pwa*.py   -> 34 passed
node --check client/sw/sw.js     -> clean
node --test tests/client/**.js   -> 82 passed
```

## Deferred (needs a behavior change) — NONE

No issue required altering behavior or a public signature. Everything found was
applied in this pass. There is nothing outstanding to defer.
