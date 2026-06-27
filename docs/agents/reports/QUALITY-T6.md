# QUALITY-T6 — code-quality pass on track T6 (`feat/docs-site`)

Track T6 is **documentation-only** (Markdown + `mkdocs.yml` + `docs.yml` CI +
`pyproject.toml`/`uv.lock`/`README.md`). No Python or JS source is touched on the
branch (verified via `git diff --name-only main...HEAD`). The quality bar for a
docs track is therefore: strict build green with zero warnings, accurate examples
that do not drift from the real core/contract, and no broken intra-doc links.

## Applied in this pass (no behavior change)

- **Fixed a broken intra-doc link in the built PT site.** `docs/tutorial/view.md`
  linked to `../contract.md#style`, but `contract.md` is **excluded** from the
  MkDocs build (`exclude_docs` — the living design docs use repo-relative links
  that do not resolve under `--strict`). The link rendered to a non-existent page.
  Repointed it to the in-site equivalent `../wire-contract.md#3-style`, matching
  the convention already used by `tutorial/patches.md` and the EN sibling. This
  also removed the `INFO: ... contains a link to 'contract.md' which is excluded`
  line from the strict build.
- **Language parity.** Tightened the EN sibling `docs/tutorial/view.en.md` to the
  same precise anchor (`../wire-contract.md#3-style`) so PT and EN point at the
  same section.

### Verification (all green after the edits)

```text
ruff check .            -> OK
ruff format --check .   -> OK
mypy tempestweb         -> OK (no issues, 9 source files)
pytest -q               -> OK (4 passed)
mkdocs build --strict   -> exit 0, zero build warnings (PT + EN, anchor resolves)
```

Verified in the built HTML: PT `tutorial/view/` now links to
`../../wire-contract/#3-style`, and `id="3-style"` exists in the built
`wire-contract/` page. The only remaining `.md` hrefs in built HTML are the
intentional absolute GitHub blob URLs for the excluded living design docs
(`contract.md`, `arquitetura.md`, `plan.md`, `roadmap.md`).

## Deferred — needs a behavior change or external action (NOT done here)

These are out of scope for a quality pass (they require new code, other tracks to
land, or a human with repo access). Recording them per the workflow rule.

1. **Import-test the forward-looking example snippets.** The
   `capabilities` / `pwa` / `observability` pages document the *planned* public
   API (`tempestweb.native.*`, `tempestweb.pwa.*`, `tempestweb.observability.*`),
   marked "under construction". Those modules are being built on Tracks N/O/P.
   When they land, add import/doctest coverage so the snippets cannot drift from
   the real modules (the same way the tutorial examples were validated against the
   real `tempest_core` in this pass). Requires the other tracks to be merged
   first — a dependency, not a quality fix.
2. **MkDocs 2.0 upstream deprecation banner.** `mkdocs-material` prints a stderr
   banner warning that MkDocs 2.0 will break the plugin/theme system. It does not
   affect the `--strict` exit code (build is exit 0) and is not actionable on this
   branch — it is an ecosystem migration to track when MkDocs 2.0 ships. No change
   is appropriate now.
3. **GitHub Pages one-time toggle + live-URL check (human-only).** The repo must
   have Pages "Source = GitHub Actions" enabled for `docs.yml` to deploy, and the
   live PT (`/tempestweb/`) and EN (`/tempestweb/en/`) URLs plus the header
   language switcher should be eyeballed after the first deploy. Cannot be
   automated in this environment (no repo settings access, no live deploy).
