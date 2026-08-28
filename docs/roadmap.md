# Roadmap e fases

!!! info "Estado atual — atualizado em 2026-07-11"
    Tracks **Trilhos 0/W/A/B/P/N/O/E/S + Trilho T mesclados na `main`** com gate
    verde (ruff/format/mypy ✓ · pytest 831 pass/1 skip · jsdom 439 pass). Última
    versão publicada no PyPI: **tempestweb 0.49.0**; o **Trilho T** (paridade de
    capacidades com a plataforma web — Tiers 1–3 + canal de eventos nativo T-EV com
    12 capacidades de stream) chega na **0.50.0**. Legenda de status: **✅** mesclado e com gate verde ·
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
| 0.0 | Extrair IR/reconciliador/estado/estilo/widgets/validators para o pacote `tempest-core`; tempestroid passa a depender dele | ✅ **fase 2 fechada** (verificado 2026-08-23): **tempestweb** pina `tempest-core>=0.15.0` sem `_core/` vendorado; **tempestroid** pina `tempest-core>=0.11.0`, também sem core vendorado, e tem suíte de conformância Qt↔Compose própria (`tests/conformance/test_conformance.py` — goldens dos **dois** tradutores de `Style`, paridade de cobertura campo a campo e tripwire das divergências intencionais de widget; 234 testes verdes). O core tem dois consumidores de fato, que era o ponto |
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
| B1 | Transporte WebSocket (Python + JS); `counter` por WS — **mesmo `app.py` do Modo A** | ✅ ao vivo (Playwright, round-trip +/- verificado). **Reconnect** com backoff exponencial + jitter (`backoffDelay`), buffer de saída **só de `event`** (frames connection-scoped — `native_result`/`native_event` — não são bufferados p/ não agir em id morto no servidor fresco; cap + drop-oldest logado) drenado no reopen, hook `onReconnect`; listeners do socket velho removidos + guard contra timer de reconnect duplo — paridade de resiliência com o SSE (que herda o reconnect do `EventSource`). Servidor faz estado fresco por conexão → reconnect re-renderiza e o DOM re-sincroniza; resume de sessão (replay exato do estado antigo) é follow-up do servidor |
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
| P0 | **Manifest + ícones:** `tempestweb build` emite `manifest.webmanifest` (`display: standalone`, `theme_color`, `start_url`, ícones maskable). App instalável ("Add to Home") + hook `beforeinstallprompt` com **soft pre-prompt** (pede em contexto, não a frio). Lighthouse "installable" verde | ✅ ao vivo wasm (branch `feat/wire-pwa-build`: build emite manifest+ícones, linkado no index.html, `validate_installable`=[] + standalone confirmado no browser). **Install UX** (adotado do famachapp): `state.method` classifica native/ios/manual, cooldown de recusa (`recordInstallDecline`/`canPromptInstall`, 7 dias) e `post-install-redirect.js` (overlay pós-`appinstalled`). Manifest inclui `launch_handler: focus-existing` (reusa janela aberta) + `display_override` (adotado do famachapp) em ambos emissores (JS + Python) |
| P1 | **Service worker + app-shell (base offline-first):** SW registrado faz precache do shell — cliente JS sempre; no Modo A também Pyodide + wheel do core + `app.py`. Cache-first no shell; app abre **offline após o 1º load**. Resolve o cold-start do bundle WASM. Inclui **update lifecycle**: detectar nova versão → prompt "recarregar", `skipWaiting`/`clientsClaim`, limpar caches antigos no `activate` — paridade com `registerServiceWorker({onUpdate})` + `skipWaiting`/`unregisterAll` do React SDK | ✅ ao vivo wasm (build injeta precache+versão no sw.js, registra como module worker; Playwright: SW ativa, precache 13 assets, **server down → shell serve do cache**). Pyodide same-origin resolvido: `tempestweb build --offline` (e `run --offline`) vendora runtime + wheels do core em `pyodide/`, aponta o bootstrap pra cópia local e inclui tudo no precache → boot 100% offline (`vendor_pyodide`, `test_wasm_offline_build_vendors_and_precaches_pyodide`) |
| P2 | **Offline-first em runtime:** store local **IndexedDB owner-scoped por domínio** (`put/bulkPut/get/list/update/updateMany/delete/clear/count`, paridade com `createOfflineStore`) p/ dados/estado/rascunhos/histórico SSE; `navigator.storage.persist()` p/ não ser despejado; estratégias por recurso (stale-while-revalidate p/ assets, network-first p/ dados); fila de mutations offline + **Background Sync** (replay com a aba fechada) + replay no reconnect (Modo B); banner online/offline ligado ao `ConnectivityEvent` do core | 🔶 (store/sync testados em jsdom; **SW drena a fila sozinho** via import estático de `store/sync.js` no evento `sync` (auto-registrado no enqueue) **e** `periodicsync` (opt-in do app via `native.bgsync.register_periodic` com tag `tw-offline*` — Periodic Sync é permission-gated) — não só pinga clientes; fallback pro replay-por-cliente se o drain falhar; replay com política compartilhada: **dead-letter** de poison message (max-attempts) + **lane de conflito** (409), fila nunca trava; `isCacheable` não cacheia 4xx/5xx/opaque, cap por ordem de inserção no runtime cache, **fallback de navegação offline** pro shell, `persistStorage()` no build da fila. **Banner online/offline** (`connectivity-banner.js`, ligado ao `ConnectivityEvent` via `network.js`) **auto-montado nos 3 shells** (wasm/server/transpile), idempotente por documento. **Read-side delta-sync** (adotado do famachapp/`tempest-react-sdk`): `pull.js` (`createPull` watermark+cursor+single-flight, `mergeRemoteInto` LWW+tombstone+guard de pending, `createWatermark`), `sync-status.js` (`createSyncController` push+pull + store observável phase/pending/lastSyncedAt) e `sw-bridge.js` (SW→página: `OFFLINE_PULL` reconcilia com o token da página). **Exposto ao Python** via `native.sync` (`configure`/`now`/`status`/`watch` streaming) — bridge auto-wired na 1ª config. **Cache de binário grande** (`asset-cache.js`: `ensureCached` dedup in-flight + `syncAssets` manifest de versão → `refreshed` p/ resetar sessão, adotado do model-sync do famachapp). Corrida SW-drain × replay da página é coberta só por idempotência (double-send seguro). Background Sync **real com aba fechada medido em Chrome** na 0.110.0: 2 mutações replicadas 1,01 s após fechar a aba, 3 ms após o reconnect, fila vazia — antes disso o `import()` dinâmico do worker era proibido por spec e todo sync caía no fallback; Periodic Sync segue exigindo permissão → verificação manual) |
| P3 | **WebPush Notifications:** VAPID via `tempest-fastapi-sdk[webpush]`; **cliente faz o browser-flow** (`subscribe`/`unsubscribe`/`isSubscribed`, permissão, `isPushSupported`), **servidor é dono do endpoint** (callbacks subscribe/unsubscribe → store de subscriptions por usuário/tópico, limpa `410 Gone`, rotação de chave); SW: `installPushHandler` + `installNotificationClickHandler` (**actions** + clique → `DeepLinkEvent` do core) + **Badging API**; `native/` expõe `notifications.subscribe()` como awaitable; envio server-side (pywebpush). Funciona com a aba fechada. **`pushsubscriptionchange`** (adotado do gap do famachapp): SW re-subscreve com a chave da própria oldSubscription e re-POSTa pra `/webpush/subscribe` (sem chave armazenada/injetada; fallback = notifica clientes) — rotação/expiração de VAPID não quebra push em silêncio. **Supressão de auto-notificação** (adotado do famachapp): o `subscribe()` grava o endpoint ativo (`getActivePushEndpoint`) e a fila carimba `X-Push-Endpoint` em cada mutação, pro servidor não notificar o próprio device que fez a mudança | ✅ (medido 2026-08-27 contra o **FCM real**, com a aba fechada: subscribe devolve endpoint `fcm.googleapis.com/fcm/send/…`, `pywebpush` responde **201** em ~1,0 s e o worker mostra a notificação com zero páginas abertas; chave VAPID trocada → **403**; subscription cancelada → **410 Gone**. **Achou defeito**: o `410` nunca chegava ao `SendOutcome` — o serviço só capturava o `WebPushError` próprio e o `pywebpush` levanta `WebPushException`, então a limpeza de endpoint morto nunca rodou em produção, só contra os senders fake dos testes. Corrigido; o `total` do store agora cai de 2 para 1 sozinho. `pushsubscriptionchange` exercitado no worker real (evento sintético, `subscribe()` de verdade): re-subscreve com a chave da `oldSubscription`, ganha endpoint novo e re-POSTa `/webpush/subscribe` — 200 no servidor, com a aba fechada) |
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
| N3 | **geolocation / clipboard / storage:** awaitables; `storage` por cima de IndexedDB (P2). Migra o conteúdo do A5 pra cá | ✅ (geo e clipboard medidos em Chrome real 2026-08-23 — geo: concedida → `located` na posição injetada, negada → `error: permission_denied`, e volta a localizar; clipboard: conteúdo lido de volta do sistema. **`storage` medido 2026-08-27 e a medição achou defeito**: `browserDeps()` não injetava `deps.store`, então Modos A e B caíam no fallback de `localStorage` — `indexedDB.databases()` vazio, 142.890 caracteres crus no `localStorage` e o codec `deflate` respondendo `supported=True` sem comprimir nada. Corrigido; agora o mesmo app grava em `tempestweb@1`, `localStorage` vazio, `bulk` de 142.890 caracteres em **10.276 bytes** deflated, sobrevive ao reload (`intact=True`) e some no `remove()` de tudo. Quota reportada: 10,7 GB contra os ~5 MB do `localStorage`) |
| N4 | **camera / mídia:** captura no cliente; no Modo B proxiada por WS (foto volta tipada). Herda o B3 | ✅ (medido 2026-08-27 com a **câmera virtual do OBS**, dirigindo o Chrome do Windows por CDP a partir do WSL: `capture()` devolve `Photo` tipado — `image/jpeg`, 2560×1080, 22.772 chars de base64, `ref=blob:tw:1` — em **72 ms**; `include_bytes=False` devolve só o `ref`, com os pixels no cliente; `CameraPreview.on_frame` entrega 12 frames com gaps de **242–264 ms** contra os 250 ms declarados; permissão negada levanta `permission_denied` e o app reporta em vez de travar. Esclareceu de quebra que `CameraFrameEvent.data` no browser é **JPEG**, não o RGB cru que a docstring do core descreve — agora escrito em `docs/advanced/capabilities.md`) |

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

