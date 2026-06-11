# tempestweb — Plano do projeto

> Framework pessoal para construir apps **web** escrevendo **Python tipado**,
> com **dois modos de execução** que compartilham 100% do código de aplicação:
> **Modo A (WASM)** — Python roda no browser via Pyodide; **Modo B (servidor)** —
> Python roda no servidor (FastAPI) e fala com um cliente fino por WebSocket.
> Irmão web do [tempestroid](../../tempestroid): mesma arquitetura "uma árvore,
> múltiplos renderizadores".

---

## 1. Visão

Poder construir apps web usando conhecimento e bibliotecas pythônicas (Pydantic,
HTTPX e cia.), com:

- **DOM nativo do browser** (sem framework JS, sem React) — o renderizador-folha
  é JavaScript puro.
- **Estilização "web-like"** declarada por objetos Pydantic tipados (o mesmo
  `Style` do tempestroid) — só que aqui o alvo é **CSS**, então o mapeamento é
  quase identidade.
- **Tipagem como referência**, no espírito do FastAPI: define o tipo uma vez, ele
  vira validação em runtime + autocomplete no editor.
- **Mesmo `view()` em dois modos**: o código de aplicação não sabe (nem precisa
  saber) se o Python dele está rodando no browser (Modo A) ou no servidor (Modo
  B). Troca-se só o **transporte de patches**.
- **Async-first**: o runtime roda sobre um event loop asyncio; handlers, hooks de
  ciclo de vida e chamadas nativas podem ser `async def`.

É, em essência, o reconciliador renderer-agnostic do tempestroid com um terceiro
renderizador-folha (DOM) e dois transportes de patch (FFI Pyodide e WebSocket).

### 1.1 Por que dois modos (A e B)

| | Modo A — WASM (Pyodide) | Modo B — servidor (FastAPI + WS) |
|---|---|---|
| Onde o Python roda | No browser do usuário | No servidor |
| Análogo conhecido | PyScript / Pyodide | Phoenix LiveView / Streamlit |
| Transporte de patch | FFI Pyodide (em-processo) | WebSocket |
| Offline | Sim (depois do load) | Não (precisa do servidor) |
| Cold start | Pesado (~6–10 MB WASM) | Leve (HTML + cliente JS) |
| Latência por interação | Zero (local) | Round-trip de rede |
| Wheels nativas | Build emscripten (de-risk) | Wheels normais (servidor) |
| SEO / first paint | Fraco (hidrata depois) | Forte (server-render) |
| Casa com o stack web | Não usa FastAPI | Usa FastAPI + tempest-fastapi-sdk |

Os dois são **alvos de produção reais** — diferente do tempestroid, onde o Qt é só
simulador de dev. Aqui A e B são produtos que se entregam ao usuário final.

**Ordem de construção: A primeiro, B depois.** O Modo A prova que o core roda no
browser e que o renderizador DOM está correto sem nenhuma infra de servidor. O
Modo B reaproveita o cliente JS inteiro do Modo A, trocando só o transporte.

---

## 2. Escopo e não-objetivos

**É:**

- Web-only (browsers modernos com WebAssembly e WebSocket).
- Dois modos de execução com **uma única base de código de aplicação**.
- Renderizador DOM em **JavaScript puro, sem etapa de build, sem TypeScript, sem
  framework**.
- Controle total do stack (core, transporte, renderizador, empacotamento).
- Reuso do `tempest-core` (extraído do tempestroid) — fonte única de verdade do
  IR, reconciliador, estado, estilo e widgets.

**Não é (decisões conscientes):**

- Não é um framework JS — o desenvolvedor escreve **Python**, não JSX.
- Não usa TypeScript em lugar nenhum dos artefatos de build (preferência
  explícita do autor). JSDoc + testes garantem disciplina.
- Não é um motor de CSS com cascata — o estilo é inline tipado, sem seletores,
  specificity nem herança implícita (igual ao tempestroid).
- Não mira jogos/120fps; é ótimo para apps de dados, formulários, dashboards e
  ferramentas internas.
- Modo A não promete bundle pequeno; quem precisa de first-paint/SEO usa o Modo B.

---

## 3. Arquitetura

### 3.1 A ideia central: uma árvore, um renderizador-folha web, dois transportes

