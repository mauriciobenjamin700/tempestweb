# REVIEW-T1 — adversarial QA, Track T1 (`feat/client-render`)

**VERDICT: PASS**

Reviewer: tw-qa (skeptical). Gate run from a clean worktree; every DONE-WHEN
clause traced to a real, asserting, passing test. No overclaim found that
affects the verdict; minor non-blocking notes recorded below.

## Gate output (actual)

The applicable gate for T1 is the JS suite (the track is JS-only — zero Python
files touched, so `ruff`/`mypy`/`pytest` do not apply to this branch's delta).

```
$ node --test "tests/client/**/*.test.js"
ℹ tests 36
ℹ suites 0
ℹ pass 36
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
```

- 36 pass / 0 fail / **0 skipped / 0 todo** — no hidden disables.
- `node --check` passes on all four client modules (dom/style/events/tempestweb).
- No `.only`, `.skip`, `todo:` markers in any test file; every test file uses
  `assert`.

## Scope / contamination check

```
$ git diff --name-only main...HEAD
QUALITY-T1.md  SUMMARY-T1.md
client/dom.js  client/events.js  client/style.js  client/tempestweb.js
tests/client/{dom,events,mount,style}.test.js
```

- **`tempestweb/_core/**` untouched** (verified — vendored core not edited).
- **No files outside T1's declared scope.** transport.js / transport-wasm.js /
  transport-ws.js correctly left as the other tracks' stubs.
- **No Python changes** — `make check`'s ruff/mypy/pytest are N/A to this delta.
- **No TypeScript, no build step, no tsconfig** — pure JS ES modules, JSDoc only.
  Honors the "JS puro" rule.
- Golden fixtures (`tests/fixtures/*.json`) are **unchanged** by T1 — they came
  from the base and carry the full Style field set dumped by the real core
  (e.g. `shadow`, `stack_align`, `text_overflow`), so the "derived from core,
  not invented" contract requirement holds; T1 did not tamper with the shape.

## DONE-WHEN checklist

| Clause | Proven by | Status |
|---|---|---|
| Build DOM from `node_initial.json` → expected tree | `dom.test.js`: "buildElement maps the counter tree…" (tags, keys, text, nesting) | PASS |
| Apply `patches_all_kinds.json` → expected DOM (all 5 kinds) | `dom.test.js`: "all five patch kinds applied in sequence…" (update/insert/remove/reorder/replace each asserted) | PASS |
| `style_sample.json` → expected CSS | `style.test.js`: "style_sample.json maps to the expected CSS declarations" + 16 field-level cases | PASS |
| Button click → mock transport `sendEvent` with right key | `events.test.js` "clicking a Button calls sendEvent with its key" → `{type:"click",key:"inc",payload:{}}`; `mount.test.js` end-to-end via `mount()` | PASS |

All four clauses map to assertions that would fail if the behavior regressed —
none are vacuous.

## Independent verification beyond the suite

- **Reorder correctness beyond the 2-element swap the suite covers.** The suite
  only tests `order:[1,0]`. I ran an out-of-band 3-element case `order:[2,0,1]`
  against the real `applyReorder`: result `[C,A,B]`, matching the contract's
  "new child i = old child order[i]". The snapshot-then-reappend implementation
  is genuinely correct, not just coincidentally right for a swap. (Non-blocking
  gap: the suite itself does not lock this in — see Findings.)
- **Patch classification** matches `docs/contract.md` §Patches key-presence rules
  exactly (`set_props`→Update, `order`→Reorder, `node`+`index`→Insert,
  `node`→Replace, `index`→Remove), with a `TypeError` on unknown shape (tested).
- **`data-tw-type` claim verified** — `TYPE_ATTR` is set in `applyNodeShape`.

## Findings (prioritized, all NON-BLOCKING)

1. **(low) Reorder coverage is thin.** Only `[1,0]` is tested; a permutation
   like `[2,0,1]` would harden the suite against a future reappend-order
   regression. Implementation is correct today (verified out-of-band).
2. **(low) `unset_props` only handles `style`/`content`/`label`.** Any other
   unset key is silently ignored. Fine for v1 (those are the only DOM-bearing
   props), but worth a comment or a guard when the prop vocabulary grows.
3. **(info) Manual verification still owed (correctly disclosed by the agent).**
   jsdom asserts DOM mutations and CSS strings, not layout/paint. A live-browser
   pass (flex/colors/spacing actually render; click round-trips through a real
   transport) remains a human step — flagged in SUMMARY-T1.md, consistent with
   the project's visual-verification rule. This is expected for T1 and does not
   reduce the verdict, since everything automatable under jsdom is green.
4. **(info) Reported commit count was 6; actual is 7** (`ef185eb ref:
   code-quality pass on T1` exists beyond the 6 listed). Cosmetic reporting
   drift, no impact on scope or correctness.

## Bottom line

T1 delivers exactly its scope, every DONE-WHEN clause has a real passing test,
the gate is green with nothing skipped, the vendored core and other tracks'
files are untouched, and the "no TS / no build / JS puro" constraints hold. The
only gaps are test-coverage hardening (reorder permutations) and the inherent
jsdom-can't-paint manual step, both correctly disclosed. **PASS.**

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