## Trilho S — segurança & produção (hardening rumo ao profissional)

!!! success "Estado (atualizado 2026-07-11) — produção-ready"
    Os modos **estáticos** (A/WASM e C/transpile) são **produção-ready** (bundles
    de CDN, superfície de servidor ~zero). O **Modo B (servidor)** agora se
    endurece via `create_app(..., security=SecurityConfig(...), metrics=...)`:
    auth gate, CORS + `Origin` no WS, `max_connections`/`max_message_bytes`/
    rate-limit por IP, headers de segurança, verificação de JWT, `/health` e
    `/metrics` — com deploy de referência (Docker + nginx TLS/WS + sticky). O
    núcleo (**S0/S1/S2/S3/S5/S6/S11 ✅**) está fechado; roda profissional.
    Os 🔶 restantes são **enhancements, não bloqueadores**: S4 backend de sessão
    Redis (sticky-sessions cobre multi-instância hoje), S8 tracing OTel
    (`/metrics` cobre o básico), S9/S10 gates de CI (perf/axe).

| ID | Escopo | Status |
|---|---|---|
| S0 | **Auth gate no servidor (Modo B):** `create_app(..., security=SecurityConfig(authenticate=...))` valida credencial no handshake WS/SSE antes de montar a sessão; recusa = WS `1008` / HTTP `401`. Builders `token_authenticator` (X-Token, tempo constante, vazio=off) e `jwt_authenticator` | ✅ (v0.41.0; `tempestweb/server/security.py`, 16 testes, `docs/security.md`) |
| S1 | **CORS + allowlist de origem:** `SecurityConfig(allowed_origins=[...])` liga `CORSMiddleware` (HTTP/SSE) + checa `Origin` no upgrade do WebSocket (WS não respeita CORS) | ✅ (v0.41.0) |
| S2 | **Limites & anti-DoS:** `max_connections` (teto WS+SSE) + `max_message_bytes` (POST SSE `413`) + `max_connections_per_minute` (flood por IP, `1013`/`429`, janela deslizante). Conexão morta ceifada pelo ping do uvicorn; idle-timeout **não** imposto de propósito (desconectaria usuário legítimo ocioso) | ✅ (v0.46.0 — cap + payload + rate-limit por IP) |
| S3 | **Verificação server-side de JWT:** `verify_jwt(token, key)` (assinatura + `exp`, extra `[auth]`) + `jwt_authenticator`, ao lado do `decode_jwt` client-side | ✅ (v0.41.0) |
| S4 | **Escala horizontal (Modo B):** `/health` (readiness ligada ao cap) + WS escala sem sticky (auto-contido) + **`RedisSessionRouter`** roteia inbound do SSE por Redis pub/sub (dispensa sticky), plugável via `create_app(..., sse_backend=...)`; `tempestweb deploy --no-sticky` gera o nginx round-robin | ✅ (v0.43.0 + v0.49.0 Redis backend) |
| S5 | **Deploy profissional:** **`tempestweb deploy`** gera `nginx.conf` parametrizado (porta do config, `--server-name`, `--tls`, `--replicas`) + `Dockerfile` (+`HEALTHCHECK`) + `docker-compose.yml` + `DEPLOY.md`. Também `examples/deploy/` de referência + guia `docs/deploy.md` (PT+EN) | ✅ (v0.43.0 + v0.48.0 CLI generator) |
| S6 | **Headers de segurança + auditoria XSS:** `SecurityConfig(security_headers/hsts/content_security_policy)` adiciona `X-Content-Type-Options`/`Referrer-Policy`/`X-Frame-Options`/HSTS/CSP via middleware. **Auditoria XSS: cliente é seguro por construção** — zero `innerHTML` em todo `client/`; patcher usa `textContent`+`setAttribute` | ✅ (v0.42.0; CSP é opt-in explícita por causa dos módulos inline do shell) |
| S7 | **Supply chain & política:** `SECURITY.md` (report privado + modelo de segurança) + job `pip-audit` no CI + `.github/dependabot.yml` (pip/actions/npm semanal). Pins formais de versão ficam a critério do app | ✅ (v0.43.0 + v0.47.0) |
| S8 | **Observabilidade de servidor:** `create_app(..., metrics=True)` monta `GET /metrics` (Prometheus) com os contadores de conexão **e** o histograma de latência evento→patch; `observability=ServerObservability(...)` liga log estruturado por sessão (JSON, com o id que o trace também carrega) e tracing OpenTelemetry por adapter — default inerte, sem import da lib | ✅ |
| S9 | **Perf & carga:** gate de regressão no CI (`benchmarks/perf_gate.py` — escala do build/diff, patch mínimo, custo calibrado e throughput de sessão), throughput do Modo B (`bench_ws_throughput.py`) e cold-start do Modo A medido em browser real por job agendado (`bench_cold_start.mjs`) | ✅ |
| S10 | **Rumo a 1.0:** `docs/stability.md` (PT+EN) — contrato de superfície pública + política de depreciação, matriz de browsers (A/B/C), baseline de a11y **medido** (gate axe-core que trava o merge, sobre cenas geradas dos exemplos) e **wire-contract congelado** (`tempestweb.contract`: versão própria + digest de forma) | ✅ |
| S11 | **Modo C — contrato do subset:** `docs/stability.md` declara o subset como **contrato estável e fail-loud** (o que está dentro/fora e por quê). Port dos `components` (resolvers em JS) segue como decisão aberta | ✅ (v0.45.0 — contrato documentado; components = decisão futura) |

