export const meta = {
  name: "tempestweb-overnight",
  description:
    "Parallel build of tempestweb across independent tracks, each in its own git worktree/branch with a domain specialist, then an adversarial QA review per track.",
  phases: [
    { title: "Build", detail: "track specialists implement in parallel worktrees off main" },
    { title: "Quality", detail: "tw-quality raises each branch to the docstring/typing/lint bar and applies fixes" },
    { title: "QA", detail: "tw-qa reviews each branch from scratch as it lands" },
  ],
};

const REPO = "/home/mauriciobenjamin700/projects/my/tempestweb";

// Shared preamble injected into every implement agent. Self-sufficient: the agent
// starts with fresh context, so everything it needs is spelled out here. The
// domain conventions live in the specialist's own system prompt (agentType).
function buildPrompt(t) {
  return `You are building tempestweb OVERNIGHT, unsupervised. Track ${t.id}.

REPO: ${REPO} (a git repo; base branch "main" is clean and green).
YOUR WORKTREE: ${REPO}-${t.id}
YOUR BRANCH: ${t.branch}

STEP 0 — your isolated worktree ALREADY EXISTS (pre-created on branch ${t.branch}):
  cd ${REPO}-${t.id}
  make setup            # uv venv + deps + npm install (uv cache makes this fast)
Then do ALL your work inside ${REPO}-${t.id}. Never touch the main checkout or
another track's files. Do NOT git push and do NOT merge. Leave your branch with all
work committed; do NOT remove your worktree.

READ FIRST: CLAUDE.md, docs/plan.md, docs/roadmap.md, docs/contract.md,
docs/agents/MANIFEST.md. The contract + golden fixtures in tests/fixtures/ are truth.

COMMIT GRANULARLY (conventional commits). Every commit must leave the branch green —
run the verification below before each commit. If something needs a real browser/
device, write every automatable test and record manual steps in NOTES-${t.id}.md. If
blocked on a design decision, record options + your choice in NOTES-${t.id}.md and
proceed — never stall the track.

YOUR SCOPE: ${t.scope}

DONE WHEN: ${t.done}

VERIFICATION (must pass before each commit): ${t.verify}

When scope is complete and green, write SUMMARY-${t.id}.md (what you built, what is
stubbed, what needs manual verification, suggested merge order) and make a final
commit. Report: branch name, commit count, test status, and anything the human must
verify by hand.`;
}

function qualityPrompt(t) {
  return `Code-quality pass on track ${t.id} (branch ${t.branch}).

  cd ${REPO}-${t.id}

Raise this branch to the tempest-fastapi-sdk / tempestroid bar: Google docstrings
on every public surface, full type annotations (ruff ANN + mypy --strict), lint
clean under the full select set, ruff format clean, double quotes, idiomatic
imports/collections/async, and complete accurate JSDoc on the client side. APPLY
the fixes (ruff --fix + format for mechanical ones, then docstrings/types/idioms by
hand) WITHOUT changing behavior or public signatures beyond adding types. Never
edit tempestweb/_core/ and never touch files outside this track. Re-run the
branch's own tests to confirm it stays green, then commit
"ref: code-quality pass on ${t.id}". Defer anything needing a behavior change to
QUALITY-${t.id}.md and report it.`;
}

function qaPrompt(t, buildReport) {
  return `Adversarial QA review of track ${t.id} (branch ${t.branch}).

Go to the worktree and review from a clean state:
  cd ${REPO}-${t.id}

The DONE-WHEN you must contest (from docs/agents/MANIFEST.md):
${t.done}

The implement agent reported:
---
${buildReport ?? "(no report — the build agent may have failed; verify what exists on the branch)"}
---

Run the full applicable gate from scratch (make setup if needed; ruff, mypy,
pytest, and node --test as they apply to this track), check every done-when clause
against an actual passing test, and hunt for untested/overclaimed work, edits to
tempestweb/_core, files touched outside the track, and convention violations
(single quotes / missing types / missing docstrings in Python; TypeScript or a
build step in the client). Write REVIEW-${t.id}.md with the VERDICT, the gate
output, the done-when checklist, and prioritized findings, then commit it. Report
the verdict and top findings. Do not implement fixes.`;
}

