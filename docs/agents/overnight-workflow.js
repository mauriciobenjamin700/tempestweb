export const meta = {
  name: "tempestweb-overnight",
  description:
    "Parallel build of tempestweb across independent tracks, each in its own git worktree/branch with an inlined domain-specialist persona, then a quality pass and an adversarial QA review per track.",
  phases: [
    { title: "Build", detail: "track specialists implement in parallel worktrees off main" },
    { title: "Quality", detail: "raise each branch to the docstring/typing/lint bar and apply fixes" },
    { title: "QA", detail: "review each branch from scratch as it lands" },
  ],
};

const REPO = "/home/mauriciobenjamin700/projects/my/tempestweb";

// Specialist personas are INLINED (custom agentTypes are not loaded mid-session,
// so we prepend the persona text and use the default subagent instead).

const PY = `PERSONA — senior Python backend engineer. Conventions (enforced by the gate):
- Double quotes everywhere. Full type hints on every param/return/var (Any explicit); mypy --strict must pass on tempestweb.
- Google-style docstrings IN ENGLISH on every public module/class/function/method (summary + Args/Returns/Raises). ruff D + ANN are in the gate.
- Async-first for all I/O. SQLAlchemy 2.0 select() if any DB (never session.query()).
- Module-level imports via __init__.py with current __all__ (never deep submodule imports). Collections return [] (never raise for empty; 404 only for single-resource). Pydantic list fields use Field(default_factory=list).
- Mode B server uses FastAPI + tempest-fastapi-sdk patterns where natural; bind 127.0.0.1.
- Engine comes from tempestweb._core (vendored) — NEVER edit tempestweb/_core/**.`;

const JS = `PERSONA — senior frontend engineer writing PURE modern JavaScript.
- NO TypeScript (no .ts, no type annotations, no tsc). NO framework. NO build step/bundler. ES modules via <script type="module">.
- No runtime deps beyond the browser (and Pyodide in Mode A). Dev-only jsdom for tests is fine.
- Double quotes. Complete, accurate JSDoc on every export/typedef (JSDoc is the type surface).
- Program against docs/contract.md + the golden fixtures in tests/fixtures/ (derived from the real core; they are truth). Patch kinds distinguished by key presence (Update/Insert/Remove/Reorder/Replace). Color {r,g,b,a}->rgba; Edge {top,right,bottom,left}->px. DOM elements carry data-tw-key; use event delegation. Tests in tests/client/ via node --test + jsdom.`;

const DOCS = `PERSONA — documentation owner. Build a BILINGUAL MkDocs site: PT-BR (default) + EN-US (under /en/), mkdocs-material + mkdocs-static-i18n + a header language switch, deployed to GitHub Pages via .github/workflows/docs.yml (build_type: workflow). 'uv run mkdocs build --strict' MUST pass with ZERO warnings — that is the gate. Write in the tiangolo/FastAPI didactic style: tutorial-first and progressive (one concept per short page), every example complete and runnable (no '...'), teach-by-doing then a short Recap, heavy Material admonitions (!!! tip/note/warning/check, ??? for depth), friendly second-person voice with light emoji. Do NOT rewrite docs/plan.md/roadmap.md/contract.md — link to them. README banner points at the live Pages URL (PT + EN), never localhost.`;

const QUALITY = `PERSONA — code-quality enforcer to the tempest-fastapi-sdk / tempestroid bar. You APPLY fixes (quality only, never behavior changes), keeping the branch green.
- Python: Google docstrings on every public surface; full annotations (ruff ANN + mypy --strict); lint clean under E,W,F,I,N,UP,B,C4,SIM,Q,ANN,D; ruff format clean; double quotes; idioms (module-level re-exports + __all__, select() not query(), [] for empty collections, Field(default_factory=list), async I/O, naming conventions).
- JS: plain JS only (no TS/framework/build), double quotes, complete accurate JSDoc, no dead code / leftover console.log.
- Method: run ruff check / ruff format --check / mypy; apply ruff --fix + format for mechanical issues, then add real docstrings/types/idioms by hand; re-run the branch's own tests so it stays green. NEVER edit tempestweb/_core/** or files outside the track.`;

const QA = `PERSONA — skeptical QA engineer. Your job is to DISPROVE that the track is done; you run code, you do not trust prose.
- Run the full applicable gate from a clean state (make setup if needed; ruff check, ruff format --check, mypy tempestweb, pytest -q, node --test). Record actual output.
- Check every done-when clause against an actual passing test. A claim with no automated proof is a GAP.
- Hunt for: assert-nothing/skipped/xfail tests, NotImplementedError behind a green test, UI/browser behavior claimed without an automatable check, edits to tempestweb/_core, files touched outside the track, single quotes / missing types / missing docstrings (Python), TypeScript or a build step in the client.
You do NOT implement features. Write REVIEW-<ID>.md (VERDICT PASS/PASS-WITH-GAPS/FAIL + gate output + done-when checklist + prioritized findings), commit it, report the verdict bluntly.`;