!!! note "Ordem sugerida"
    Bloco de segurança primeiro (**S0 → S1 → S3 → S2 → S6**) — é o que separa
    "roda" de "seguro em produção". Depois deploy/escala (**S5 → S4 → S8**), e por
    fim maturidade (**S9 → S10 → S11**). Os modos estáticos (A/C) podem ir a
    produção **antes** deste trilho; ele é pré-requisito só para o **Modo B**
    exposto publicamente.

## Trilho T — paridade de capacidades com a plataforma web

Expande o **Trilho N**: cobrir as Web APIs que o browser oferece e que a
biblioteca ainda não embrulha. Mesmo padrão por capacidade — entrada no
`contract.py` (com `mode_c`), facade Python tipada em `tempestweb/native/`,
handler em `client/native/`, entrada no Mode C facade (`client/transpile/
native.js`) quando `mode_c=True`, e testes (conformância `test_native_contract.py`
+ handler jsdom). Todas embrulháveis nos 3 modos (o handler JS roda no browser em
A/B/C); as só-Chromium expõem `is_supported()` + degradação graciosa.

!!! info "Pré-requisito de streaming (T-EV)"
    O `NativeBridge` hoje é **request/response single-shot**. Capacidades de
    **stream** (geolocation `watchPosition`, sensores contínuos, eventos de
    mudança de rede/visibilidade/orientação/bateria) exigem um **canal de eventos
    nativo** Python←cliente. **T-EV** é esse canal; as fases marcadas *(stream)*
    dependem dele. As de leitura única (poll) não dependem e vêm primeiro.

