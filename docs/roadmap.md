# Roadmap e fases

!!! info "Estado atual — atualizado em 2026-06-13"
    Tracks **T1–T10 + Trilhos 0/W/A/B/P/N/O/E mesclados na `main`** com gate verde
    (ruff/format/mypy ✓ · pytest 459 pass/1 skip · jsdom 205 pass). Publicado no
    PyPI: **tempestweb 0.5.1**. Legenda de status: **✅** mesclado e com gate verde ·
    **🔶** implementado mas pendente de **verificação real** (browser/device — ver
    `docs/agents/reports/NOTES-T*.md`) · **⬜** não iniciado. Os dois modos rodam um
    app fim-a-fim ao vivo (counter por WS e Pyodide no browser), Trilho E está ✅ ao
    vivo (7/7) e o core já é o pacote `tempest-core` (o `_core/` vendorado foi
    removido). Pendências de alto nível: **Trilho 0 fase 2** (tempestroid passar a
    depender do `tempest-core` + conformância Qt↔Compose) — bloqueada no repo
    tempestroid; e a **verificação ao vivo device-dependente** dos itens 🔶
    (Background Sync com aba fechada, WebPush aba-fechada, geo/clipboard/câmera
    reais), que não dá para automatizar em unit/jsdom.

!!! danger "Lacuna de integração descoberta na verificação (2026-06-11)"
    Os **engines** de ambos os modos existem e passam unit/jsdom, mas a **costura
    CLI ↔ engine nunca foi feita** — `tempestweb build`/`run`/`dev` emitiam
    entrypoints **stub**: o `server.py` do Modo B jogava `NotImplementedError("B0...")`,
    o `bootstrap.js` do Modo A joga `throw "A3: Pyodide bootstrap..."`, e **não
    existe loader Pyodide** (`loadPyodide`). Cada track validou só os próprios
    testes contra stubs (MANIFEST: "integração no merge") — a integração T5↔T2/T3
    ficou pendente.

    **Modo B — RESOLVIDO** (branch `feat/integrate-server-cli`, 2026-06-11):
    `build --mode server` emite `server.py` real (via `create_app`) + `index.html`
    que monta o cliente por WebSocket; `tempestweb run --mode server` sobe uvicorn
    de verdade. **Verificado ao vivo no browser (Playwright):** counter renderiza por
    WS e +/- atualizam a contagem pelo round-trip evento → WS → reconcílio → patch →
    DOM. Junto: fix de serialização (`Style` Pydantic agora lowerado no path de
    runtime) + `mount()` com node inicial diferido pro Modo B.

    **Modo A — RESOLVIDO** (branch `feat/integrate-wasm-cli`, 2026-06-11):
    `build --mode wasm` emite `bootstrap.js` real que carrega Pyodide v314 +
    `pydantic` (`loadPackage`), desempacota o pacote `tempestweb` (`_core`/`runtime`/
    `transports`/`native`) + `app.py` na FS virtual e monta o cliente por bridge
    in-process. **Verificado ao vivo (Playwright):** counter roda Python no browser,
    +/- atualizam por reconciliação in-process, zero-network — **de-risk A0 provado,
    não só pesquisado**. Junto: refactor que torna o import do Modo A livre de
    Starlette (`transports/__init__` lazy nos transportes Modo B).

    Ambos os modos agora rodam um app fim-a-fim. `A2` (handler async com `await`
    ao vivo), Trilho 0 fase 1 (`tempest-core` adotado, `_core/` removido) e Trilho
    E (7/7 ao vivo) já fecharam — resta só o Trilho 0 fase 2 no repo tempestroid.