```
            Python tipado (view + state)        ← idêntico nos dois modos
                        │
                        ▼
        tempest-core: IR (Pydantic) ──diff──► patches    ← reusado do tempestroid
                        │
              ┌─────────┴──────────┐
        Modo A: transporte    Modo B: transporte
        FFI Pyodide           WebSocket
        (no browser)          (servidor → cliente)
              └─────────┬──────────┘
                        ▼
        cliente JS (puro): aplica patches no DOM
        + tradutor Style → CSS + captura de eventos    ← MESMO código nos dois modos
```

O **reconciliador é o mesmo código Python** (vem do `tempest-core`) nos dois modos.
O **cliente JS é o mesmo arquivo** nos dois modos. A única coisa que troca é a
**camada de transporte de patches/eventos**.

### 3.2 Camadas ortogonais

| Camada | Responsabilidade | Origem |
|---|---|---|
| Core | IR, diff/patch, estado, estilo, widgets | `tempest-core` (extraído do tempestroid) |
| Renderizador-folha | Aplicar patches no DOM, traduzir `Style → CSS`, capturar eventos | Cliente JS puro (este repo) |
| Transporte | Levar patches Python → JS e eventos JS → Python | `transports/wasm.py` (A) e `transports/websocket.py` (B) |
| Runtime | Hospedar o interpretador Python | Pyodide no browser (A) · CPython no servidor (B) |
| Host servidor | Sessão WS, ciclo de vida por conexão | FastAPI + tempest-fastapi-sdk (B) |
| Empacotamento | Gerar o artefato entregável | `tempestweb build` (estático A · app servidor B) |

### 3.3 Onde a tipagem "vaza" (o contrato)

O contrato tipado mora na fronteira **patch/evento** entre Python e o cliente JS,
e o Pydantic valida os pontos de cruzamento, análogo ao request/response do
FastAPI:

1. **IR → cliente**: a árvore/patches serializados que o JS interpreta.
2. **Eventos → handlers**: payloads que voltam do JS (click, input) validados
   antes de entrar na função Python.
3. **Chamadas nativas**: wrappers tipados sobre as Web APIs (geolocation,
   clipboard, camera), expostos como awaitables.

No Modo A o cruzamento é via `pyodide.ffi` (em-processo, sem rede). No Modo B é
via WebSocket (JSON na rede). O **schema é o mesmo** — só o transporte difere.

### 3.4 Regra de ouro de execução

O Python roda sobre um **event loop asyncio**. No Modo A, o Pyodide integra o
asyncio ao event loop do browser (webloop) — não há UI thread separada, mas
trabalho pesado em Python **trava a aba**, então I/O e CPU-bound devem ser async/
cedidos. No Modo B, cada conexão WS tem sua sessão asyncio no servidor; patches
saem pela conexão, eventos entram por ela.

### 3.5 Style → CSS: o alvo mais fácil

No tempestroid, `Style → Compose` é a parte difícil (vocabulários divergentes). Na
web, `Style → CSS` é **quase identidade** — o IR do tempestroid já foi desenhado
copiando o vocabulário do CSS (flexbox, box model, tipografia). Isso é uma
vantagem estrutural: o renderizador web é o mais fiel dos três. O tradutor vive no
**cliente JS** (um só), então serve A e B sem divergência possível.

---

## 4. Sistema de estilo "web-like" tipado

Reusa o `Style` do `tempest-core` integralmente. O tradutor `Style → CSS` vive no
cliente JS.

### 4.1 Layout padronizado em flexbox

Flexbox do CSS é o alvo direto — o `Style` do tempestroid já fala flex (direction,
justify, align, grow). Mapeamento 1:1: `flex-direction`, `justify-content`,
`align-items`, `flex-grow`, `gap`, `padding`, `margin`, `border`, `border-radius`,
`background`, cor, `font-*`, dimensões.

### 4.2 O que mapeia x o que não mapeia

**Mapeia limpo (v1):** todo o subconjunto flex + box model + tipografia + cores +
dimensões já validado no tempestroid — na web mapeia ainda melhor.

**Bônus que a web ganha de graça (pós-v1):** `:hover`/`:focus` (existem no
browser, diferente do toque do Android), grid CSS, transições/animações CSS, mídia
responsiva. São oportunidades, não dívidas.