### Tier 1 — alto valor, barato, suporte universal (poll/single-shot)

| Fase | Capacidades | Status |
|---|---|---|
| T1 | **vibration:** `vibrate(pattern)` (`navigator.vibrate`) | ✅ (v0.50.0) |
| T2 | **badge:** `set(count)` / `clear()` (`navigator.setAppBadge`/`clearAppBadge`) — contador no ícone do PWA | ✅ (v0.50.0) |
| T3 | **wakelock:** `request()` → id / `release(id)` (`navigator.wakeLock`) — tela acesa | ✅ (v0.50.0) |
| T4 | **fullscreen:** `enter()` / `exit()` / `state()` (`requestFullscreen`/`exitFullscreen`/`fullscreenElement`) | ✅ (v0.50.0) |
| T5 | **visibility:** `state()` (`document.visibilityState`) — leitura única | ✅ (v0.50.0) |
| T6 | **orientation:** `lock(kind)` / `unlock()` / `state()` (`screen.orientation`) | ✅ (v0.50.0) |
| T7 | **quota:** `estimate()` / `persist()` / `persisted()` (`navigator.storage.*`) — pareia com storage/offline | ✅ (v0.50.0) |
| T8 | **network:** `state()` (`navigator.connection`: `effectiveType`/`downlink`/`rtt`/`saveData` + `onLine`) — leitura única | ✅ (v0.50.0) |
| T9 | **clipboard rico:** `read_image()` / `write_image(data)` (`ClipboardItem`, base64) — estende o grupo clipboard | ✅ (v0.50.0) |