O desenvolvimento segue um pré-requisito, trilhos compartilhados e dois trilhos de
execução. **Trilho 0** extrai o `tempest-core` do tempestroid. **Trilho W** é o
renderizador-folha web (cliente JS puro), compartilhado pelos dois modos.
**Trilho A** é o **Modo WASM** (Pyodide, Python no browser) — construído primeiro.
**Trilho B** é o **Modo servidor** (FastAPI + WebSocket/SSE) — depois. **Trilho P**
é a camada **PWA / Offline-first / WebPush**. **Trilho N** são as **capacidades
`native/`** (http, audio, share, geo, clipboard, storage) expostas como awaitables.
**Trilho O** é **observabilidade/produção** (telemetry, logger, error boundary,
feature flags, auth). N/O/P são compartilhados pelos dois modos. O plano completo
está em [Plano de design](plan.md).

> Paridade com o `tempest-react-sdk`: o SDK React já entrega em produção — testado
> — todo o conjunto de **capacidades de plataforma** (http/sse/ws/push/sw/offline/
> audio/share/telemetry/feature-flags/auth). O tempestweb herda esse conjunto na
> abordagem "pythônica": componentes vêm do `tempest-core`; as capacidades viram
> `native/` (awaitables) + `transports/` + provedores de produção. App
> **instalável** (PWA), **offline-first** (service worker + app-shell + IndexedDB),
> push por **SSE** e **WebPush** são metas de primeira classe, não polimento. O
> Modo A é o alvo natural de PWA (Python no browser, offline após o load); o Modo B
> ganha install shell + push do servidor.
>
> Decisões herdadas do React SDK: padrão **adapter** (telemetry/feature-flags —
> troca o backend sem tocar a app), divisão **cliente faz o browser-flow / servidor
> é dono do endpoint** (WebPush), **idempotency key + retry** em toda mutation
> (base do replay offline).

## Trilho 0 — `tempest-core` (pré-requisito)

| Fase | Escopo | Status |
|---|---|---|
| 0.0 | Extrair IR/reconciliador/estado/estilo/widgets/validators para o pacote `tempest-core`; tempestroid passa a depender dele | 🔶 fase 1 (pacote `tempest-core` 0.1.0 criado — ruff/pyright/pytest verdes; **tempestweb** adota e dropa `_core/` vendorado, branch `feat/adopt-tempest-core`, ambos modos verificados ao vivo). **tempestroid** depender dele + conformância Qt↔Compose = fase 2 pendente |
| 0.1 | Extrair extras de paridade (navigation, theme, i18n, animation, forms, lists) sob demanda da web | ✅ (o pacote já carrega navigation/theme/i18n/animation/forms/lists — incluídos no core extraído) |

!!! warning "Guarda do Trilho 0"
    A extração só fecha com a suite completa do tempestroid — **incluindo a
    conformância Qt↔Compose** — verde após a troca do core interno pelo pacote.

## Trilho W — cliente JS (renderizador-folha web)

JavaScript **puro**: sem TypeScript, sem framework, sem etapa de build. Compartilhado
pelos Modos A e B.

| Fase | Escopo | Status |
|---|---|---|
| W0 | Fundação do repo: pacote, ferramental, `tempestweb --help`, dep em `tempest-core` | ✅ (dep `tempest-core` real desde `feat/adopt-tempest-core`; `_core/` vendorado removido) |
| W1 | Aplicador de patches no DOM (insert/remove/update/reorder/replace), testado com jsdom | ✅ |
| W2 | Tradutor `Style → CSS` (flexbox + box model + tipografia) | ✅ |
| W3 | Captura de eventos + interface de transporte (`sendEvent`/`onPatches`) | ✅ |

## Trilho A — Modo WASM (Pyodide) — primeiro