const TRACKS = [
  {
    id: "T1",
    branch: "feat/client-render",
    agent: "tw-js",
    scope:
      "Pure-JS client renderer. Implement client/dom.js (buildElement + applyPatches for all 5 patch kinds; set data-tw-key on elements), client/style.js (styleToCss covering flex/box-model/border/background/color/typography/dimensions; Color {r,g,b,a}->rgba, Edge->padding/margin), client/events.js (delegated capture -> transport.sendEvent reading data-tw-key), and wire client/tempestweb.js mount() against a mock transport. jsdom tests in tests/client/.",
    done:
      "Building DOM from tests/fixtures/node_initial.json then applying tests/fixtures/patches_all_kinds.json yields the expected DOM; tests/fixtures/style_sample.json maps to the expected CSS; a click on a Button calls the mock transport's sendEvent with the right key.",
    verify: 'node --test "tests/client/**/*.test.js"',
  },
  {
    id: "T2",
    branch: "feat/mode-server",
    agent: "tw-python",
    scope:
      "Mode B (server), phases B0-B2 + B5(SSE). Implement tempestweb/server/ (FastAPI + WebSocket host using tempest-fastapi-sdk patterns where natural), tempestweb/transports/websocket.py (PatchTransport over WS), tempestweb/transports/sse.py (B5: patches server->client via EventSource, events client->server via HTTP POST, SAME PatchTransport interface), tempestweb/runtime/session.py (per-connection session: connect=mount, disconnect=unmount, cancel orphan tasks), client/transport-ws.js and client/transport-sse.js (both implement the transport.js interface). Reconciler from tempestweb._core. pytest with WS and SSE/POST test clients.",
    done:
      "A test client connects over WS, receives initial patches for the counter, sends a click, and receives the resulting Update patch; the SSE transport delivers the same patch stream via EventSource + POST; two connections keep independent state.",
    verify: "pytest tests/unit/test_server*.py -q",
  },
  {
    id: "T3",
    branch: "feat/mode-wasm",
    agent: "tw-python",
    scope:
      "Mode A (WASM/Pyodide). FIRST research the CURRENT state of pydantic-core in Pyodide (post knowledge-cutoff — use web search) and record findings in NOTES-T3.md. Implement public/index.html bootstrap (loads Pyodide + vendored core + an app.py, produces patches in the browser), tempestweb/runtime/wasm.py (Python-side glue), tempestweb/transports/wasm.py (PatchTransport over pyodide.ffi), client/transport-wasm.js. Pure-Python logic must be pytest-covered; the live browser path is documented for manual verification.",
    done:
      "transport-wasm.js + wasm.py implement the interface; the bootstrap is complete and documented. Pure-Python units are green. Live Pyodide run is documented in NOTES-T3.md.",
    verify: "pytest tests/unit/test_wasm*.py -q",
  },
  {
    id: "T4",
    branch: "feat/native-web",
    agent: "tw-python",
    scope:
      "Web capability adapters in tempestweb/native/ as typed awaitables: geolocation, clipboard, notifications, storage (mirror tempestroid/native naming where it maps). client/native.js glue calling navigator.*. Document the Mode-A (browser) vs Mode-B (proxied over WS round-trip) split. pytest with mocked Web APIs.",
    done:
      "Each capability has a typed Python awaitable wrapper + JS glue; signatures are async; the client/server split is documented.",
    verify: "pytest tests/unit/test_native*.py -q",
  },
  {
    id: "T5",
    branch: "feat/cli-devloop",
    agent: "tw-python",
    scope:
      "Flesh out tempestweb/cli/ (new/dev/build/run — keep cli/main.py's parser shape) and tempestweb/devserver/ (file watcher + reload signal, transport-agnostic). `new` scaffolds a runnable project; `dev` watches and triggers reload (stub transport); `build --mode wasm|server` produces the right artifact shape. pytest coverage.",
    done:
      "tempestweb new X creates a runnable project tree; dev watcher detects a change and emits a reload; build --mode produces the expected artifact layout.",
    verify: "pytest tests/unit/test_cli*.py -q",
  },
  {
    id: "T6",
    branch: "feat/docs-site",
    agent: "tw-docs",
    scope:
      "Bilingual MkDocs site (PT-BR default + EN-US under /en/) in the tiangolo/FastAPI didactic style: mkdocs-material + mkdocs-static-i18n + header language switch, and .github/workflows/docs.yml for Pages (build_type: workflow). Pages: landing, installation, architecture (link docs/arquitetura.md), a progressive tutorial building the counter, the wire contract, and placeholders for PWA/SSE. Do NOT rewrite docs/plan.md/roadmap.md/contract.md — link to them. Point the README banner at the Pages URL (PT + EN).",
    done:
      "uv run mkdocs build --strict passes with zero warnings; language switch present; tutorial covers the counter end to end; docs.yml deploy workflow present.",
    verify: "uv run mkdocs build --strict",
  },
  {
    id: "T7",
    branch: "feat/conformance",
    agent: "tw-qa",
    scope:
      "Conformance harness in tests/conformance/: generate patches from the real core and lock the wire-format shape (regenerable goldens); a test asserting two mock transports fed the same patch stream produce identical DOM (the A-vs-B guarantee). New fixtures under tests/fixtures/.",
    done:
      "A pytest suite pins the contract shape and asserts transport-independence of the rendered DOM.",
    verify: "pytest tests/conformance -q",
  },
  {
    id: "T8",
    branch: "feat/examples",
    agent: "tw-python",
    scope:
      "Additional example apps under examples/ (todo-list, a form, an async fetch view) exercising the core widget API (inputs, lists, forms). Each is a view(app)->Widget module like examples/counter/app.py. tests/unit/test_examples.py imports each, builds the view, validates the tree.",
    done:
      "Each example imports, build(view()) validates and yields a tree; input/list/form widgets are exercised.",
    verify: "pytest tests/unit/test_examples.py -q",
  },
  {
    id: "T9",
    branch: "feat/pwa-offline-webpush",
    agent: "tw-js",
    scope:
      "Trilho P — PWA / offline-first / WebPush. Own files: client/pwa/ (manifest.webmanifest emitter, sw.js service worker, register.js), tempestweb/server/webpush.py (VAPID via tempest-fastapi-sdk[webpush] patterns), tests/unit/test_pwa*.py. P0: installable manifest (standalone, theme_color, start_url, maskable icons). P1: service worker precaches the app-shell (client JS always; Mode A also Pyodide + core wheel + app.py) cache-first -> offline after first load. P2: per-resource strategies (stale-while-revalidate assets, network-first data) + offline event queue with replay-on-reconnect (Mode B). P3: WebPush — native notifications.subscribe()/permission awaitables, SW push handler, server-side send (pywebpush). Stub client/build integration against interfaces.",
    done:
      "manifest is valid JSON and installable-shaped; sw.js passes node --check and has precache + fetch strategy; webpush VAPID subscribe/send is unit-tested (pywebpush mocked); offline queue replay is unit-tested. Live install/push documented in NOTES-T9.md.",
    verify: 'pytest tests/unit/test_pwa*.py -q && node --check client/pwa/sw.js',
  },
];

