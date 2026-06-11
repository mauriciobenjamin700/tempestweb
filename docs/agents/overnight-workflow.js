export const meta = {
  name: "tempestweb-overnight",
  description:
    "Parallel build of tempestweb across 8 independent tracks, each in its own git worktree/branch, committing incrementally.",
  phases: [{ title: "Build", detail: "8 track agents in parallel worktrees off main" }],
};

const REPO = "/home/mauriciobenjamin700/projects/my/tempestweb";

// Shared preamble injected into every track agent. Self-sufficient: the agent
// starts with fresh context, so everything it needs is spelled out here.
function preamble(t) {
  return `You are an autonomous build agent working OVERNIGHT, unsupervised. Track ${t.id}.

REPO: ${REPO} (a git repo; base branch "main" is clean and green).
YOUR WORKTREE: ${REPO}-${t.id}
YOUR BRANCH: ${t.branch}

STEP 0 — set up your isolated worktree (do this exactly, with absolute paths):
  git -C ${REPO} worktree add -b ${t.branch} ${REPO}-${t.id} main
  cd ${REPO}-${t.id}
  make setup            # uv venv + deps + npm install (uv cache makes this fast)
Then do ALL your work inside ${REPO}-${t.id}. Never touch the main checkout.

READ FIRST (in your worktree): CLAUDE.md, docs/plan.md, docs/roadmap.md,
docs/contract.md, docs/agents/MANIFEST.md. The contract + golden fixtures in
tests/fixtures/ are the source of truth for the Python<->client wire format.

HARD RULES:
- Do NOT edit tempestweb/_core/** (mechanical vendored copy).
- Do NOT edit files owned by other tracks (see MANIFEST). Stay in your dir/files.
- Program against the documented contract/interfaces. Where you need another
  track's runtime, STUB/MOCK it against the interface — integration happens later.
- Every commit must leave your branch with green automated tests. Run the
  verification below before each commit. Commit GRANULARLY (one logical step =
  one conventional commit: feat:/fix:/test:/docs:/ref:/chore:). End each commit
  message with: Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
- If something needs a real browser/device to verify, write the code + every test
  you CAN automate, and record what needs manual verification in NOTES-${t.id}.md.
- If blocked on a design decision, write the options + your choice in NOTES-${t.id}.md
  and proceed — do not stop the whole track.
- Do NOT git push. Do NOT merge into main or any other branch. Do NOT remove your
  worktree. Leave your branch with all work committed.

YOUR SCOPE: ${t.scope}

DONE WHEN: ${t.done}

VERIFICATION (must pass before each commit): ${t.verify}

Work thoroughly through the whole scope, committing as you go. When the scope is
complete and verification is green, write a short SUMMARY-${t.id}.md (what you
built, what's stubbed, what needs manual verification, suggested merge order) and
make a final commit. Then report: branch name, number of commits, test status,
and anything the human must verify by hand.`;
}

