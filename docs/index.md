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

!!! tip "Não é desenvolvedor front-end? Comece pelas telas prontas"
    Se o que você precisa é um **painel administrativo**, um **dashboard**, uma
    tela de **CRUD** com busca e paginação, um **formulário** de configurações ou
    uma tela de **login**, você não precisa aprender layout, CSS ou breakpoint
    nenhum.

    As [telas prontas (presets)](tutorial/presets.md) recebem **dados tipados** —
    quais itens o menu tem, quais números o dashboard mostra, quais colunas a
    tabela tem — e decidem a aparência por você. O resultado já é responsivo:
    a sidebar vira drawer no celular, os cartões reorganizam, a tabela rola.

    ```python
    admin_shell(
        title="Console ACME",
        nav=[NavItem("Visão geral", "overview"), NavItem("Usuários", "users")],
        active=app.state.tab,
        on_navigate=ir_para,
        body=dashboard_page(
            title="Visão geral",
            kpis=[Kpi("Receita", "R$ 82.400", delta="+12%", tone="success")],
        ),
    )
    ```

    Um painel inteiro sai em ~260 linhas de Python, sem um `Style` escrito à mão —
    veja o [Console Administrativo](examples/admin-console.md) completo.

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
    Vá direto para a [Instalação](tutorial/installation.md) e depois siga o
    [Tutorial — o Counter](tutorial/index.md). Em quatro páginas curtas você
    constrói o app canônico e entende o contrato de fronteira de ponta a ponta.

## O que você vai encontrar aqui

<div class="grid cards" markdown>

-   :material-rocket-launch: __Comece aqui__

    ---

    [**Instalação**](tutorial/installation.md) — o ambiente em um minuto ·
    [**Tutorial — o Counter**](tutorial/index.md) — quatro páginas curtas, um
    conceito cada, e o app rodando nos três modos ·
    [**Usando a CLI**](tutorial/cli.md) — `new`, `build`, `dev`, `deploy` ·
    [**Arquitetura**](architecture.md) — as quatro camadas e por que o
    renderizador é um só

-   :material-palette: __Construindo a interface__

    ---

    [**Componentes prontos**](tutorial/components.md) — campos, formulários,
    botões Material 3 (e os campos brasileiros) ·
    [**Telas prontas (presets)**](tutorial/presets.md) — painel, dashboard,
    listagem, formulário e login a partir de dados ·
    [**Tema**](tutorial/theming.md) · [**Ícones**](tutorial/icons.md) ·
    [**Rotas e navegação**](tutorial/routing.md) ·
    [**Boas práticas**](tutorial/best-practices.md) — como organizar o app e o
    que nunca pôr dentro de um handler

-   :material-server-network: __Indo a produção__

    ---

    [**Segurança (Modo B)**](advanced/security.md) — auth, origem, limites ·
    [**Deploy**](advanced/deploy.md) — CDN, nginx, escala, métricas ·
    [**Observabilidade**](advanced/observability.md) — telemetria, logs, feature
    flags ·
    [**PWA e offline**](advanced/pwa.md) — instalável, service worker, WebPush ·
    [**Offline + backend**](advanced/offline-sync.md) — fila e sincronização ·
    [**Modo C — transpile**](advanced/transpile.md) — bundle estático, SEO ·
    [**SSR estático**](advanced/ssr.md)

-   :material-database: __Dado e modelo__

    ---

    [**Lendo dados remotos**](tutorial/query.md) — cache com chave, invalidação
    por prefixo e mudança otimista que desfaz sem ir à rede ·
    [**Exportar CSV e XLSX**](advanced/export.md) — os bytes que o `file.save`
    entrega, sem dependência ·
    [**Permissões na view**](advanced/access.md) — `can()` para decidir o que
    desenhar (e por que isso **não** é autorização) ·
    [**Visão computacional**](advanced/vision.md) — classificar, detectar,
    segmentar ·
    [**Inferência tabular**](advanced/tabular.md) — sklearn no browser, com o
    manifesto que impede a predição silenciosamente errada ·
    [**Comprimir o store**](advanced/storage-codec.md) — medido antes de ligar

-   :material-book-open-variant: __Consultar__

    ---

    [**Referência de API**](reference/presets.md) — assinatura de tudo, em todos
    os subpacotes ·
    [**Capacidades nativas**](advanced/capabilities.md) e sua
    [**referência**](advanced/native-reference.md) ·
    [**Canal de eventos**](advanced/native-events.md) ·
    [**Cliente a partir de OpenAPI**](advanced/openapi.md) ·
    [**Contrato de fronteira**](advanced/wire-contract.md) —
    [`transports`](reference/transports.md) e [`html`](reference/html.md) ·
    [**Servidor (Modo B)**](reference/server.md) ·
    [**Galeria de exemplos**](examples/index.md) — apps rodáveis, um por receita ·
    [**Quando dá errado**](troubleshooting.md) — diagnóstico por sintoma ·
    [**FAQ**](faq.md) ·
    [**Estabilidade**](stability.md) ·
    [**Roadmap**](design-docs.md)

</div>

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
[Componentes prontos](tutorial/components.md)). O tempestroid renderiza para telas nativas;
o tempestweb renderiza para o DOM. Se você já conhece um, o modelo mental transfere direto —
mas **não é preciso conhecer o tempestroid** para usar o tempestweb.

## Próximo passo

1. **[Instale](tutorial/installation.md)** — um comando.
2. **[Faça o counter](tutorial/index.md)** — quatro páginas, e você entende o
   ciclo inteiro.
3. Depois disso, siga por onde o seu problema estiver: monte a tela com
   [presets](tutorial/presets.md), ou vá direto para
   [segurança e deploy](advanced/deploy.md) se o app já existe.

## Convenções do projeto

Python: aspas duplas, tipagem completa (`mypy --strict`), docstrings Google em
inglês, async-first. Cliente: **JavaScript puro** — sem TypeScript, sem
framework, sem passo de build.

!!! note "Estado do projeto"
    Os três modos estão **funcionais hoje** — o counter e todos os exemplos da
    galeria rodam e passam no gate completo. Os planos de design vivos continuam
    versionados no repositório: [plan.md](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/plan.md),
    [roadmap.md](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/roadmap.md)
    e [contract.md](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/contract.md).
    Esta documentação reflete a superfície já construída e linka os planos para o
    detalhe completo.
