# Roadmap e fases

O desenvolvimento segue um pré-requisito, dois trilhos compartilhados e dois
trilhos de execução. **Trilho 0** extrai o `tempest-core` do tempestroid.
**Trilho W** é o renderizador-folha web (cliente JS puro), compartilhado pelos
dois modos. **Trilho A** é o **Modo WASM** (Pyodide, Python no browser) —
construído primeiro. **Trilho B** é o **Modo servidor** (FastAPI + WebSocket/SSE)
— depois. **Trilho P** é a camada **PWA / Offline-first / WebPush**, compartilhada
pelos dois modos (instalável, app-shell em cache, notificações push). O plano
completo está em [Plano de design](plan.md).

> Paridade com o `tempest-react-sdk`: app **instalável** (PWA), **offline-first**
> (service worker + app-shell em cache), push no servidor por **SSE** e
> **WebPush** são metas de primeira classe, não polimento. O Modo A é o alvo
> natural de PWA (Python no browser, offline após o load); o Modo B ganha install
> shell + push do servidor.

## Trilho 0 — `tempest-core` (pré-requisito)

| Fase | Escopo | Status |
|---|---|---|
| 0.0 | Extrair IR/reconciliador/estado/estilo/widgets/validators para o pacote `tempest-core`; tempestroid passa a depender dele | ⬜ |
| 0.1 | Extrair extras de paridade (navigation, theme, i18n, animation, forms, lists) sob demanda da web | ⬜ |

!!! warning "Guarda do Trilho 0"
    A extração só fecha com a suite completa do tempestroid — **incluindo a
    conformância Qt↔Compose** — verde após a troca do core interno pelo pacote.

## Trilho W — cliente JS (renderizador-folha web)

JavaScript **puro**: sem TypeScript, sem framework, sem etapa de build. Compartilhado
pelos Modos A e B.

| Fase | Escopo | Status |
|---|---|---|
| W0 | Fundação do repo: pacote, ferramental, `tempestweb --help`, dep em `tempest-core` | ⬜ |
| W1 | Aplicador de patches no DOM (insert/remove/update/reorder/replace), testado com jsdom | ⬜ |
| W2 | Tradutor `Style → CSS` (flexbox + box model + tipografia) | ⬜ |
| W3 | Captura de eventos + interface de transporte (`sendEvent`/`onPatches`) | ⬜ |

## Trilho A — Modo WASM (Pyodide) — primeiro

| Fase | Escopo | Status |
|---|---|---|
| A0 | **De-risk crítico:** `tempest-core` + `pydantic` rodando no Pyodide; reconciliador produz patches no browser | ⬜ |
| A1 | Transporte WASM (FFI Pyodide): patches Python→DOM, eventos DOM→Python; `counter` 100% no browser | ⬜ |
| A2 | Loop async no browser: handler `async` com `await` atualiza a UI sem travar a aba | ⬜ |
| A3 | `tempestweb build --mode wasm`: saída estática (Pyodide + wheel do core + `app.py`) | ⬜ |
| A4 | `tempestweb dev` (modo A): watcher + reload da aba (hot restart) | ⬜ |
| A5 | `native/` web (modo A): geolocation, clipboard, notifications, storage como awaitables | ⬜ |

## Trilho B — Modo servidor (FastAPI + WS/SSE) — depois

| Fase | Escopo | Status |
|---|---|---|
| B0 | Host FastAPI + tempest-fastapi-sdk com endpoint WS; patches iniciais ao conectar | ⬜ |
| B1 | Transporte WebSocket (Python + JS); `counter` por WS — **mesmo `app.py` do Modo A** | ⬜ |
| B2 | Sessão e ciclo de vida por conexão (connect=mount, disconnect=unmount, cancelamento de tasks) | ⬜ |
| B3 | `native/` split cliente/servidor (camera/geo no cliente, proxiados por WS) | ⬜ |
| B4 | `tempestweb dev` (modo B): reload do servidor + push aos clientes | ⬜ |
| B5 | **Transporte SSE:** patches servidor→cliente via `EventSource`; eventos cliente→servidor via HTTP POST. `transports/sse.py` + `transport-sse.js`, mesma interface do W3. Alternativa ao WS para infra que bloqueia WebSocket | ⬜ |

## Trilho P — PWA / Offline-first / WebPush (compartilhado)

Camada instalável e offline, compartilhada pelos dois modos. Depende do cliente
(W3) e do empacotamento (A3 para o app-shell WASM). O service worker (P1) é
pré-requisito do WebPush (P3). Paridade com o `tempest-react-sdk`.

| Fase | Escopo | Status |
|---|---|---|
| P0 | **Manifest + ícones:** `tempestweb build` emite `manifest.webmanifest` (`display: standalone`, `theme_color`, `start_url`, ícones maskable). App instalável ("Add to Home"). Lighthouse "installable" verde | ⬜ |
| P1 | **Service worker + app-shell (base offline-first):** SW registrado faz precache do shell — cliente JS sempre; no Modo A também Pyodide + wheel do core + `app.py`. Cache-first no shell; app abre **offline após o 1º load**. Resolve também o cold-start do bundle WASM | ⬜ |
| P2 | **Offline-first em runtime:** estratégias por recurso (stale-while-revalidate p/ assets, network-first p/ dados); fila de eventos offline + replay no reconnect (Modo B); banner online/offline ligado ao hook de conectividade do core | ⬜ |
| P3 | **WebPush Notifications:** VAPID via `tempest-fastapi-sdk[webpush]`; `native/` expõe `notifications.subscribe()` + permissão como awaitables; SW recebe `push` e mostra a notificação; envio server-side (pywebpush). Funciona com a aba fechada | ⬜ |

!!! note "PWA por modo"
    **Modo A** é o alvo pleno: instalável + offline real (Python roda no browser,
    sem servidor após o load). **Modo B** ganha install shell + WebPush; o offline
    é parcial (precisa do servidor para reconciliar), então P2 cobre fila/replay de
    eventos no reconnect. P0/P1/P3 são compartilhados; P2 tem ramo por modo.

## Pós-convergência

| Fase | Escopo | Status |
|---|---|---|
| C | Polimento: `new`/`build --mode`/`run` + hot reload com estado (B primeiro) | ⬜ |
| D | Conformância A-vs-B: mesma `view()` → DOM idêntico nos dois modos, no CI | ⬜ |
| E | Paridade (reusa extras do `tempest-core`): rotas/URL, listas, overlays, animação CSS, gestos, formulários, mídia, tema/i18n/a11y | ⬜ |

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
`native/` tem dois backends por capacidade. A camada PWA/offline/WebPush (Trilho
P) é compartilhada: o mesmo manifest + service worker servem os dois modos, com o
ramo offline (P2) divergindo só no que cada modo consegue fazer sem servidor.