### 4.3 Defesa contra divergência

Como há **um único tradutor** (JS) servindo A e B, não há divergência de tradutor.
O risco vira **A vs B produzirem DOM diferente** por causa do transporte. A
garantia é a **suite de conformância** (Trilho D): a mesma `view()` roda em Modo A
e Modo B e o DOM resultante tem que ser idêntico.

---

## 5. Dev loop: cockpit único

`tempestweb dev` espelha o `tempest dev` do tempestroid: file watcher + loop
interativo de comandos. No Modo A, recarrega a aba do browser; no Modo B,
reinicia a sessão no servidor e empurra para os clientes conectados.

```
tempestweb dev --mode wasm

  Dev server   http://127.0.0.1:8000
  Modo         WASM (Pyodide)   ● rodando
  Browser      auto-reload      ● conectado

  Comandos:
    r  hot reload   (v1: hot restart — ver abaixo)
    R  hot restart  (estado limpo)
    o  abrir no browser
    q  sair
```

### 5.1 v1 = só hot restart

Igual ao tempestroid: começar **só com hot restart** (re-roda do zero, estado
limpo) — robusto e simples. Hot reload com preservação de estado fica pós-v1.
Observação: no Modo B a preservação de estado é mais fácil (o estado vive no
servidor, não some no reload do cliente); no Modo A precisa serializar/restaurar.

### 5.2 Bind

`127.0.0.1` por padrão (dev local). `0.0.0.0` só quando outro dispositivo na LAN
precisa alcançar (ex.: testar num celular). Segue a regra de bind do CLAUDE.md.

---

## 6. Estratégia: trilhos

### Trilho 0 — `tempest-core` (extração, pré-requisito)

Extrair do tempestroid o núcleo renderer-agnostic (IR, reconciliador, estado,
estilo, widgets, validators) num pacote PyPI próprio, `tempest-core`. Tempestroid
e tempestweb passam a ser **renderizadores-folha** que dependem dele.

**Por quê:** fonte única de verdade. Um fix no diff vale para Android e web. Sem
isso, web ou acopla ao pacote Android inteiro (peso morto) ou forka e diverge.

**Risco controlado:** a extração não pode quebrar o tempestroid. Guarda: rodar a
suite de testes do tempestroid (incluindo conformância Qt↔Compose) verde **depois**
de trocar o core interno pelo `tempest-core`.

### Trilho W — renderizador-folha web (cliente JS puro, compartilhado A+B)

O cliente JavaScript: aplicador de patches no DOM, tradutor `Style → CSS`, captura
de eventos. **Escrito uma vez, serve os dois modos.** Sem build, sem TS, sem
framework — `<script type="module">` direto.

### Trilho A — Modo WASM (Pyodide) — PRIMEIRO

Python no browser. Prova o core no browser + o cliente JS, sem servidor.

### Trilho B — Modo servidor (FastAPI + WS) — DEPOIS

Python no servidor. Reusa o cliente JS inteiro do Trilho W, troca o transporte
por WebSocket.

**Convergência:** o mesmo `view()`/state roda em A e B. `tempestweb build --mode
wasm|server` escolhe o transporte. `native/` ganha dois backends por capacidade.

---

## 7. Fases e marcos

Cada fase tem um "feito quando" testável. Ordem dentro de cada trilho é
sequencial. Trilho 0 antecede tudo; Trilho W pode correr em paralelo ao A após W0.

### Trilho 0 — tempest-core

- **0.0 — Extração do core.** Mover `ir`, `reconciler`, `state`, `style`,
  `widgets`, `validators` do tempestroid para o pacote `tempest-core`; tempestroid
  passa a depender dele.
  *Feito quando:* `pip install tempest-core`; tempestroid importa do pacote; toda a
  suite do tempestroid (incl. conformância) verde.
- **0.1 — Extras de paridade (sob demanda).** Conforme a web precisar, extrair
  também `navigation`, `theme`, `i18n`, `animation`, formulários e listas.
  *Feito quando:* o item que a web consome importa de `tempest-core` e os testes
  passam nos dois consumidores.

### Trilho W — cliente JS (renderizador-folha web)