| Fase | Escopo | Status |
|---|---|---|
| A0 | **De-risk crítico:** `tempest-core` + `pydantic` rodando no Pyodide; reconciliador produz patches no browser | ✅ ao vivo (Pyodide v314, pydantic carrega, counter no browser — 2026-06-11, branch `feat/integrate-wasm-cli`) |
| A1 | Transporte WASM (FFI Pyodide): patches Python→DOM, eventos DOM→Python; `counter` 100% no browser | ✅ ao vivo (Playwright: +/- zero-network in-process) |
| A2 | Loop async no browser: handler `async` com `await` atualiza a UI sem travar a aba | ✅ ao vivo (branch `feat/wasm-async-a2`: example `async_demo`, MutationObserver capturou `loading…`→`done` num clique, aba sem travar) |
| A3 | `tempestweb build --mode wasm`: saída estática (Pyodide + wheel do core + `app.py`) | ✅ |
| A4 | `tempestweb dev` (modo A): watcher + reload da aba (hot restart) | ✅ (via T5 devserver) |
| A5 | `native/` web (modo A): primeiro backend das capacidades — geolocation, clipboard, notifications, storage como awaitables. Conjunto completo detalhado no **Trilho N** | ✅ (consolidado no Trilho N) |

## Trilho B — Modo servidor (FastAPI + WS/SSE) — depois

| Fase | Escopo | Status |
|---|---|---|
| B0 | Host FastAPI + tempest-fastapi-sdk com endpoint WS; patches iniciais ao conectar | ✅ ao vivo (counter por WS no browser, 2026-06-11) |
| B1 | Transporte WebSocket (Python + JS); `counter` por WS — **mesmo `app.py` do Modo A** | ✅ ao vivo (Playwright, round-trip +/- verificado) |
| B2 | Sessão e ciclo de vida por conexão (connect=mount, disconnect=unmount, cancelamento de tasks) | ✅ |
| B3 | `native/` split cliente/servidor (camera/geo no cliente, proxiados por WS) | ✅ (`ProxyBridge` + split documentado em T4) |
| B4 | `tempestweb dev` (modo B): reload do servidor + push aos clientes | ✅ (via T5 devserver) |
| B5 | **Transporte SSE:** patches servidor→cliente via `EventSource`; eventos cliente→servidor via HTTP POST. `transports/sse.py` + `transport-sse.js`, mesma interface do W3. Reconnect exponencial (até 10 tentativas), heartbeat `ping`, `namedEvents`, `withCredentials` p/ cookie-auth — paridade com `createEventStream` do React SDK. Alternativa ao WS para infra que bloqueia WebSocket | ✅ |

## Trilho P — PWA / Offline-first / WebPush (compartilhado)

Camada instalável e offline, compartilhada pelos dois modos. Depende do cliente
(W3) e do empacotamento (A3 para o app-shell WASM). O service worker (P1) é
pré-requisito do WebPush (P3). Paridade com o `tempest-react-sdk`.

