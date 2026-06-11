# QUALITY-T4 — code-quality pass on `feat/native-web`

Track T4 (`tempestweb/native/*`, `client/native/*`, `tests/unit/test_native*.py`)
was already implemented to a very high standard by the build stage: ruff
(`E,W,F,I,N,UP,B,C4,SIM,Q,ANN,D`), `ruff format`, and `mypy --strict` were already
clean, and all tests green. The quality pass therefore applied only small,
behavior-preserving fixes.

## Applied (no behavior / signature change)

- **`tests/unit/test_native_http.py`** — `ruff format` reformatted one
  multi-argument call (`test_request_post_not_retried_without_key`) to one
  argument per line. Formatting only.
- **`client/native/http.js`** — corrected two JSDoc generic annotations from the
  non-standard `Object<string,string>` to the valid `Object.<string,string>` form
  so the `@returns` / `@type` parse correctly under standard JSDoc tooling. Doc
  comments only.
- **`client/native/notifications.js`** — removed a dead
  `// eslint-disable-next-line no-new` directive (the project has no ESLint
  configured, so it referenced a linter that never runs) and replaced it with a
  plain comment documenting the intentional side-effect construction of
  `new Ctor(...)`. No behavior change.
- **`client/native/share.js`** — collapsed a redundant `catch` body in
  `shareShare`: both the `err.name === "AbortError"` branch and the fallthrough
  returned the identical `{ outcome: "cancelled" }`, so the branch was dead. The
  unified `catch {}` keeps the exact same observable behavior (any `navigator.share`
  rejection → `cancelled`), and the comment now documents that AbortError is the
  common cancel path. The `share.share: cancelled when the user aborts` test still
  passes.

## Deferred — would require a behavior or public-signature change

These are real observations, but each would change the public surface or behavior,
which is out of scope for a quality-only pass. Flagging for the supervised review:

1. **Ambiguous top-level re-exports in `tempestweb/native/__init__.py`.**
   `clipboard.read` / `clipboard.write` are re-exported at the package top level as
   the bare names `read` / `write`, while `storage.get` is aliased to `storage_get`
   to avoid a clash. The bare `read`/`write` names are ambiguous at
   `from tempestweb.native import read` (clipboard? storage? file?). Consider
   namespacing them as `clipboard_read` / `clipboard_write` (or only exposing them
   via the `clipboard` module namespace, dropping the bare re-export). This changes
   the importable public surface, so it is deferred.

2. **`storage_get` asymmetry.** Only `get` is aliased (`storage_get`); `put`,
   `remove`, `list_keys` are re-exported bare. If the bare-name policy is revisited
   per (1), the storage names should be made consistent at the same time
   (`storage_put` / `storage_remove` / `storage_list_keys`, or none aliased).
   Public-surface change → deferred.

3. **`NATIVE_RESULT_PREFIX` is exported but unused within T4.** It is documented as
   a transport-multiplexing token consumed by Track T2's transports during the
   morning merge. It is correct to keep it exported for that integration, but if T2
   ends up not multiplexing native results onto the event lane, this constant
   should be removed. Confirm at merge; removing it now would be premature and would
   change the public surface.

None of the above were applied because they alter the public import surface or
observable behavior; the quality bar (lint/format/types/docstrings/idioms) is fully
met as-is.

## Verification (after the pass)

```
ruff check .            # All checks passed!
ruff format --check .   # 28 files already formatted
mypy tempestweb         # Success: no issues found in 19 source files
pytest -q               # 39 passed
node --test tests/client/**/*.test.js   # pass 24, fail 0
```