### Tier 2 — média, muito usados

| Fase | Capacidades | Status |
|---|---|---|
| T10 | **speech:** `speak(text, opts)` / `cancel()` (TTS, `SpeechSynthesis`) — single-shot; STT (`SpeechRecognition`) é *(stream)* → T-EV | ✅ (v0.50.0 — TTS + STT `listen`) |
| T11 | **recorder:** `start`/`stop` gravação de áudio/vídeo (`MediaRecorder`) + captura de tela (`getDisplayMedia`) — devolve blob base64 | ✅ (v0.50.0) |
| T12 | **filesystem:** `open_file`/`save_file`/`open_directory` com handles vivos (`showOpenFilePicker`/`showSaveFilePicker`) + OPFS | ✅ (v0.50.0) |
| T13 | **bgsync:** registra Background Sync + Periodic Sync (`SyncManager`) — replay real da offline queue pelo SW | ✅ (v0.50.0) |
| T14 | **webauthn:** `create`/`get` credencial + passkeys (`navigator.credentials`) + **Web OTP** (`OTPCredential`) | ✅ (v0.50.0) |
| T15 | **tabs:** Broadcast Channel + Web Locks — sincronizar entre abas | ✅ (v0.50.0 — broadcast send/receive + Web Locks) |
| T16 | **idle:** Idle Detection (`IdleDetector`) — single-shot state; contínuo *(stream)* → T-EV | ✅ (v0.50.0 — `idle.watch` via T-EV) |

### Tier 3 — nicho / secure-context / maioria só Chromium

