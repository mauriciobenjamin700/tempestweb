# tempestweb 🌩️

<p align="center"><em>Construa web apps em <strong>Python tipado</strong>. Uma árvore
declarativa de widgets, um renderizador <strong>DOM</strong>, e <strong>três modos de
execução</strong> que compartilham 100% do código de aplicação.</em></p>

---

**tempestweb** é um framework para construir web apps escrevendo **Python
tipado**. Você descreve a UI como uma **árvore declarativa de widgets** numa
função `view()`, e o framework a renderiza no **DOM**. A mesma `view()`, sem
alterar uma linha, roda em **três modos de execução**:

<div class="grid cards" markdown>

-   :material-language-python: __Modo A — WASM__

    ---

    Seu Python roda **no browser** via Pyodide. Análogo a PyScript. Offline pleno
    depois do load.

    **Quando usar:** offline pleno, zero infra de servidor, prototipagem rápida.

-   :material-server: __Modo B — Servidor__

    ---

    Seu Python roda **no servidor** (FastAPI) e fala com um cliente JS fino por
    WebSocket ou SSE. Análogo a Phoenix LiveView.

    **Quando usar:** lógica sensível no servidor, estado central, dados ao vivo.

-   :material-language-javascript: __Modo C — transpile__

    ---

    A camada de app é **transcrita para JavaScript nativo** no build. Zero Python
    no browser — um bundle estático servível por qualquer CDN.

    **Quando usar:** PWA instalável, SEO e first-paint ótimos, custo de servidor
    zero.

</div>

O segredo: o app **nunca nomeia um transporte**. O mesmo
`examples/counter/app.py` roda sob `--mode wasm`, `--mode server` e
`--mode transpile` sem mudar uma linha. 🚀

!!! question "Qual modo escolher?"
    - Precisa de **SEO, first-paint rápido e um bundle estático sem servidor**? →
      **Modo C (transpile)** — a escolha padrão para sites/PWAs públicos.
    - Precisa manter **lógica ou estado no servidor** (dados ao vivo, segredos)? →
      **Modo B (servidor)**.
    - Quer **Python vivo no browser** para prototipar ou rodar libs Python
      client-side? → **Modo A (WASM)**.

    Você não decide isso no código — só na hora do `build --mode`. Comece pelo
    [Tutorial](tutorial/index.md), que roda o counter nos três modos.

## Como funciona

```text
   view(app) ──build──▶ árvore de Node (IR)        ← core compartilhado
                            │
                          diff
                            ▼
                        [ Patch ]              insert / remove / update / reorder / replace
                    ╱        │        ╲
          Modo A          Modo B          Modo C
       (pyodide.ffi)   (WebSocket/SSE)  (app → JS nativo, diff em JS)
                    ╲        │        ╱
                  client/ (JS puro): aplica patches no DOM
                  + Style→CSS + captura de eventos   ← MESMO código nos três modos
```

A função `view()` produz uma **árvore de widgets** (IR). O reconciliador faz
`diff` entre a árvore antiga e a nova e emite **patches** — dados puros
serializados. Nos Modos A e B o `diff` roda em Python e os patches viajam por um
transporte; no **Modo C** a camada de app é transcrita para JS, então o `diff`
roda nativo no browser. Em todos, o cliente JS só sabe consumir patch e mutar o
DOM — não liga de onde o patch veio. Por isso o renderizador é **um só** nos três
modos.

!!! tip "Por onde começar"
    Vá direto para a [Instalação](installation.md) e depois siga o
    [Tutorial — o Counter](tutorial/index.md). Em quatro páginas curtas você
    constrói o app canônico e entende o contrato de fronteira de ponta a ponta.

## O que você vai encontrar aqui

- **[Instalação](installation.md)** — prepare o ambiente em um minuto.
- **[Arquitetura](architecture.md)** — as quatro camadas e por que o renderizador
  é compartilhado.
- **[Tutorial](tutorial/index.md)** — construa o counter, um conceito por página,
  e rode-o nos três modos.
- **[Modo C — transpile](transpile.md)** — Python → JavaScript nativo: bundle
  estático, SEO e PWA turnkey.
- **[PWA e offline](pwa.md)** — app instalável, service worker, IndexedDB, WebPush.
- **[Capacidades](capabilities.md)** — Web APIs tipadas (geolocation, clipboard,
  camera) como awaitables Python.
- **[Contrato de fronteira](wire-contract.md)** — o wire format Python↔cliente.
- **[Observabilidade](observability.md)** — telemetry, logger, feature flags, auth.
- **[Roadmap e docs de design](design-docs.md)** — o que vem por aí e os planos
  vivos do projeto.

!!! info "Idioma"
    Esta documentação é **bilíngue**. Use o seletor de idioma no topo da página
    para alternar entre **Português (Brasil)** e **English (US)**.

## Relação com o tempestroid

O tempestweb é o **irmão web** do
[tempestroid](https://github.com/mauriciobenjamin700), o framework mobile da mesma
família. Os dois seguem a filosofia **"uma árvore, múltiplos renderizadores"** e
compartilham o mesmo núcleo renderer-agnostic — o pacote
[`tempest-core`](https://pypi.org/project/tempest-core/) (IR, `diff`/patch,
estado, estilo, widgets **e o catálogo de componentes Material 3**, que o
tempestweb **reexporta** em `tempestweb.components` — veja
[Componentes prontos](components.md)). O tempestroid renderiza para telas nativas;
o tempestweb renderiza para o DOM. Se você já conhece um, o modelo mental transfere direto —
mas **não é preciso conhecer o tempestroid** para usar o tempestweb.

## Convenções do projeto

Python: aspas duplas, tipagem completa (`mypy --strict`), docstrings Google em
inglês, async-first. Cliente: **JavaScript puro** — sem TypeScript, sem
framework, sem passo de build.

!!! note "Estado do projeto"
    Os três modos estão **funcionais hoje** — o counter e os 50 exemplos rodam e
    passam no gate completo. Os planos de design vivos continuam
    versionados no repositório: [plan.md](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/plan.md),
    [roadmap.md](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/roadmap.md)
    e [contract.md](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/contract.md).
    Esta documentação reflete a superfície já construída e linka os planos para o
    detalhe completo.