const TRACKS = [
  {
    id: "T1",
    branch: "feat/client-render",
    scope:
      "Pure-JS client renderer (NO TypeScript, NO framework, NO build step). Implement client/dom.js (buildElement + applyPatches for all 5 patch kinds), client/style.js (styleToCss covering flex/box-model/border/background/color/typography/dimensions; Color {r,g,b,a}->rgba, Edge->padding/margin; reference tempestroid Qt translator at ../tempestroid/tempestroid/renderers/qt/style_translator.py), client/events.js (delegated event capture -> transport.sendEvent, read data-tw-key set by dom.js), and wire client/tempestweb.js mount() against a mock transport. Add jsdom tests in tests/client/.",
    done:
      "Building DOM from tests/fixtures/node_initial.json then applying tests/fixtures/patches_all_kinds.json yields the expected DOM; tests/fixtures/style_sample.json maps to the expected CSS; a click on a Button calls the mock transport's sendEvent with the right key.",
    verify: 'node --test "tests/client/**/*.test.js"',
  },
  {
    id: "T2",
    branch: "feat/mode-server",
    scope:
      "Mode B (server), phases B0-B2 + B5(SSE). Implement tempestweb/server/ (FastAPI + WebSocket host using tempest-fastapi-sdk patterns where natural), tempestweb/transports/websocket.py (PatchTransport over WS), tempestweb/transports/sse.py (B5: patches server->client via EventSource, events client->server via HTTP POST, SAME PatchTransport interface), tempestweb/runtime/session.py (per-connection session: connect=mount, disconnect=unmount, cancel orphan tasks), client/transport-ws.js and client/transport-sse.js (both implement the transport.js interface). Reconciler from tempestweb._core (build/diff). pytest with a WS test client and an SSE/POST test client.",
    done:
      "A test client connects over WS, receives initial patches for the counter, sends a click, and receives the resulting Update patch; the SSE transport delivers the same patch stream via EventSource + POST; two connections keep independent state.",
    verify: "pytest tests/unit/test_server*.py -q",
  },
  {
    id: "T3",
    branch: "feat/mode-wasm",
    scope:
      "Mode A (WASM/Pyodide). FIRST research the CURRENT state of pydantic-core in Pyodide (it is post-knowledge-cutoff — use web search) and record findings in NOTES-T3.md. Implement public/index.html bootstrap that loads Pyodide + the vendored core + an app.py and produces patches in the browser; tempestweb/runtime/wasm.py (Python-side glue) and tempestweb/transports/wasm.py (PatchTransport over pyodide.ffi); client/transport-wasm.js. Pure-Python logic must be pytest-covered; the live browser path is documented for manual verification.",
    done:
      "transport-wasm.js + wasm.py implement the interface; the bootstrap is complete and documented. Pure-Python units are green. Live Pyodide run is documented in NOTES-T3.md for manual check.",
    verify: "pytest tests/unit/test_wasm*.py -q",
  },
  {
    id: "T4",
    branch: "feat/native-web",
    scope:
      "Web capability adapters in tempestweb/native/ as typed awaitables: geolocation, clipboard, notifications, storage (mirror tempestroid/native naming where it maps). Add client/native.js glue calling the Web APIs (navigator.*). Document the Mode-A (browser) vs Mode-B (proxied over WS round-trip) split. pytest with mocked Web APIs.",
    done:
      "Each capability has a typed Python awaitable wrapper + JS glue; signatures are async; the client/server split is documented.",
    verify: "pytest tests/unit/test_native*.py -q",
  },
  {
    id: "T5",
    branch: "feat/cli-devloop",
    scope:
      "Flesh out tempestweb/cli/ (new/dev/build/run subcommands — keep cli/main.py's parser shape) and tempestweb/devserver/ (file watcher + reload signal, transport-agnostic). `new` scaffolds a runnable project; `dev` watches and triggers reload (against a stub transport); `build --mode wasm|server` produces the right artifact shape. pytest coverage.",
    done:
      "tempestweb new X creates a runnable project tree; dev watcher detects a change and emits a reload; build --mode produces the expected artifact layout.",
    verify: "pytest tests/unit/test_cli*.py -q",
  },
  {
    id: "T6",
    branch: "feat/docs-site",
    scope:
      "Bilingual MkDocs site (PT-BR default + EN-US under /en/) in the tiangolo/FastAPI didactic style, with mkdocs-static-i18n + Material + a header language switch, and .github/workflows/docs.yml for Pages. Pages: landing, installation, architecture (reuse docs/arquitetura.md), a progressive tutorial building the counter, and the wire contract. Do NOT rewrite docs/plan.md/roadmap.md/contract.md content — link to them.",
    done:
      "uv run mkdocs build --strict passes with zero warnings; language switch present; tutorial covers the counter end to end.",
    verify: "uv run mkdocs build --strict",
  },
  {
    id: "T7",
    branch: "feat/conformance",
    scope:
      "Conformance harness in tests/conformance/: generate patches from the real core and lock the wire-format shape (regenerable goldens); a test asserting that two mock transports fed the same patch stream produce identical DOM (the A-vs-B guarantee). Add any new fixtures under tests/fixtures/.",
    done:
      "A pytest suite pins the contract shape and asserts transport-independence of the rendered DOM.",
    verify: "pytest tests/conformance -q",
  },
  {
    id: "T8",
    branch: "feat/examples",
    scope:
      "Additional example apps under examples/ (todo-list, a form, an async fetch view) exercising the core widget API (inputs, lists, forms). Each is a view(app)->Widget module like examples/counter/app.py. Add tests/unit/test_examples.py that imports each, builds the view, and validates the tree.",
    done:
      "Each example imports, build(view()) validates and yields a tree; input/list/form widgets are exercised.",
    verify: "pytest tests/unit/test_examples.py -q",
  },
  {
    id: "T9",
    branch: "feat/pwa-offline-webpush",
    scope:
      "Trilho P — PWA / offline-first / WebPush (parity with tempest-react-sdk). Own files: client/pwa/ (manifest.webmanifest emitter, sw.js service worker, register.js), tempestweb/server/webpush.py (VAPID via tempest-fastapi-sdk[webpush] patterns), tests/unit/test_pwa*.py. P0: manifest (display=standalone, theme_color, start_url, maskable icons) — installable. P1: service worker precaches the app-shell (client JS always; in Mode A also Pyodide + core wheel + app.py) cache-first — app opens offline after first load. P2: per-resource strategies (stale-while-revalidate assets, network-first data) + an offline event queue with replay-on-reconnect for Mode B. P3: WebPush — native notifications.subscribe()/permission as awaitables, SW push handler, server-side send (pywebpush). Stub the client/build integration against interfaces; do not edit other tracks' files.",
    done:
      "manifest is valid JSON and installable-shaped; sw.js passes node --check and has precache + fetch strategy; webpush VAPID subscribe/send logic is unit-tested (pywebpush mocked); offline queue replay is unit-tested. Live install/push documented in NOTES-T9.md for manual verification.",
    verify: "pytest tests/unit/test_pwa*.py -q && node --check client/pwa/sw.js",
  },
];

phase("Build");
log(`Launching ${TRACKS.length} track agents in parallel worktrees off main.`);

const results = await parallel(
  TRACKS.map((t) => () =>
    agent(preamble(t), { label: t.id, phase: "Build" }).then((report) => ({
      id: t.id,
      branch: t.branch,
      report,
    }))
  )
);

const ok = results.filter(Boolean);
log(`Done. ${ok.length}/${TRACKS.length} tracks reported back.`);
return ok;
