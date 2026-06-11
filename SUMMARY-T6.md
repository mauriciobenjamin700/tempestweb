# SUMMARY — Track T6: Bilingual MkDocs documentation site

Branch: `feat/docs-site`. Worktree: `tempestweb-T6`.

## What this track delivers

A **bilingual MkDocs site** (PT-BR default + EN-US under `/en/`) in the
tiangolo/FastAPI didactic style, deployed to GitHub Pages via a workflow.

**The gate passes:** `uv run mkdocs build --strict` -> exit 0, **zero warnings**.
Both languages build (9 pages PT + 9 pages EN), with a contextual language
switcher in the header.

### Tooling / config

- `mkdocs.yml` — Material theme, `mkdocs-static-i18n` (suffix mode: `*.md` = PT,
  `*.en.md` = EN), `reconfigure_material: true` (injects the header language
  switch), bilingual search, tiangolo-style markdown extensions (admonition,
  details `???`, superfences, content tabs, emoji, code annotations).
  - Removed `navigation.instant` — incompatible with the i18n language switcher
    and the source of a strict-mode warning.
  - `exclude_docs` keeps the living design docs (`plan.md`, `roadmap.md`,
    `contract.md`, `arquitetura.md`, `agents/`) out of the build — they use
    repo-relative links that do not resolve under `--strict`. They are linked from
    the rendered pages via GitHub blob URLs instead (per scope: do NOT rewrite).
- `pyproject.toml` carries the `[docs]` extra; `uv.lock` updated with the docs
  dependency tree.
- `.github/workflows/docs.yml` — `build_type: workflow` for Pages. Strict build is
  the gate on push/PR; deploy to Pages only on push to `main`.
- `README.md` — banner points at the live Pages URL for **both** languages
  (PT root + EN `/en/`), never localhost.

### Pages (each in PT `.md` + EN `.en.md`)

- `index`, `installation`, `architecture` (links canonical `docs/arquitetura.md`).
- `tutorial/` — progressive, one concept per page, builds the **counter end to
  end**: `index`, `view`, `state`, `patches` (new), `modes` (new).
- `wire-contract` (new) — didactic summary; links canonical `docs/contract.md`.
- `capabilities` (new) — Track N (`native/`): two backends, one Python API.
- `pwa` (new) — Track P: installable, service worker, IndexedDB offline, WebPush.
- `observability` (new) — Track O: telemetry/logger/error-boundary/flags/auth.
- `design-docs` (new) — index linking the living plan/roadmap/contract/arquitetura.

Style: tutorial-first, complete runnable examples (no `...`), code annotations,
content tabs for mode variants, heavy admonitions (`!!! tip/note/warning/check/
danger`, `???` for depth), short Recap per page, second-person voice, light emoji.

## What is stubbed / forward-looking

- The capabilities / PWA / observability pages document the **planned** surface
  (Tracks N/O/P are still being built). Examples use the intended public API
  (`tempestweb.native.*`, `tempestweb.pwa.*`, `tempestweb.observability.*`),
  marked "under construction" with an info admonition + link to the design plan.
  When those tracks land, the examples should be import-tested against real modules.

## What a human must verify by hand

- **GitHub Pages settings:** repo must have Pages "Source = GitHub Actions"
  enabled for `docs.yml` to deploy (one-time manual toggle).
- **Live URLs after first deploy:** confirm `https://mauriciobenjamin700.github.io/
  tempestweb/` (PT) and `.../en/` (EN) load and the header switcher flips between
  them. Verified in built HTML locally (PT `capabilities/` links to
  `../en/capabilities/`); the live render is worth a glance.
- **Visual check** (optional): Material theme + dark/light toggle is standard; not
  browser-verified in this environment.

## Suggested merge order

Documentation-only — no Python/JS source touched (verified via `git diff --stat`
over the T6 commits). Safe to merge **independently and early**, no dependency on
Tracks N/O/P/W. If merging after those tracks, optionally add import-tests for the
example snippets on the capabilities/pwa/observability pages.

## Verification

```bash
cd tempestweb-T6
uv pip install -e ".[docs]"
uv run mkdocs build --strict   # exit 0, zero warnings (the gate)
```

Result: **exit 0, 0 warnings**, 9 PT pages + 9 EN pages, contextual language
switcher present in every page.