const COMMON = `You are working on tempestweb OVERNIGHT, unsupervised. Commit GRANULARLY with conventional commits (feat:/fix:/ref:/test:/docs:/chore:), and end every commit message with:
Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Do NOT git push and do NOT merge into any branch. Never claim something works without a passing test; if a step needs a real browser/device, write every automatable test and record manual steps in NOTES-<ID>.md. Read CLAUDE.md, docs/plan.md, docs/contract.md and docs/agents/MANIFEST.md first.`;

function buildPrompt(t) {
  return `${t.persona}

${COMMON}

TASK — Track ${t.id}.
Your isolated worktree ALREADY EXISTS on branch ${t.branch}:
  cd ${REPO}-${t.id}
  make setup
Do ALL work inside ${REPO}-${t.id}. Never touch the main checkout or another track's files. Leave your branch with all work committed; do not remove your worktree.

SCOPE: ${t.scope}

DONE WHEN: ${t.done}

VERIFICATION (must pass before each commit): ${t.verify}

When the scope is complete and green, write SUMMARY-${t.id}.md (what you built, what is stubbed, what needs manual verification, suggested merge order) and make a final commit. Report: branch, commit count, test status, and anything the human must verify by hand.`;
}

function qualityPrompt(t) {
  return `${QUALITY}

${COMMON}

TASK — code-quality pass on track ${t.id} (branch ${t.branch}).
  cd ${REPO}-${t.id}
Raise this branch to the bar and APPLY the fixes without changing behavior or public signatures beyond adding types. Re-run the branch's own tests so it stays green, then commit "ref: code-quality pass on ${t.id}". Defer anything needing a behavior change to QUALITY-${t.id}.md and report it.`;
}

function qaPrompt(t, buildReport) {
  return `${QA}

${COMMON}

TASK — adversarial QA review of track ${t.id} (branch ${t.branch}).
  cd ${REPO}-${t.id}
The DONE-WHEN to contest (from docs/agents/MANIFEST.md):
${t.done}

The implement agent reported:
---
${buildReport ?? "(no report — verify what actually exists on the branch)"}
---
Run the full applicable gate from scratch, check every done-when clause against a passing test, hunt for untested/overclaimed work and convention violations, then write and commit REVIEW-${t.id}.md and report the verdict. Do not implement fixes.`;
}