- **W0 — Fundação do repo.** Layout do pacote, `pyproject.toml`, `CLAUDE.md`,
  ferramentas (ruff, pyright/mypy, pytest), `tempestweb --help`, dependência em
  `tempest-core`.
  *Feito quando:* `pip install -e .` e a CLI respondem; lint/type-check rodam.
- **W1 — Aplicador de patches no DOM.** `client/dom.js`: aplica
  insert/remove/update/reorder/replace numa árvore DOM. JS puro, testado com jsdom.
  *Feito quando:* dado um JSON de patches golden, o DOM resultante bate com o
  esperado (teste jsdom).
- **W2 — Tradutor `Style → CSS`.** `client/style.js`: Style-data → estilo inline /
  CSS. Flexbox + box model + tipografia primeiro.
  *Feito quando:* golden de `Style` produz o CSS esperado; um layout flex renderiza
  correto no jsdom/headless.
- **W3 — Captura de eventos + interface de transporte.** `client/transport.js`
  define a interface (`sendEvent`, `onPatches`); captura click/input no DOM →
  payload tipado → `transport.sendEvent`.
  *Feito quando:* um click num botão chama o handler via um transporte mock e o
  payload validado chega "no Python" (stub).

### Trilho A — Modo WASM (Pyodide) — PRIMEIRO

- **A0 — De-risk crítico (Pyodide + pydantic).** Análogo ao B1 do tempestroid
  (wheels nativas). Rodar `tempest-core` dentro do Pyodide: `import pydantic`
  (pydantic-core em WASM) + reconciliador no browser.
  *Feito quando:* o reconciliador roda no browser e produz a lista de patches de
  uma `view()` de exemplo. **Verificar antes o estado atual do wheel de
  pydantic-core no Pyodide** (ver §8).
- **A1 — Transporte WASM.** `transports/wasm.py` + cola `pyodide.ffi`: Python
  produz patches → cliente JS aplica (em-processo); eventos JS → handler Python.
  *Feito quando:* o app `counter` roda 100% no browser — click incrementa, DOM
  atualiza, zero rede.
- **A2 — Loop async no browser.** Integrar asyncio do Pyodide ao event loop do
  browser; handler `async` com `await` (sleep ou `fetch`/HTTPX-pyodide) atualiza a
  tela ao concluir sem travar a aba.
  *Feito quando:* um handler `async` que faz `await` atualiza a UI sem congelar.
- **A3 — Empacotamento estático.** `tempestweb build --mode wasm` gera
  `index.html` + bootstrap JS que carrega Pyodide + o wheel do `tempest-core` + o
  `app.py`. Saída estática servível por qualquer CDN/host.
  *Feito quando:* `tempestweb build --mode wasm` gera uma pasta estática; abrir o
  `index.html` num servidor estático roda o app.
- **A4 — `tempestweb dev` (modo A).** File watcher + reload da aba (hot restart),
  cockpit de comandos.
  *Feito quando:* editar `app.py` recarrega o browser com a UI nova.
- **A5 — `native/` web (modo A).** Adaptadores Web API expostos como awaitables:
  geolocation, clipboard, notifications, storage; camera depois.
  *Feito quando:* `await geolocation.get()` retorna no Python rodando no browser.

### Trilho B — Modo servidor (FastAPI + WS) — DEPOIS

- **B0 — Host servidor.** FastAPI + tempest-fastapi-sdk com endpoint WebSocket;
  ao conectar, o servidor roda `view()` e envia os patches iniciais.
  *Feito quando:* o cliente conecta no WS, o servidor manda os patches iniciais, o
  DOM monta a tela.
- **B1 — Transporte WebSocket no cliente.** `transports/websocket.py` (Python) +
  impl JS da mesma interface do W3, agora sobre WS. Patches via WS → DOM; eventos →
  WS → handler no servidor.
  *Feito quando:* o `counter` — click vai por WS, o servidor reconcilia, o patch
  volta, o DOM atualiza. **Mesmo `app.py` do Modo A, sem mudança.**
- **B2 — Sessão e ciclo de vida por conexão.** Estado isolado por cliente;
  connect = mount, disconnect = unmount; cancelamento de tasks async órfãs no
  disconnect (concorrência estruturada).
  *Feito quando:* dois clientes têm estados independentes; desconectar cancela as
  tasks daquela sessão.