| Fase | Escopo | Status |
|---|---|---|
| P0 | **Manifest + ícones:** `tempestweb build` emite `manifest.webmanifest` (`display: standalone`, `theme_color`, `start_url`, ícones maskable). App instalável ("Add to Home") + hook `beforeinstallprompt` com **soft pre-prompt** (pede em contexto, não a frio). Lighthouse "installable" verde | ✅ ao vivo wasm (branch `feat/wire-pwa-build`: build emite manifest+ícones, linkado no index.html, `validate_installable`=[] + standalone confirmado no browser) |
| P1 | **Service worker + app-shell (base offline-first):** SW registrado faz precache do shell — cliente JS sempre; no Modo A também Pyodide + wheel do core + `app.py`. Cache-first no shell; app abre **offline após o 1º load**. Resolve o cold-start do bundle WASM. Inclui **update lifecycle**: detectar nova versão → prompt "recarregar", `skipWaiting`/`clientsClaim`, limpar caches antigos no `activate` — paridade com `registerServiceWorker({onUpdate})` + `skipWaiting`/`unregisterAll` do React SDK | ✅ ao vivo wasm (build injeta precache+versão no sw.js, registra como module worker; Playwright: SW ativa, precache 13 assets, **server down → shell serve do cache**). Gap: Pyodide é CDN cross-origin, não precacheável (offline boot completo = follow-up) |
| P2 | **Offline-first em runtime:** store local **IndexedDB owner-scoped por domínio** (`put/bulkPut/get/list/update/updateMany/delete/clear/count`, paridade com `createOfflineStore`) p/ dados/estado/rascunhos/histórico SSE; `navigator.storage.persist()` p/ não ser despejado; estratégias por recurso (stale-while-revalidate p/ assets, network-first p/ dados); fila de mutations offline + **Background Sync** (replay com a aba fechada) + replay no reconnect (Modo B); banner online/offline ligado ao `ConnectivityEvent` do core | 🔶 (store/sync testados em jsdom; Background Sync real pendente) |
| P3 | **WebPush Notifications:** VAPID via `tempest-fastapi-sdk[webpush]`; **cliente faz o browser-flow** (`subscribe`/`unsubscribe`/`isSubscribed`, permissão, `isPushSupported`), **servidor é dono do endpoint** (callbacks subscribe/unsubscribe → store de subscriptions por usuário/tópico, limpa `410 Gone`, rotação de chave); SW: `installPushHandler` + `installNotificationClickHandler` (**actions** + clique → `DeepLinkEvent` do core) + **Badging API**; `native/` expõe `notifications.subscribe()` como awaitable; envio server-side (pywebpush). Funciona com a aba fechada | 🔶 (fluxo + endpoint testados; push real aba-fechada pendente) |
| P4 | **Gate PWA no CI:** Lighthouse PWA (installable + offline), teste de SW (precache/update), teste de push end-to-end (subscribe → envio → notificação). Trava o merge | ✅ (job CI presente; execução ao vivo do Lighthouse pendente) |
| P5 | **Extras de manifest (valor de produto):** `shortcuts`, `share_target` (recebe conteúdo compartilhado), file handlers. Pareia com `native/share` (Trilho N) | ✅ |

!!! note "PWA por modo"
    **Modo A** é o alvo pleno: instalável + offline real (Python roda no browser,
    sem servidor após o load). **Modo B** ganha install shell + WebPush; o offline
    é parcial (precisa do servidor para reconciliar), então P2 cobre fila/replay de
    eventos no reconnect. P0/P1/P3/P4 são compartilhados; P2 tem ramo por modo.

!!! warning "Limitações de plataforma + segurança"
    **iOS/Safari:** WebPush exige a PWA **instalada** (Safari 16.4+, `display:
    standalone`, via APNs); **Background Sync não existe** no Safari — o replay cai
    no reconnect com a aba aberta (P2). Detectar e degradar com elegância.
    **VAPID/segredos:** chaves VAPID e credenciais de push vivem como env/secret,
    **nunca** commitadas.

## Trilho N — capacidades `native/` (compartilhado)

Adaptadores de Web API expostos como **awaitables tipados** em Python. Dois
backends por capacidade: **Modo A** chama a Web API direto (FFI Pyodide); **Modo
B** proxia por um round-trip (WS/SSE) — a API Python é idêntica. Cada capacidade
espelha um módulo de plataforma do `tempest-react-sdk`. Expande o A5 (que só
listava geo/clipboard/notifications/storage).

| Fase | Escopo | Status |
|---|---|---|
| N0 | **http:** `native.http` com cliente tipado — `retry`, `generate_idempotency_key`, upload com progresso, `poll`. **Idempotency key + retry são a base do replay offline** (P2). Modo A: `fetch`/httpx-pyodide; Modo B: httpx no servidor | ✅ |
| N1 | **audio:** `await audio.play(src, volume=...)` — chime de notificação/sucesso. Autoplay bloqueado até a 1ª interação (resolve com `None`); pareia com WebPush (P3) | ✅ |
| N2 | **share:** `await share(title, text, url, files=...)` + `is_share_supported()`, com fallback gracioso (clipboard). Pareia com `share_target` (P5) | ✅ |
| N3 | **geolocation / clipboard / storage:** awaitables; `storage` por cima de IndexedDB (P2). Migra o conteúdo do A5 pra cá | 🔶 (wrappers testados; geo/clipboard reais pendentes) |
| N4 | **camera / mídia:** captura no cliente; no Modo B proxiada por WS (foto volta tipada). Herda o B3 | 🔶 (proxy testado; captura real pendente) |