phase("Build");
log(`Launching ${TRACKS.length} track specialists in parallel worktrees off main; each is QA-reviewed as it lands.`);

// Pipeline (no barrier): each track is implemented by its domain specialist, then
// raised to the quality bar by tw-quality (which applies fixes), then adversarially
// verified by tw-qa — all per-track, so a finished track flows through quality+QA
// while other tracks are still building.
const results = await pipeline(
  TRACKS,
  (t) =>
    agent(buildPrompt(t), { label: `build:${t.id}`, phase: "Build", agentType: t.agent }).then(
      (report) => ({ ...t, buildReport: report })
    ),
  (built) =>
    agent(qualityPrompt(built), {
      label: `quality:${built.id}`,
      phase: "Quality",
      agentType: "tw-quality",
    }).then((qualityReport) => ({ ...built, qualityReport })),
  (checked) =>
    agent(qaPrompt(checked, checked.buildReport), {
      label: `qa:${checked.id}`,
      phase: "QA",
      agentType: "tw-qa",
    }).then((qaReview) => ({
      id: checked.id,
      branch: checked.branch,
      buildReport: checked.buildReport,
      qualityReport: checked.qualityReport,
      qaReview,
    }))
);

const ok = results.filter(Boolean);
log(`Done. ${ok.length}/${TRACKS.length} tracks built + quality-passed + QA-reviewed.`);
return ok;