| Fase | Capacidades | Status |
|---|---|---|
| T17 | **bluetooth:** Web Bluetooth (`navigator.bluetooth`) | ✅ (v0.50.0) |
| T18 | **usb / serial / hid:** Web USB / Web Serial / Web HID | ✅ (v0.50.0) |
| T19 | **nfc:** Web NFC (`NDEFReader`) | ✅ (v0.51.0 — write + scan via T-EV) |
| T20 | **contacts:** Contact Picker (`navigator.contacts`) | ✅ (v0.50.0) |
| T21 | **payment:** Payment Request API | ✅ (v0.50.0) |
| T22 | **misc UI:** Picture-in-Picture · EyeDropper · Pointer Lock | ✅ (v0.50.0) |
| T23 | **gamepad / midi:** Gamepad API (poll) · Web MIDI (`requestMIDIAccess`) | ✅ (v0.50.0 — gamepad poll+watch, MIDI send+messages) |
| T24 | **webaudio:** Web Audio API — síntese/análise (`AudioContext`), além do play/stop atual | ✅ (v0.112.0 — `sequence` agenda a frase inteira numa chamada, cada passo com envelope, `start_ms` igual = acorde; `stop` corta sem fechar o contexto compartilhado; `levels` streama rms/peak/bands de um `AnalyserNode` sobre o barramento de síntese (`"output"`, sem microfone nem prompt) ou do microfone. **Medido em Chrome:** acorde de 700 ms → `rms 0.365→0.353`, `peak 0.852→0.719`, e `0.000` em t=720 ms quando o release acaba. Grafo de nós arbitrário fica **fora** de propósito: no Modo B poria a rede entre um oscilador e seu ganho) |

### Canal de eventos (pré-requisito das *(stream)*)

| Fase | Escopo | Status |
|---|---|---|
| T-EV | **Canal de eventos nativo:** stream Python←cliente para subscrições contínuas (geolocation watch, sensores, mudanças de rede/visibilidade/orientação/bateria, STT, idle contínuo). Estende o `NativeBridge` com `subscribe`/`unsubscribe` + entrega de eventos (Modo A via callback FFI, Modo B via frame WS/SSE). Desbloqueia os *(stream)* dos Tiers 1–2 | ✅ (v0.50.0) |

!!! note "Ordem sugerida"
    Tier 1 primeiro (barato, universal, fecha a paridade PWA), depois T-EV (destrava
    os streams), depois Tier 2 e Tier 3 por demanda. As só-Chromium (Tier 3) sempre
    entram com `is_supported()` + fallback.

## Trilho R — adoção do `tempest-react-sdk`

O `tempest-react-sdk` resolveu, em React, problemas que este framework também
tem. O que vale trazer é a **lógica**, nunca o hook: aqui o estado é Python, e um
`useX` não tem para onde ir. Cada fase abaixo nomeia o módulo de origem e o que
ficou deliberadamente de fora.

