# REVIEW-T7 — Conformance harness (independent adversarial QA)

**Reviewer:** skeptical QA (run-it-don't-trust-it)
**Branch:** `feat/conformance`
**Worktree:** `/home/mauriciobenjamin700/projects/my/tempestweb-T7`
**Base:** `2e3a9bf`
**HEAD at review:** `774c3b6 ref: code-quality pass on T7`

## VERDICT: PASS

The track's DONE-WHEN is met by passing, falsifiable automated tests. I ran the
full gate from the existing venv, tampered the golden to prove the lock bites,
independently re-derived the patch stream from the live core, and confirmed both
transport doubles converge to the same DOM *and* to the core's own final view.
Two LOW scope-boundary gaps (F1/F2) are correctly out of T7's file scope and do
not block the gate.

## DONE-WHEN (from MANIFEST.md)

> Suite que gera patches do core e fixa o shape; teste que garante que dois
> transportes mock produzem DOM idêntico.

| Clause | Proof (passing test) | Status |
|---|---|---|
| Generates patches from the real core | `_scenarios.py` runs `build`/`diff` over real `tempestweb._core` widgets; `_generate.py` writes the golden; `test_conformance_fixture_matches_core` byte-matches on-disk vs fresh render | MET |
| Pins the node IR shape | `test_node_ir_shape` (exactly 4 keys), `test_text_props_carry_content`, `test_button_props_carry_label_and_handler_ref` | MET |
| Pins all five patch kinds | `test_all_five_patch_kinds_are_emitted_and_classified` (update/insert/remove/reorder/replace), `test_patch_paths_are_index_lists` | MET |
| Regenerable golden lock | `test_conformance_fixture_matches_core` + `test_scenario_ticks_match_golden[*]`; regeneration is idempotent (re-ran `_generate`, tree stayed clean) | MET |
| Two mock transports → identical DOM | `test_two_transports_render_identical_dom[counter/list/replace]`: asserts A==B AND both == core's `final` | MET |

## Gate (run from existing `.venv`, clean tree)

```
ruff check .            -> All checks passed!
ruff format --check .   -> 22 files already formatted
mypy tempestweb         -> Success: no issues found in 9 source files
mypy tests/conformance  -> Success: no issues found in 7 source files
pytest tests/conformance -q -> 20 passed in 0.16s
pytest -q (whole repo)  -> 24 passed in 0.16s
node --test             -> N/A (T7 added no client JS; MANIFEST gate is `pytest tests/conformance`)
```

## Adversarial probes

- **Golden is falsifiable.** Tampered `counter.final.key` -> `TAMPERED`: suite went
  RED (`test_conformance_fixture_matches_core` + `test_scenario_ticks_match_golden[counter]`,
  2 failed / 18 passed). Restored from backup: tree byte-exact clean, 20 passed.
  Not a vacuous lock.
- **Derived from the real core.** Independently ran `build`/`diff` on the live core
  via `.venv/bin/python`: insert emits `node`+`index`, replace emits `node` without
  `index`, matching `patch_kind`'s classifier and the committed goldens. All five
  kinds appear (counter=update, list=insert/reorder/remove, replace=replace).
- **A-vs-B convergence is real and non-trivial.** For every scenario A==B==final:
  counter ticks=2 final=[label,Row], list ticks=3 final=[b] (after a->ab->ba->b),
  replace ticks=1 final=[Button@x]. The `final`-equality guard means two identical
  applicator bugs could not both "agree" past the core's own answer.
- **Protocol check is meaningful.** `PatchTransport` is `@runtime_checkable` with
  `send_patches`/`recv_event`/`close`; both doubles implement all three, so the
  `isinstance` assertion is not vacuous.
- **No assert-nothing / skip / xfail.** Only legit `@pytest.mark.parametrize`. No
  `NotImplementedError`, no `pass`-only tests, no TODO/FIXME.
- **Scope clean.** `git log 2e3a9bf..HEAD -- tempestweb/_core` empty. Diff touches
  only `tests/conformance/*`, `tests/fixtures/conformance_scenarios.json`, and the
  report files (`REVIEW-T7.md`, `QUALITY-T7.md`). No TypeScript, no build step, no
  client JS.
- **Conventions.** Double quotes (apparent single-quote grep hits are apostrophes
  inside English docstrings). Full type hints, Google docstrings in English. mypy
  --strict clean on both the package and the test package.

## Findings (LOW — follow-ups, NOT gate failures)

- **F1 — native_call/native_result framing and the Style/Color/Edge object shape
  are not golden-locked here.** `grep` of `tests/conformance` + the golden finds no
  `native_call`/`native_result` and no dedicated Style→CSS field assertion. Style
  *objects* do flow through the IR (golden has 20 `"style"` keys) and round-trip
  through Mode-B JSON, but the harness does not pin the native-bridge envelope or
  the per-field Style shape. These are owned by T2/T4 (native protocol) and T1 (the
  client Style renderer), so the omission is in-scope-correct — but anyone relying
  on T7 as the drift guard for the native bridge should know it is not covered yet.
- **F2 — both transport doubles share one Python applicator** (`_dom.apply_batch`);
  they differ only by a JSON round-trip in Mode-B. This proves *wire-serialization*
  independence (number coercion, key order, tuple->list), not JS-vs-Python
  applicator parity. The latter is closed by the client jsdom tests in T1. Mitigated
  here by both transports also being asserted equal to the core's own `final`.

## Manual verification required

None. The track is fully automatable under pytest and is green.
