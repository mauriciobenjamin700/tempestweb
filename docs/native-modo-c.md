# Native capabilities no Modo C (design)

> Como as capacidades nativas tipadas em Python (`native.http`, `native.storage`,
> `native.clipboard`, `native.cookies`, …) atravessam para o **Modo C**
> (transpile → JS nativo, sem runtime Python), reusando a mesma glue de browser
> dos Modos A/B.

## O que já existe (Modos A/B)

`tempestweb/native/*.py` expõe cada capacidade como **awaitable Python tipado**
(`await native.http.request(...)`, `await native.storage.get(...)`). O seam é a
`NativeBridge` (`dispatch.py`):

- **Modo A (WASM):** `FFIBridge` — chama `client/native/*.js` em processo (FFI).
- **Modo B (servidor):** `ProxyBridge` — serializa `native_call` → WS → o cliente
  roda a Web API → `native_result` volta.

O cliente (`client/native/index.js`) tem um registro `HANDLERS`
(`"http.request"`, `"storage.get"`, `"geolocation.get"`, …) e um
`dispatch(envelope) → {ok, value|error}` que nunca lança. **É essa a glue que o
Modo C reusa.**

## O modelo do Modo C

No Modo C não há Python nem bridge: o app é JS nativo. Uma chamada native vira
uma chamada JS **em processo** ao mesmo `dispatch`:

```text
Python (autoria):   await native.http.request("GET", "/api/items")
        │ transpile
        ▼
JS gerado:          await native.http.request("GET", "/api/items")
        │  client/transpile/native.js
        ▼
dispatch({ capability: "http.request", args: {...} })  →  client/native/http.js
```

Três peças:

1. **`async`/`await` no subset do transpiler.** `async def` → `async` arrow;
   `await expr` → `await expr`. Handlers assíncronos: o runtime já re-renderiza
   quando o `set_state` roda (após o `await`), então nenhuma mudança de runtime é
   necessária além de o `sendEvent` tolerar um handler que retorna promise.
2. **Mapeamento `native.<cap>.<método>(…)`.** O transpiler reconhece o namespace
   `native` (importado de `tempestweb`/`tempest_core`) e emite chamadas à fachada
   JS. Ex.: `native.http.request(m, u)` → `native.http.request(m, u)` importado de
   `client/transpile/native.js`.
3. **Fachada JS `client/transpile/native.js`.** Espelha as assinaturas Python,
   montando o `args` de cada capacidade e chamando `dispatch`, desembrulhando
   `.value` (ou lançando em `.ok === false`). Reusa `client/native/*.js` via os
   `HANDLERS` — zero reimplementação da Web API.

## Onde mora o quê (não vai pro tempest-core)

`tempest-core` é **lógica pura renderer-agnostic** (IR/reconciler/estado/estilo) —
sem I/O, sem browser. Native é **glue de plataforma**, então **fica no
tempestweb** (como hoje). O que PODE ser compartilhado é o **contrato tipado** (as
assinaturas/DTOs das capacidades), para tempestroid (mobile) e tempestweb (web)
concordarem — mas a implementação é sempre por plataforma. Recomendação: manter
`tempestweb.native` como fonte, e o Modo C adaptar via a fachada JS.

## Capacidades

| Capacidade | A/B (Python + client JS) | Modo C (fachada JS) | Status |
|---|---|---|---|
| **http / requests** | ✅ `http.request/upload/poll` | reusa `dispatch` | a fiar |
| **storage / IndexedDB** | ✅ `storage.put/get/list/remove` | reusa `dispatch` | a fiar |
| **clipboard** | ✅ | reusa | a fiar |
| **geolocation** | ✅ | reusa | a fiar |
| **cookies** | ❌ (novo) | novo handler | a criar |

**cookies** (novo, todos os modos): `native.cookies.get/set/remove/all` sobre
`document.cookie` no browser (client JS handler) + a mesma API awaitable Python.

## Plano faseado

- **N-C0 — fundação. ✅** `async`/`await` no transpiler (`async def` → arrow
  `async`; `await` → `await`) + runtime tolerando handler async (re-render no
  `set_state` pós-await; rejeição capturada). Dict literal e call com args mistos
  (posicional + kwargs → objeto final) também entraram no subset.
- **N-C1 — fachada + http. ✅** `client/transpile/native.js` (objeto `native`
  congelado) + o transpiler mapeia `from tempestweb import native` →
  `import { native } from "./native.js"`. Verificado no Playwright: fetch via
  `await native.http.request(...)`.
- **N-C2 — storage/clipboard/geo. ✅** Fachada estendida às capacidades já com
  handler JS, desembrulhando os campos de resultado (`.content`/`.keys`/`.text`)
  como o lado Python. **storage é IndexedDB de verdade:** a fachada injeta um KV
  IndexedDB (`client/native/idb-kv.js`) como `deps.store`, com fallback a
  localStorage quando o IDB não existe. Verificado no Playwright: o valor persiste
  no object store `tempestweb/kv` (não no localStorage) e o round-trip funciona.
- **N-C3 — cookies. ✅** Capacidade nova ponta-a-ponta: `tempestweb/native/
  cookies.py` (awaitable Python) + `client/native/cookies.js` (handler
  `document.cookie`, registrado no `HANDLERS`) + fachada Modo C. Verificado nos
  três modos (Playwright no Modo C).
- **N-C4 — contrato de capacidades. ✅** `tempestweb/native/contract.py` é a
  **fonte única**: `CAPABILITIES` (nome dotted + grupo + flag `mode_c`) e
  `MODE_C_CAPABILITIES`. Testes de conformidade parseiam as superfícies JS e
  exigem concordância — `client/native/index.js` `HANDLERS` == contrato; a fachada
  `client/transpile/native.js` == subset `mode_c`; cada grupo tem submódulo Python.
  Adicionar uma capacidade em uma superfície só quebra o CI. É o candidato à
  extração para um módulo compartilhado que o `tempestroid` (mobile) espelharia.

## Bundle do Modo C

O artefato transpile embarca a árvore `client/native/*` + `client/push/` +
`client/pwa/` (o mesmo conjunto do Modo A), então `dispatch` resolve toda a glue
de browser em processo. `client/transpile/native.js` é a fachada; o app importa
via `from tempestweb import native`. Sem Python, sem bridge, sem rede.

## Verificação

Cada fase fecha verde: `ruff`/`mypy`/`pytest`, `node --test` (jsdom, incl. um
`dispatch` fake), e Playwright para as que tocam Web API real (http/storage).
Fixtures de contrato (`native_call`/`native_result`) permanecem a fonte da verdade
do wire, idênticas entre os modos.