## Trilho O — observabilidade / produção (compartilhado)

Provedores de produção, todos com **padrão adapter** (interface mínima, troca o
backend sem tocar a app) herdado do `tempest-react-sdk`. Servidor reusa o
`tempest-fastapi-sdk` onde houver (JWT, e-mail, métricas).

| Fase | Escopo | Status |
|---|---|---|
| O0 | **telemetry:** provedor + adapters (console / Sentry / PostHog). Instrumenta eventos de SW, push (subscribe/entrega), replay offline, erros | ✅ |
| O1 | **logger:** `create_logger` com sinks plugáveis (console + custom); níveis tipados | ✅ |
| O2 | **error boundary:** captura erro de render → fallback visual + hook de report (liga no telemetry). Complementa o rollback de state que o core já faz | ✅ |
| O3 | **feature flags:** provedor + adapters (InMemory p/ dev → GrowthBook / LaunchDarkly). `is_enabled(key)` / `get(key, default)` / `on_change` | ✅ |
| O4 | **auth (cliente):** store de auth + guarda de rota, `decode_jwt` / `is_jwt_expired`, fila de refresh; OAuth. Servidor reusa `JWTUtils` do `tempest-fastapi-sdk` | ✅ |

## Pós-convergência

| Fase | Escopo | Status |
|---|---|---|
| C | Polimento: `new`/`build --mode`/`run` + hot reload com estado (B primeiro) | ✅ (CLI completo; hot reload preserva-estado ainda é restart) |
| D | Conformância A-vs-B: mesma `view()` → DOM idêntico nos dois modos, no CI | ✅ |
| E | Paridade (reusa extras do `tempest-core`): rotas/URL, listas, overlays, animação CSS, gestos, formulários, mídia, tema/i18n/a11y | ✅ ao vivo (branch `feat/trilho-e-parity`, 7/7 verificados no browser: E.1 rotas URL→view · E.2 listas virtualizadas · E.3 overlays · E.4 animação CSS · E.5 gestos · E.6 forms+media · E.7 a11y/i18n/theme). Follow-ups ✅: view→URL (pushState) + scrollbar proporcional, ambos mesclados e testados (`test_server_navigate.py` · `router.test.js` · `virtualize.test.js`) |

!!! note "Conformância (fase D)"
    Diferente do tempestroid (Qt vs Compose, dois tradutores de `Style`), aqui há
    **um único** tradutor `Style → CSS` no cliente JS. A suite de conformância fixa
    que o **transporte** (WASM vs WebSocket) não altera o resultado: a mesma
    `view()` precisa produzir o mesmo DOM no Modo A e no Modo B.

## Convergência

O mesmo `view()`/state roda nos dois modos sem mudar uma linha. `tempestweb build
--mode wasm|server` escolhe o transporte. O cliente JS (Trilho W) é idêntico nos
três transportes; só a implementação difere (`transport-wasm.js` ·
`transport-ws.js` · `transport-sse.js`), todas atrás da mesma interface do W3.
As capacidades `native/` (Trilho N) têm dois backends por capacidade — mesma API
Python, Modo A chama a Web API direto, Modo B proxia por round-trip. A camada
PWA/offline/WebPush (Trilho P) é compartilhada: o mesmo manifest + service worker
servem os dois modos, com o ramo offline (P2) divergindo só no que cada modo
consegue fazer sem servidor. A camada de produção (Trilho O) é puro Python tipado
sobre o padrão adapter — idêntica nos dois modos. Resultado: o `view()`, o estado,
as capacidades, a observabilidade e a casca PWA são escritos **uma vez** e o
`--mode` só troca o transporte.
