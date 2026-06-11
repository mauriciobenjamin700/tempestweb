# Manifesto de agentes — build paralelo overnight

Plano de trabalho para **vários agentes em paralelo**, cada um numa **worktree +
branch própria**, commitando incrementalmente. O autor revisa e faz merge depois.

## Princípios

- **Tracks são independentes a nível de arquivo** (dirs/arquivos disjuntos) → rodam
  em paralelo sem conflito de merge.
- Onde um track precisa do runtime de outro, ele **programa contra o contrato**
  (`docs/contract.md` + as interfaces JSDoc/Protocol já no repo) e **mocka/stuba** a
  dependência. A integração real fica para o merge supervisionado.
- Cada track fecha no seu **"feito quando"** com **teste automatizado verde** antes
  de cada commit. O que exigir browser/device real: escreva o código + os testes
  automatizáveis e **marque no commit** o que falta verificar à mão.
- **Não toque** `tempestweb/_core/**` (cópia mecânica) nem arquivos de outro track.
- Commits convencionais, granulares. Linha de co-autoria no final.

## Base

Branch base limpa: **`main`** (fundação já commitada: core vendorado, contrato +
fixtures, esqueleto do pacote, stubs do cliente, harness de teste, CI, Makefile,
docs). Gate global: `make check` (ruff + mypy + pytest + JS jsdom).

## Tracks

| ID | Branch | Dir/arquivos próprios | Escopo (fases do roadmap) | Feito quando | Verificação |
|----|--------|----------------------|---------------------------|--------------|-------------|
| **T1** | `feat/client-render` | `client/dom.js`, `client/style.js`, `client/events.js`, `client/tempestweb.js`, `tests/client/*` | W1 (patches→DOM), W2 (Style→CSS), W3 (eventos), mount com transporte mock | Aplicar `patches_all_kinds.json` sobre o DOM de `node_initial.json` dá o DOM esperado; `style_sample.json`→CSS esperado; click via transporte mock chama `sendEvent` | `node --test "tests/client/**/*.test.js"` verde |
| **T2** | `feat/mode-server` | `tempestweb/server/*`, `tempestweb/transports/{websocket,sse}.py`, `tempestweb/runtime/session.py`, `client/transport-{ws,sse}.js`, `tests/unit/test_server*.py` | B0 (host FastAPI+WS), B1 (transporte WS), B2 (sessão/ciclo de vida), **B5 (transporte SSE: EventSource + POST, mesma interface)** | Cliente de teste recebe patches iniciais, manda evento, recebe update — via WS **e** via SSE/POST; sessões isoladas | `pytest tests/unit/test_server*.py` verde |
| **T3** | `feat/mode-wasm` | `tempestweb/transports/wasm.py`, `tempestweb/runtime/wasm.py`, `client/transport-wasm.js`, `public/index.html` (bootstrap), `tests/unit/test_wasm*.py` | A0 (de-risk Pyodide — **pesquisar estado atual do pydantic-core no Pyodide**), A1 (transporte WASM), A3 (bootstrap/bundle estático) | Bootstrap carrega Pyodide + core vendorado + `app.py` e produz patches no browser; transporte implementa a interface. **A0/A1 ao vivo exigem browser → marcar verificação manual** | `pytest tests/unit/test_wasm*.py` (lógica puramente Python) verde + doc dos passos manuais |
| **T4** | `feat/native-web` | `tempestweb/native/*`, `client/native/*`, `tests/unit/test_native*.py` | **Trilho N completo:** N0 (`http`: retry + idempotency key + upload + poll — base do replay offline), N1 (`audio`), N2 (`share`), N3 (`geolocation`/`clipboard`/`storage`), N4 (`camera`) como awaitables tipados + esqueleto do split cliente/servidor (B3, protocolo `native_call`/`native_result` do contract.md) | Cada capacidade tem wrapper Python tipado + glue JS; assinaturas awaitable; `http` faz retry com backoff e não duplica com idempotency key; split documentado | `pytest tests/unit/test_native*.py` verde (mock das Web APIs) |
| **T5** | `feat/cli-devloop` | `tempestweb/cli/*` (exceto `main.py` topo), `tempestweb/devserver/*`, `tests/unit/test_cli*.py` | C (`new` scaffold rodável, `dev` watcher + reload, `build`/`run` dirigindo os dois modos) | `tempestweb new x` cria projeto rodável; `dev` watcher detecta mudança e dispara reload (stub de transporte); `build --mode` gera artefato | `pytest tests/unit/test_cli*.py` verde |
| **T6** | `feat/docs-site` | `docs/**` (exceto os planos já escritos), `mkdocs.yml`, `.github/workflows/docs.yml` | Site MkDocs **bilíngue PT-BR (default) + EN-US** estilo tiangolo/FastAPI: landing, instalação, arquitetura, tutorial progressivo, contrato, referência | `uv run mkdocs build --strict` zero warnings; seletor de idioma; tutorial cobre counter | `mkdocs build --strict` verde |
| **T7** | `feat/conformance` | `tests/conformance/*`, `tests/fixtures/*` (novas fixtures) | D (harness golden A-vs-B): mesma `view()` → mesmo DOM nos dois modos; trava o wire contract | Suite que gera patches do core e fixa o shape; teste que garante que dois transportes mock produzem DOM idêntico | `pytest tests/conformance` verde |
| **T8** | `feat/examples` | `examples/**` (exceto counter), `tests/unit/test_examples.py` | Mais exemplos: todo-list, formulário, fetch async — exercitando a API de widgets do core | Cada exemplo importa, `build(view())` valida e produz árvore; cobre widgets de input/lista/form | `pytest tests/unit/test_examples.py` verde |
| **T9** | `feat/pwa-offline-webpush` | `client/{pwa,sw,offline,push}/*`, `tempestweb/pwa/*`, `tempestweb/server/webpush.py`, `tests/unit/test_pwa*.py` | **Trilho P completo:** P0 (manifest instalável + soft install-prompt), P1 (service worker + app-shell + **update lifecycle**), P2 (IndexedDB owner-scoped + `storage.persist()` + **Background Sync** + fila/replay), P3 (WebPush VAPID: cliente-flow / servidor-endpoint, store de subscriptions, notification actions/click→DeepLink/Badging), P4 (gate PWA no CI: Lighthouse + offline + push e2e), P5 (manifest extras: shortcuts/share_target/file handlers) | manifest válido/instalável; `sw.js` passa `node --check` com precache+fetch+update; WebPush subscribe/send + fila offline com teste unitário (pywebpush mockado); job de CI do gate presente; install/push ao vivo em `NOTES-T9.md` | `pytest tests/unit/test_pwa*.py` + `node --check client/sw/sw.js` |
| **T10** | `feat/observability` | `tempestweb/observability/*`, `tests/unit/test_observability*.py` | **Trilho O completo:** O0 (`telemetry`: provider + adapters console/sentry/posthog), O1 (`logger`: sinks plugáveis), O2 (`error_boundary`: fallback + report), O3 (`feature_flags`: adapters in_memory/growthbook/launchdarkly), O4 (`auth`: store + guarda de rota + decode/expiry JWT + refresh queue) — todos no **padrão adapter** | Cada provider tem interface mínima + ≥1 adapter; trocar adapter não muda chamadas; teste unitário por provider (adapters de terceiros mockados) | `pytest tests/unit/test_observability*.py` verde |