| Fase | Escopo | Status |
|---|---|---|
| R1 | **export:** `Column` + `to_csv`/`to_xlsx` em Python puro, para o `native.file.save` entregar. Cobre os quatro erros clássicos de encoder à mão — separador dentro do campo, aspas no texto, BOM ausente (Excel lê `João` como `JoÃ£o`) e data de XLSX escrita como número cru. Zero dependência: XLSX é `zipfile` + `xml.etree`, e o teste **abre a planilha de volta** para provar que a célula de data é data, não número parecido. **Modos A e B** — o Modo C serve um conjunto fechado de módulos e recusa o import no build. Origem: `src/utils/{csv,xlsx}.ts` | ✅ (v0.114.0 — #176) |
| R2 | **access:** `AccessControl.can()` + leitura de claims do token, para a `view` decidir o que desenhar. Curinga de um nível (`users:*` cobre `users:delete`, não cobre `audit:read` nem `users`), papel desconhecido concede nada, `NO_ACCESS` para deslogado. `unverified_access_from_token` **não** verifica assinatura — o `unverified_` está no nome para aparecer em toda chamada, e um token forjado decodificar está fixado por teste. Construído sobre o `decode_jwt` que já existia em `observability/auth.py`. **Modos A e B** — o Modo C recusa o import no build. Origem: `src/access/` | ✅ (v0.115.0 — #177) |
| R3 | **query:** cache com chave hierárquica (tupla, então prefixo é comparação e não convenção), invalidação por prefixo que **mantém o valor na tela**, single-flight, paginação offset/cursor tipada e mutação otimista com **rollback exato** — `patch` devolve o undo e `optimistic(...)` é o bloco que não deixa esquecer dele. Persistência sobre o `native.storage` que já existe, por Protocol, sem duplicar `client/offline/store.js`. Não substitui o delta-sync do `native.sync`. **Modos A e B**. Origem: `src/query/` | ✅ (v0.116.0 — #175) |
| R4 | **storage (codec):** compressão opcional, **medida antes de decidir** — e a medição mudou a resposta: o IndexedDB **já comprime** o que guarda, então o codec não compete com texto cru e economiza 45–65% do que **sobra**, custando +12 ms/leitura e +76 ms/escrita por MB num aparelho fraco (tabela medida em `docs/advanced/storage-codec.md`). Default `json`, opt-in por `native.storage.configure(codec=...)` — não na fila de mutações, que a própria issue punha fora de escopo. Decodificar está sempre ligado, então ligar/desligar não apaga cache de ninguém. Origem: `src/utils/compressed-storage.ts` | ✅ (v0.117.0 — #180) |
| R5 | **device.profile:** memória, núcleos e heap da máquina do usuário, para qualidade adaptativa. Conexão e cota **não** entram: já são `native.network.state` e `native.quota.estimate`, e repetir daria dois nomes ao mesmo fato no contrato. Todo campo é opcional (as APIs são só-Chromium) e o teste fixa o caminho em que tudo volta `None` — app que lê `None` como "fraco" degrada todo iPhone. Medido em Chrome 150; a medição corrigiu a doc sobre o cap do `deviceMemory`. Fingerprinting fora por escrito. Origem: `src/perf/` | ✅ (v0.118.0 — #179) |
| R6 | **imaging:** comprimir, miniaturar e transformar antes do upload, endereçando o blob por **handle** em vez de reenviar os bytes — no Modo B, mandar bytes faria uma foto de 4 MB atravessar a rede duas vezes só para encolher. Busca binária de qualidade contra orçamento, **limitada**, reportando qualidade, encodes e `within_budget`; orçamento impossível responde em vez de travar. Opção de desenvolvedor é `extra="forbid"`, payload de browser ignora extras. Implementa junto o `blob_id` que o `http.upload` documentava e não resolvia. Medido em Chrome real. Origem: `src/imaging/` | ✅ (v0.119.0 — #174) |
| R7 | **tabular:** inferência sklearn→ONNX no browser, irmã do `vision/`. O **manifesto** (quais features, em que ordem) é o que impede a predição silenciosamente errada — sem ele, `{"idade": 30}` num modelo treinado com `age` lê zero e responde um número plausível e errado. Erros nomeados com as duas metades do typo. Sem numpy (tensor por `struct`); treinar/exportar é passo de build em venv descartável. Medido em Chrome real: **idêntico ao sklearn até 6e-08**. Achou dois defeitos no caminho: `onnx.load` não usava o cache de assets, e export com ZipMap falhava com mensagem que não dizia o porquê. **v1 estreita** — `CompactPredictor` e ordem de provider ficaram para o follow-up #191, que mediu (2026-08-27): o `.onnx` de uma `LogisticRegression` de 30 features tem **660 B**, e o `onnxruntime-web` que o executa tem **13,96 MB** (3,58 MB gzip) — **+43% no gzip** de um artefato Modo A offline, **12×** o artefato Modo C inteiro. Inferência de 3 linhas: **0,1 ms**. Ou seja: **o default `["wasm"]` fica** (a EP WebGPU exige o runtime jsep, 2,9 MB gzip a mais, para acelerar 0,1 ms) e **`CompactPredictor` pagou** — entregue na v0.122.0, lendo `.tmc`/`TMC1` em Python de stdlib, medido em Chrome real: `setosa` p=1,00000000 e `0` p=0,99111871 contra o sklearn, 6,3 ms do frio à primeira predição, p95 de 0,2 ms por linha. Achou de quebra que **sete subpacotes que uma app importa pelo nome não iam no artefato Modo A** (`tabular`, `vision`, `query`, `access`, `export`, `presets`, `observability`) — e que presença no zip não é importabilidade: `vision` importa `numpy`/`ort_vision_sdk` no nível do módulo, então roda só com `[wasm] packages` declarado, e o `pwa` é emissor de build, que não entra. Origem: `src/tabular/` | ✅ (v0.120.0 — #178 · v0.122.0 — #191) |

!!! note "O que nunca vem junto"
    Provider, contexto e hook (`useCan`, `usePaginatedQuery`, `useImagePreview`,
    `useTabularPredictor`) ficam de fora por construção: o estado vive no `State`
    da app, e a `view` lê dele. Trazer o ciclo de vida de componente React seria
    importar a solução de um problema que este framework não tem.

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