- **B3 — `native/` split cliente/servidor.** Definir o que roda no servidor (DB,
  push) vs no cliente (camera, geolocation — sempre no cliente, proxiado por um
  round-trip WS).
  *Feito quando:* `await camera.capture()` chamado no servidor dispara a captura no
  cliente e a foto volta pelo WS, tipada.
- **B4 — `tempestweb dev` (modo B).** Reload do servidor + push para os clientes
  conectados.
  *Feito quando:* editar `app.py` reinicia a sessão no servidor e atualiza os
  clientes abertos.

### Pós-convergência

- **Trilho C — Polimento.** `tempestweb new` (scaffold rodável), `tempestweb build
  --mode wasm|server`, `tempestweb run`. Hot reload com preservação de estado
  (Modo B primeiro — estado no servidor; Modo A depois — serializa/restaura).
- **Trilho D — Conformância.** Suite de golden snapshots: a mesma `view()` →
  DOM idêntico em Modo A e Modo B. O transporte **não pode** alterar o resultado.
  Análogo ao Qt-vs-Compose do tempestroid (aqui é A-vs-B), no CI.
- **Trilho E — Paridade.** Espelha o Trilho E do tempestroid, reusando os extras do
  `tempest-core`: navegação/rotas (a web ganha URL + History API de bônus), listas
  virtualizadas, overlays, animação (CSS transitions / Web Animations API), gestos,
  formulários, mídia, tema/i18n/a11y. Cada fase fecha com os **dois modos** verdes.

---

## 8. Riscos e mitigação

| Risco | Mitigação |
|---|---|
| `pydantic-core` (Rust→WASM) não carregar/quebrar no Pyodide | É a fase A0, atacada cedo (de-risk crítico). O Pyodide já distribui muitos pacotes pré-buildados — **verificar antes se pydantic vem no índice do Pyodide ou se precisa build emscripten próprio** |
| Extração do `tempest-core` quebrar o tempestroid | Trilho 0 só fecha com a suite + conformância do tempestroid verde após a troca |
| Bundle WASM grande / cold start lento (Modo A) | Lazy-load do Pyodide, cache via service worker, splash de carregamento; quem precisa de first-paint usa o Modo B |
| Latência por interação no Modo B (round-trip WS) | Coalescer patches por tick (já no core); UI otimista como refinamento pós-v1 |
| asyncio do Pyodide x event loop do browser | O Pyodide já integra (webloop); validar na A2; trabalho CPU-bound trava a aba — manter handlers async/leves |
| A e B produzirem DOM divergente | Suite de conformância A-vs-B (Trilho D) |
| Sem TypeScript, o cliente JS regredir sem aviso | JSDoc + testes jsdom obrigatórios por fase (W1/W2/W3); o type-check Python cobre a fronteira |
| Ecossistema Pyodide/WASM mudou pós jan/2026 | Ligar busca web antes de cravar a A0 — pode poupar dias |

> **Atenção:** o estado do Pyodide (versão do CPython embarcado, índice de pacotes
> pré-buildados, se `pydantic`/`pydantic-core` vêm prontos) evolui rápido.
> Verificar o estado atual **antes** de iniciar a A0.

---

## 9. Estrutura de repositório (proposta)

```
tempestweb/
├── pyproject.toml
├── CLAUDE.md
├── README.md
├── docs/
│   ├── plan.md                   # este documento
│   ├── roadmap.md
│   └── arquitetura.md
├── tempestweb/
│   ├── __init__.py
│   ├── transports/
│   │   ├── base.py               # Protocol: send_patches / recv_event
│   │   ├── wasm.py               # Modo A — ponte pyodide.ffi
│   │   └── websocket.py          # Modo B — WS
│   ├── runtime/
│   │   ├── wasm.py               # bootstrap Pyodide (A)
│   │   └── session.py            # sessão por conexão (B)
│   ├── server/                   # host FastAPI + tempest-fastapi-sdk (B)
│   │   ├── app.py
│   │   └── ws.py
│   ├── native/                   # adaptadores Web API (geo, clipboard, camera...)
│   ├── devserver/                # dev loop, file watch, reload
│   └── cli/                      # tempestweb new/dev/build/run
├── client/                       # JavaScript PURO (sem build, sem TS)
│   ├── tempestweb.js             # entrypoint / orquestrador
│   ├── dom.js                    # aplicador de patches no DOM
│   ├── style.js                  # tradutor Style → CSS
│   ├── transport.js              # interface comum
│   ├── transport-wasm.js         # impl FFI Pyodide (A)
│   └── transport-ws.js           # impl WebSocket (B)
├── examples/
│   └── counter/app.py            # roda igual em --mode wasm e --mode server
└── tests/
    ├── unit/                     # Python (transporte, native, cli)
    ├── client/                   # JS via jsdom (dom, style, transport)
    └── conformance/              # golden: view → DOM, Modo A vs Modo B
```

