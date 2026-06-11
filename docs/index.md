# tempestweb 🌩️

<p align="center"><em>Construa web apps em <strong>Python tipado</strong>. Uma árvore
declarativa de widgets, um renderizador <strong>DOM</strong>, e <strong>dois modos de
execução</strong> que compartilham 100% do código de aplicação.</em></p>

---

**tempestweb** é o irmão web do
[tempestroid](https://github.com/mauriciobenjamin700) — a mesma ideia de **uma
árvore, múltiplos renderizadores**. Você escreve uma função `view()` em Python e
ela roda, sem alteração, em dois modos:

<div class="grid cards" markdown>

-   :material-language-python: __Modo A — WASM__

    ---

    Seu Python roda **no browser** via Pyodide. Análogo a PyScript. Offline pleno
    depois do load.

-   :material-server: __Modo B — Servidor__

    ---

    Seu Python roda **no servidor** (FastAPI) e fala com um cliente JS fino por
    WebSocket ou SSE. Análogo a Phoenix LiveView.

</div>

O segredo: o app **nunca nomeia um transporte**. O mesmo
`examples/counter/app.py` roda sob `--mode wasm` e `--mode server` sem mudar uma
linha. 🚀

## Como funciona

```text
   view(app) ──build──▶ árvore de Node (IR)        ← core compartilhado
                            │
                          diff
                            ▼
                        [ Patch ]              insert / remove / update / reorder / replace
                       ╱          ╲
              Transporte Modo A   Transporte Modo B
              (pyodide.ffi)       (WebSocket / SSE)
                       ╲          ╱
                  client/ (JS puro): aplica patches no DOM
                  + Style→CSS + captura de eventos   ← MESMO código nos dois modos
```

A função `view()` produz uma **árvore de widgets** (IR). O reconciliador faz
`diff` entre a árvore antiga e a nova e emite **patches** — dados puros
serializados. O cliente JS só sabe consumir patch e mutar o DOM; não liga de
onde o patch veio. Por isso o renderizador é **um só** nos dois modos.

!!! tip "Por onde começar"
    Vá direto para a [Instalação](installation.md) e depois siga o
    [Tutorial — o Counter](tutorial/index.md). Em quatro páginas curtas você
    constrói o app canônico e entende o contrato de fronteira de ponta a ponta.

## O que você vai encontrar aqui

- **[Instalação](installation.md)** — prepare o ambiente em um minuto.
- **[Arquitetura](architecture.md)** — as quatro camadas e por que o renderizador
  é compartilhado.
- **[Tutorial](tutorial/index.md)** — construa o counter, um conceito por página.
- **[Contrato de fronteira](wire-contract.md)** — o wire format Python↔cliente.
- **[Capacidades](capabilities.md)** — Web APIs tipadas (geolocation, clipboard,
  camera) como awaitables Python.
- **[PWA e offline](pwa.md)** — app instalável, service worker, IndexedDB, WebPush.
- **[Observabilidade](observability.md)** — telemetry, logger, feature flags, auth.
- **[Roadmap e docs de design](design-docs.md)** — o que vem por aí e os planos
  vivos do projeto.

!!! info "Idioma"
    Esta documentação é **bilíngue**. Use o seletor de idioma no topo da página
    para alternar entre **Português (Brasil)** e **English (US)**.

## Convenções do projeto

Python: aspas duplas, tipagem completa (`mypy --strict`), docstrings Google em
inglês, async-first. Cliente: **JavaScript puro** — sem TypeScript, sem
framework, sem passo de build.

!!! note "Estado do projeto"
    🚧 tempestweb está em **construção inicial**. Os planos de design vivos estão
    versionados no repositório: [plan.md](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/plan.md),
    [roadmap.md](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/roadmap.md)
    e [contract.md](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/contract.md).
    Esta documentação reflete a superfície já construída e linka os planos para o
    detalhe completo.
