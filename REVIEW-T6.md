# REVIEW-T6 — adversarial QA of `feat/docs-site` (bilingual MkDocs site)

**VERDICT: PASS**

Reviewer: tw-qa (skeptical). Method: ran the gate from a clean `site/` rebuild,
checked every done-when clause against actual built output and against the real
core/fixtures, hunted for overclaim and convention violations. No fixes applied.

---

## Gate output (from clean state)

```
$ rm -rf site && uv run mkdocs build --strict
EXIT=0
INFO -  mkdocs_static_i18n: Building 'pt' documentation to directory: .../site
INFO -  mkdocs_static_i18n: Overriding 'pt' config 'site_name' with 'tempestweb'
INFO -  Cleaning site directory
INFO -  Building documentation to directory: .../site
INFO -  mkdocs_static_i18n: Translated 14 navigation elements to 'pt'
INFO -  mkdocs_static_i18n: Building 'en' documentation to directory: .../site/en
INFO -  mkdocs_static_i18n: Overriding 'en' config 'site_name' with 'tempestweb'
INFO -  Documentation built in 0.65 seconds
```

Zero `WARNING`/`ERROR` log lines. The only red text in output is the **Material
for MkDocs team's cosmetic stderr banner** about the future MkDocs 2.0 release —
it is NOT a MkDocs build warning and does **not** fail `--strict` (exit 0
confirms it). Builds 9 PT pages (`site/*/index.html`) + 13 EN pages
(`site/en/.../index.html`).

This is a docs-only track: `uv run mkdocs build --strict` is the entire
applicable gate (ruff/mypy/pytest/node apply to source tracks; T6 touches no
source). Confirmed below.

---

## Done-when checklist

| Clause | Status | Proof |
|---|---|---|
| `mkdocs build --strict` zero warnings | PASS | Exit 0 from clean rebuild; no `WARNING -`/`ERROR -` lines. |
| Language switch present | PASS | Built `site/index.html` contains `md-select` (Material header switcher) + `<link hreflang="pt">`/`<link hreflang="en">` alternates. `mkdocs.yml`: `mkdocs-static-i18n` with `pt` default + `en`, `alternate_style: true`. |
| Tutorial covers the counter end to end | PASS | 5 pages: `tutorial/index` → `view` → `state` → `patches` → `modes`. Code matches `examples/counter/app.py` (same imports, `view` shape, keys, `Style(gap=8.0, padding=Edge.all(16))`). API verified against real core (`App.set_state`, `Column/Row/Text/Button`, `Edge.all` all import and run). |
| `docs.yml` deploy workflow present | PASS | `.github/workflows/docs.yml`: strict build is the gate, Pages deploy via `upload-pages-artifact@v3` + `deploy-pages@v4` (`build_type: workflow`), deploy gated to `push` on `main`, `pages: write`/`id-token: write` perms. |

---

## Verifications run (not trusting prose)

- **No `_core` edits.** `git diff main...HEAD -- tempestweb/_core` is empty.
- **No source touched.** `git diff main...HEAD -- '*.py'` is empty. Only
  `pyproject.toml` change is a new `[docs]` optional-dependency group
  (mkdocs-material, mkdocs-static-i18n) — in scope per MANIFEST (`pyproject.toml`
  is a docs-trigger path).
- **No orphan nav pages.** Living design docs (`plan.md`, `roadmap.md`,
  `contract.md`, `arquitetura.md`, `agents/`) are excluded via `exclude_docs`;
  every nav entry is bilingual. The 4 PT-only `.md` files are exactly those
  excluded design docs — not part of the site.
- **Tutorial code is faithful to the real core, not invented.** IR shape
  `{type, key, props, children}` matches `tests/fixtures/node_initial.json`
  exactly. All 5 patch shapes documented in `patches.md`
  (Update `{path,set_props,unset_props}`, Insert `{path,index,node}`,
  Remove `{path,index}`, Reorder `{path,order}`, Replace `{path,node}`) match
  `tests/fixtures/patches_all_kinds.json` field-for-field.
- **README banner** points to both PT (`/tempestweb/`) and EN (`/tempestweb/en/`)
  Pages URLs — no localhost instruction.
- **Planned-API pages marked.** `capabilities.md`, `pwa.md`, `observability.md`
  carry explicit under-construction markers (they document Track N/O/P surface
  not yet built). Not part of the contested done-when.

---

## Findings (prioritized — all non-blocking)

1. **(low) Doc-vs-code latent drift on app construction.** Tutorial + counter
   example present a `make_state()` factory, but the real `App.__init__` takes a
   positional `state` (`App(state, view, apply_patches, ...)`), not
   `state_factory=`. No docs page calls `App(...)` with a wrong signature (the
   tutorial only uses `app.set_state`/`app.state`, both real), so nothing in the
   site is a falsifiable overclaim today. When the runtime/CLI (Track T5) lands
   the `make_state` wiring, re-check this convention end to end.
2. **(info) Planned-API pages need import-testing once Tracks N/O/P land.**
   `capabilities`/`pwa`/`observability` snippets are aspirational; the agent
   already flagged this. Track them for an import test against the real modules
   at merge time.
3. **(info) Cosmetic Material 2.0 banner** prints to stderr on every build. Not a
   warning; cannot be suppressed without `INSIDERS`. No action needed.

## Bottom line

Every contested done-when clause is backed by actual built output and verified
against the real core/fixtures. Gate is green from clean state. No scope
violations, no `_core`/source edits, no untested overclaim in the in-scope
material. **PASS.**