const TRACKS = [
  {
    id: "T1",
    branch: "feat/client-render",
    persona: JS,
    scope:
      "Pure-JS client renderer. Implement client/dom.js (buildElement + applyPatches for all 5 patch kinds; set data-tw-key on elements), client/style.js (styleToCss covering flex/box-model/border/background/color/typography/dimensions; Color {r,g,b,a}->rgba, Edge->padding/margin), client/events.js (delegated capture -> transport.sendEvent reading data-tw-key), and wire client/tempestweb.js mount() against a mock transport. jsdom tests in tests/client/.",
    done:
      "Building DOM from tests/fixtures/node_initial.json then applying tests/fixtures/patches_all_kinds.json yields the expected DOM; tests/fixtures/style_sample.json maps to the expected CSS; a click on a Button calls the mock transport's sendEvent with the right key.",
    verify: 'node --test "tests/client/**/*.test.js"',
  },
  {
    id: "T2",
    branch: "feat/mode-server",
    persona: PY,
    scope:
      "Mode B (server), phases B0-B2 + B5(SSE). Implement tempestweb/server/ (FastAPI + WebSocket host using tempest-fastapi-sdk patterns where natural), tempestweb/transports/websocket.py (PatchTransport over WS), tempestweb/transports/sse.py (B5: patches server->client via EventSource, events client->server via HTTP POST, SAME PatchTransport interface), tempestweb/runtime/session.py (per-connection session: connect=mount, disconnect=unmount, cancel orphan tasks), client/transport-ws.js and client/transport-sse.js. Reconciler from tempestweb._core. pytest with WS and SSE/POST test clients.",
    done:
      "A test client connects over WS, receives initial patches for the counter, sends a click, and receives the resulting Update patch; the SSE transport delivers the same patch stream via EventSource + POST; two connections keep independent state.",
    verify: "pytest tests/unit/test_server*.py -q",
  },
  {
    id: "T3",
    branch: "feat/mode-wasm",
    persona: PY,
    scope:
      "Mode A (WASM/Pyodide). FIRST research the CURRENT state of pydantic-core in Pyodide (post knowledge-cutoff — use web search) and record findings in NOTES-T3.md. Implement public/index.html bootstrap (loads Pyodide + vendored core + an app.py, produces patches in the browser), tempestweb/runtime/wasm.py (Python-side glue), tempestweb/transports/wasm.py (PatchTransport over pyodide.ffi), client/transport-wasm.js. Pure-Python logic must be pytest-covered; the live browser path is documented for manual verification.",
    done:
      "transport-wasm.js + wasm.py implement the interface; the bootstrap is complete and documented. Pure-Python units are green. Live Pyodide run is documented in NOTES-T3.md.",
    verify: "pytest tests/unit/test_wasm*.py -q",
  },
  {
    id: "T4",
    branch: "feat/native-web",
    persona: PY,
    scope:
      "Web capability adapters in tempestweb/native/ as typed awaitables: geolocation, clipboard, notifications, storage (mirror tempestroid/native naming where it maps). client/native.js glue calling navigator.*. Document the Mode-A (browser) vs Mode-B (proxied over WS round-trip) split. pytest with mocked Web APIs.",
    done:
      "Each capability has a typed Python awaitable wrapper + JS glue; signatures are async; the client/server split is documented.",
    verify: "pytest tests/unit/test_native*.py -q",
  },
  {
    id: "T5",
    branch: "feat/cli-devloop",
    persona: PY,
    scope:
      "Flesh out tempestweb/cli/ (new/dev/build/run — keep cli/main.py's parser shape) and tempestweb/devserver/ (file watcher + reload signal, transport-agnostic). `new` scaffolds a runnable project; `dev` watches and triggers reload (stub transport); `build --mode wasm|server` produces the right artifact shape. pytest coverage.",
    done:
      "tempestweb new X creates a runnable project tree; dev watcher detects a change and emits a reload; build --mode produces the expected artifact layout.",
    verify: "pytest tests/unit/test_cli*.py -q",
  },
  {
    id: "T6",
    branch: "feat/docs-site",
    persona: DOCS,
    scope:
      "Bilingual MkDocs site (PT-BR default + EN-US under /en/) in the tiangolo style: mkdocs-material + mkdocs-static-i18n + header language switch, and .github/workflows/docs.yml for Pages. Pages: landing, installation, architecture (link docs/arquitetura.md), a progressive tutorial building the counter, the wire contract, and placeholders for PWA/SSE. Do NOT rewrite docs/plan.md/roadmap.md/contract.md — link to them. Point the README banner at the Pages URL (PT + EN).",
    done:
      "uv run mkdocs build --strict passes with zero warnings; language switch present; tutorial covers the counter end to end; docs.yml deploy workflow present.",
    verify: "uv run mkdocs build --strict",
  },
  {
    id: "T7",
    branch: "feat/conformance",
    persona: QA,
    scope:
      "Conformance harness in tests/conformance/: generate patches from the real core and lock the wire-format shape (regenerable goldens); a test asserting two mock transports fed the same patch stream produce identical DOM (the A-vs-B guarantee). New fixtures under tests/fixtures/.",
    done:
      "A pytest suite pins the contract shape and asserts transport-independence of the rendered DOM.",
    verify: "pytest tests/conformance -q",
  },
  {
    id: "T8",
    branch: "feat/examples",
    persona: PY,
    scope:
      "Additional example apps under examples/ (todo-list, a form, an async fetch view) exercising the core widget API (inputs, lists, forms). Each is a view(app)->Widget module like examples/counter/app.py. tests/unit/test_examples.py imports each, builds the view, validates the tree.",
    done:
      "Each example imports, build(view()) validates and yields a tree; input/list/form widgets are exercised.",
    verify: "pytest tests/unit/test_examples.py -q",
  },
  {
    id: "T9",
    branch: "feat/pwa-offline-webpush",
    persona: JS,
    scope:
      "Trilho P — PWA / offline-first / WebPush. Own files: client/pwa/ (manifest.webmanifest emitter, sw.js service worker, register.js), tempestweb/server/webpush.py (VAPID via tempest-fastapi-sdk[webpush] patterns), tests/unit/test_pwa*.py. P0: installable manifest. P1: service worker precaches the app-shell (client JS always; Mode A also Pyodide + core wheel + app.py) cache-first -> offline after first load. P2: per-resource strategies + offline event queue with replay-on-reconnect (Mode B). P3: WebPush — native notifications.subscribe()/permission awaitables, SW push handler, server-side send (pywebpush). Stub client/build integration against interfaces.",
    done:
      "manifest is valid JSON and installable-shaped; sw.js passes node --check and has precache + fetch strategy; webpush VAPID subscribe/send is unit-tested (pywebpush mocked); offline queue replay is unit-tested. Live install/push documented in NOTES-T9.md.",
    verify: 'pytest tests/unit/test_pwa*.py -q && node --check client/pwa/sw.js',
  },
];

phase("Build");
log(`Launching ${TRACKS.length} track specialists (inlined personas) in parallel pre-created worktrees; each flows build -> quality -> qa.`);

const results = await pipeline(
  TRACKS,
  (t) =>
    agent(buildPrompt(t), { label: `build:${t.id}`, phase: "Build" }).then((report) => ({
      ...t,
      buildReport: report,
    })),
  (built) =>
    agent(qualityPrompt(built), { label: `quality:${built.id}`, phase: "Quality" }).then(
      (qualityReport) => ({ ...built, qualityReport })
    ),
  (checked) =>
    agent(qaPrompt(checked, checked.buildReport), { label: `qa:${checked.id}`, phase: "QA" }).then(
      (qaReview) => ({
        id: checked.id,
        branch: checked.branch,
        buildReport: checked.buildReport,
        qualityReport: checked.qualityReport,
        qaReview,
      })
    )
);

const ok = results.filter(Boolean);
log(`Done. ${ok.length}/${TRACKS.length} tracks built + quality-passed + QA-reviewed.`);
return ok;
