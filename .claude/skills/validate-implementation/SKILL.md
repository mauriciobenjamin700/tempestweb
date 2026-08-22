---
name: validate-implementation
description: Validate a tempestweb change end to end before calling it done — the code gate (ruff/mypy/pytest/node) plus a real browser pass with the Chrome DevTools MCP and Playwright MCP, driving the affected screen with real input and reporting measured evidence. Use when finishing a feature or fix, when asked to "validar", "validate this", "provar que funciona", "check in the browser", or before opening/updating a PR that touches rendered UI, client JS, transports or examples.
---

# Validate an implementation

A change is not done because it compiles. In this project the truth is measured
in two places, and both are mandatory for anything that reaches a screen:

1. **The code gate** — ruff, mypy `--strict`, pytest, and the jsdom client tests.
   It proves the code is legal and the units behave.
2. **A real browser** — Chrome, driving the actual app, with real pointer input.
   It proves the pixel, the layout, the gesture and the console.

The gate alone has never caught a layout bug, a dead gesture, or a widget that
renders as an empty box. That is what this skill exists for.

## Step 0 — know what changed

```bash
git status --short
git diff --stat main...HEAD
```

Classify the change, because it decides how far you go:

| The diff touches | You must run |
| --- | --- |
| `client/**`, `tempestweb/html/**`, theme/style, an example's `view` | gate **+ browser** |
| `tempestweb/{server,transports,runtime}/**` | gate + browser (a session is UI) |
| docs only (`docs/**`, `README.md`, docstring wording) | `mkdocs build --strict` + docs guards |
| build/CI plumbing, tests only | gate |

## Step 1 — the code gate

Run it from the worktree of the branch under validation, and record real output.
Never paraphrase a result you did not see:

```bash
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy tempestweb
uv run --frozen pytest -q
node --test "tests/client/*.test.js"
```

!!! warning "Two traps that have bitten this repo"
    * `node --test tests/client/` (directory form) fails on Node 24+ with
      `MODULE_NOT_FOUND` — always use the glob.
    * A locally installed ruff can be newer than `uv.lock` and reformat markdown
      the CI never touches. `uv sync --all-extras` first, then `uv run --frozen`,
      so you check with the version CI uses.

Docs-touching change, additionally:

```bash
uv run --frozen --extra docs mkdocs build --strict
uv run --frozen pytest tests/unit/test_docs_nav.py tests/unit/test_docs_links.py \
  tests/unit/test_docs_redirects.py -q
```

A red gate ends the validation. Report it; do not proceed to the browser to look
for good news.

## Step 2 — serve the real app

Pick the mode the change lives in. Mode B (server) boots fastest and needs no
Pyodide download; Mode A proves the WASM bundle; Mode C proves the transpiler.

```bash
uv run --frozen tempestweb run --mode server --path examples/<example> --port 8123
# --mode wasm | --mode transpile for the other two legs
```

Run it in the background and confirm it answers before driving it:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8123/
```

!!! danger "The artifact is built at startup"
    `tempestweb run` copies `client/*.js` into `dist/`. Editing a client file
    after boot changes nothing on the page — restart the server, then verify the
    build actually carries your edit
    (`grep -c "<your marker>" examples/<example>/dist/server/static/<file>.js`).

## Step 3 — drive it in Chrome

Use the **Chrome DevTools MCP** (`mcp__chrome-devtools__*`) for inspection and
budgets, and the **Playwright MCP** (`mcp__playwright__*`) for scripted input.
Either can navigate; prefer one browser per validation so state is coherent.

The five things to establish, in order:

1. **It mounts.** `browser_navigate` (or `navigate_page`), then
   `browser_snapshot` — the accessibility tree, not a screenshot. A widget that
   renders as `generic` with no name is a widget that is not really there.
2. **It is marked as intended.** `browser_evaluate` reading the contract the
   renderer writes: `data-tw-key`, `data-tw-type`, and whatever attribute the
   change introduces. Measure geometry here too (`getBoundingClientRect`,
   `scrollHeight`, `getComputedStyle`) — a number is evidence, a screenshot is an
   impression.
3. **The interaction works with real input.** Clicks and typing:
   `browser_click` / `browser_type` / `browser_fill_form`. Gestures, wheel and
   drags: `browser_run_code_unsafe` with `page.mouse.*`, in steps, so
   `pointermove` really fires:

   ```js
   async (page) => {
     const box = await page.locator('[data-tw-key="rows"]').boundingBox();
     await page.mouse.move(box.x + box.width / 2, box.y + 20);
     await page.mouse.down();
     await page.mouse.move(box.x + box.width / 2, box.y + 140, { steps: 6 });
     await page.mouse.up();
     return page.locator('[data-tw-key="status"]').textContent();
   }
   ```

   Synthetic `dispatchEvent` is a last resort: it tests your listener, not the
   browser. Real pointer input is what separates this pass from the jsdom suite.
4. **It survives both sizes.** `browser_resize` to ≤430px and ≥1024px, then
   snapshot each. Check nothing overflows horizontally and no card pushes the
   page sideways.
5. **The console is clean.** `browser_console_messages` (level `warning`). A 404
   for an asset counts. For a PWA/performance-touching change, add
   `mcp__chrome-devtools__lighthouse_audit`.

## Step 4 — report evidence, not adjectives

Write the result as measurements, before → after where a defect was fixed:

```
✅ end_reached — wheel over the list: status went 25 → 50 → 125 → 200 items,
   stopping at the cap. 30 nodes in the DOM for 200 items (virtualization held).
✅ refresh — mouse down at the top, 140px drag, release: data-tw-pull-armed
   appeared past 64px, aria-busy=true during the reload, reloads 0 → 1.
✅ console: 0 errors, 0 warnings.
❌ spacer — reserved ::after 5950px, scrollHeight stayed 1050px (the window
   only). Fixed with flex:0 0 auto → 7000px.
```

Rules for the report:

* State what you could **not** verify, and why. "MCP unavailable in this
  environment" is an acceptable outcome; "it works" without a measurement is not.
* Every fix needs a test that **fails without it**. If the browser found the bug,
  the pass is incomplete until a jsdom or pytest case pins it.
* Kill the dev server and delete the build artifact (`dist/`) when done, so the
  next run rebuilds from source.

## Step 5 — leave the repo clean

```bash
pgrep -af "tempestweb run"      # then kill the pid you started
rm -rf examples/<example>/dist
git status --short               # nothing stray: no screenshots, no dist, no logs
```

## Recap

Gate first, browser second, evidence always. Classify the diff, run the real
gate with the locked tool versions, serve the real app, drive it with real input
at two viewport sizes, read the console, and report numbers. Anything you could
not measure gets said out loud instead of assumed.