## Especialistas (agentType) + estágio QA

Cada track é um **pipeline de 3 estágios** (sem barreira — track que fecha flui pra
qualidade+QA enquanto outros ainda constroem):

1. **build** — o especialista de domínio implementa o escopo.
2. **quality** — `tw-quality` eleva ao padrão (docstrings google, tipagem forte
   ANN+mypy strict, lint completo, idiomas) e **aplica fixes**, mantendo verde.
3. **qa** — `tw-qa` revisa adversarialmente do zero e reporta (`REVIEW-<ID>.md`).

| Especialista | Onde | Foco |
|---|---|---|
| **tw-python** | build de T2, T3, T4, T5, T8, T10 | FastAPI/async/pydantic, mypy --strict, aspas duplas, docstrings EN |
| **tw-js** | build de T1, T9 | JS puro (sem TS/framework/build), JSDoc, jsdom, contrato/fixtures |
| **tw-docs** | build de T6 | MkDocs bilíngue tiangolo, `--strict`, deploy Pages, docs↔código |
| **tw-quality** | estágio quality de **toda** branch | padrão sdk/tempestroid: docstrings, tipagem, lint, boas práticas — aplica fixes |
| **tw-qa** | T7 + estágio qa de **toda** branch | roda o gate do zero, contesta o "feito quando", caça overclaim |

Gate do projeto já reflete o padrão: ruff `select` inclui `ANN` (anotações) + `D`
(docstrings google), `flake8-quotes` double, `mypy --strict`. `make check` falha se
faltar docstring ou tipo — então o padrão é enforçado automaticamente, e o
`tw-quality` garante a qualidade idiomática que o linter não pega.

`tw-docs` é dono permanente da doc: mantém o site sincronizado com o código e
garante o build/deploy das Pages (não só na noite — sempre que a superfície muda).

## Dependências (para o merge da manhã, não para a execução)

- T3 (wasm) e T2 (server) consomem o cliente real do **T1** na integração. Durante
  a noite ambos programam contra a interface (`client/transport.js`) e stubam.
- T7 (conformance) referencia T1/T2/T3 na integração; à noite trava só o contrato.
- **T9 (PWA)** consome o cliente do **T1** (app-shell), o empacotamento do **T3**
  (precache de Pyodide+core no Modo A) e o servidor do **T2** (envio WebPush);
  à noite programa contra as interfaces e stuba.
- **T10 (observability)** é ortogonal — dirs próprios, sem dependência de runtime de
  outro track; pode mergear a qualquer momento após o T1.
- Ordem de merge sugerida: T1 → T2/T3 → T4 → T9 → T5/T7/T8/T10 → T6 (docs por
  último, refletindo o que entrou).

> **Tracks com trabalho prévio (rodada anterior interrompida):** **T1** já está
> completo e verde (W1/W2/W3); **T3** tem só a pesquisa A0; **T9** tem só o P0. O
> agente de build de cada track DEVE inspecionar `git log` da própria branch antes
> de começar e **continuar de onde parou** — nunca refazer trabalho já commitado e
> verde.

## Regra de parada

Cada agente para quando seu "feito quando" está verde e o escopo coberto. **Não
ficar em loop** inventando trabalho fora do track. Se bloquear por uma decisão de
design, registrar num arquivo `NOTES-<ID>.md` na branch e seguir para o próximo
item do track.
