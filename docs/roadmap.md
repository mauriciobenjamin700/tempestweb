# Roadmap e fases

O desenvolvimento segue um pré-requisito, um trilho compartilhado e dois trilhos
de execução. **Trilho 0** extrai o `tempest-core` do tempestroid. **Trilho W** é o
renderizador-folha web (cliente JS puro), compartilhado pelos dois modos.
**Trilho A** é o **Modo WASM** (Pyodide, Python no browser) — construído primeiro.
**Trilho B** é o **Modo servidor** (FastAPI + WebSocket) — depois. O plano completo
está em [Plano de design](plan.md).

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

## Trilho B — Modo servidor (FastAPI + WS) — depois

| Fase | Escopo | Status |
|---|---|---|
| B0 | Host FastAPI + tempest-fastapi-sdk com endpoint WS; patches iniciais ao conectar | ⬜ |
| B1 | Transporte WebSocket (Python + JS); `counter` por WS — **mesmo `app.py` do Modo A** | ⬜ |
| B2 | Sessão e ciclo de vida por conexão (connect=mount, disconnect=unmount, cancelamento de tasks) | ⬜ |
| B3 | `native/` split cliente/servidor (camera/geo no cliente, proxiados por WS) | ⬜ |
| B4 | `tempestweb dev` (modo B): reload do servidor + push aos clientes | ⬜ |

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
dois; só a implementação de transporte difere (`transport-wasm.js` vs
`transport-ws.js`). `native/` tem dois backends por capacidade.