> `tempest-core` mora no **seu próprio repositório/pacote** (extraído do
> tempestroid). tempestweb apenas o declara como dependência.

---

## 10. Convenções de código (para o `CLAUDE.md`)

Manter o estilo consolidado nos outros projetos, com os ajustes web:

- **Python:** aspas duplas em tudo; tipagem obrigatória e completa; docstrings
  Google em inglês; imports de nível de módulo via `__init__.py` com `__all__`;
  async-first sobre um event loop asyncio.
- **JavaScript (cliente):** **JS puro, sem TypeScript, sem framework, sem etapa de
  build.** ES modules (`<script type="module">`). Aspas duplas. JSDoc nos contratos
  públicos. Testes jsdom obrigatórios. Sem dependências de runtime no cliente além
  do que o browser já oferece (e do Pyodide, no Modo A).
- **Stack Python:** `tempest-core` (núcleo do modelo), Pyodide (runtime do Modo A),
  FastAPI + tempest-fastapi-sdk (host do Modo B). Sem SQLAlchemy/Redis no core do
  framework — é um framework, não um serviço; o app do usuário é que pode usá-los.
- **Linguagem:** identificadores e docstrings em inglês; comentários explicativos
  podem ser PT-BR.

Fluxo com o Claude Code:

- Trabalhar **uma fase por vez**, sempre fechando no "feito quando".
- Rodar `review-pr` antes de mergear cada fase.
- Manter os testes da fase verdes antes de avançar — especialmente W1 (patches no
  DOM), A0 (Pyodide + pydantic) e D (conformância A↔B), que são a espinha dorsal da
  corretude.
- **Uma worktree por fase/agente** (regra do CLAUDE.md global).

---

## 11. Glossário

- **IR** — Intermediate Representation: a árvore de widgets serializável (Pydantic)
  que o renderizador interpreta. Vem do `tempest-core`.
- **Reconciliador** — compara a árvore nova com a anterior e emite patches. Mesmo
  código nos dois modos.
- **Patch** — operação mínima sobre a UI (insert/remove/update/reorder/replace).
- **Renderizador-folha** — quem aplica os patches numa tecnologia concreta. Aqui: o
  cliente JS que muta o DOM.
- **Transporte** — leva patches Python→JS e eventos JS→Python. `wasm` (FFI Pyodide)
  no Modo A; `websocket` no Modo B.
- **Modo A / WASM** — Python roda no browser via Pyodide.
- **Modo B / servidor** — Python roda no servidor; o cliente é fino e fala por WS.
- **Tradutor de estilo** — converte `Style` (Pydantic) para CSS. Vive no cliente JS,
  único para os dois modos.
- **Hot restart** — recarrega do zero, estado limpo (v1).
- **Hot reload** — recarrega preservando estado (pós-v1).

---

## 12. Próximo passo imediato

A ordem de arranque:

1. **Trilho 0, fase 0.0** — extrair o `tempest-core` do tempestroid (pré-requisito
   de tudo; fecha só com o tempestroid verde).
2. **Em paralelo, Trilho W (W0→W1)** — fundação do repo + aplicador de patches no
   DOM em JS puro, testado com golden de patches. Não depende de Pyodide nem de
   servidor — retorno em dias, igual ao Trilho A do tempestroid.
3. **Depois, Trilho A, fase A0** — o de-risk: provar `tempest-core` + `pydantic`
   rodando dentro do Pyodide no browser. **Verificar o estado atual do wheel de
   pydantic-core no Pyodide antes** (ligar busca web).

Com W1 + A0 verdes, o `counter` rodando 100% no browser (A1) está a poucos passos —
e o Modo B (Trilho B) reaproveita o cliente inteiro, trocando só o transporte.
