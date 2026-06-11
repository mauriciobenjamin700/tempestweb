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
| Offline | Sim, pleno (após o load roda sem servidor) | Parcial (precisa do servidor p/ reconciliar; só leitura de cache + fila offline) |
| Cold start | Pesado (~6–10 MB WASM) | Leve (HTML + cliente JS) |
| Latência por interação | Zero (local) | Round-trip de rede |
| Wheels nativas | Build emscripten (de-risk) | Wheels normais (servidor) |
| SEO / first paint | Fraco (hidrata depois) | Forte (server-render) |
| Casa com o stack web | Não usa FastAPI | Usa FastAPI + tempest-fastapi-sdk |
| Transporte de patch (alt.) | — | WebSocket **ou** SSE (B5) |
| Instalável (PWA) | Sim — alvo natural (Trilho P) | Sim — install shell + push |
| WebPush | Sim (subscribe no browser; envio por qualquer servidor) | Sim (servidor é dono do endpoint) |

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

### Trilho P — PWA / Offline-first / WebPush (compartilhado)

Camada instalável e offline, paridade com o `tempest-react-sdk`, compartilhada
pelos dois modos: manifest + ícones (app instalável), service worker + app-shell
em cache com **update lifecycle** (offline após o 1º load — no Modo A também
resolve o cold-start do bundle WASM), offline-first em runtime com store
**IndexedDB** + **Background Sync** + fila/replay de eventos no reconnect (Modo B),
WebPush (VAPID via `tempest-fastapi-sdk[webpush]`), gate de PWA no CI e extras de
manifest. Detalhe fase-a-fase (P0–P5) em [`roadmap.md`](roadmap.md) e no §7 abaixo.

### Transporte SSE (B5)

Além do WebSocket, o Modo B ganha um transporte **SSE**: patches servidor→cliente
via `EventSource`, eventos cliente→servidor via HTTP POST — a **mesma** interface
`PatchTransport`. Reconnect exponencial, heartbeat e cookie-auth (paridade com o
`createEventStream` do `tempest-react-sdk`). Alternativa ao WS para infra que
bloqueia WebSocket.

### Trilho N — capacidades `native/` (compartilhado)

Adaptadores de Web API expostos como **awaitables tipados** em Python, espelhando
os módulos de plataforma do `tempest-react-sdk` (http, audio, share, geolocation,
clipboard, storage, camera). **Dois backends por capacidade, mesma API Python:**
no Modo A a chamada vai direto na Web API via `pyodide.ffi`; no Modo B ela é
**proxiada** por um round-trip (WS/SSE) — o servidor pede, o cliente executa, o
resultado tipado volta. O `http` (com idempotency key + retry) é a base do replay
offline do Trilho P. Detalhe fase-a-fase (N0–N4) no §7.

### Trilho O — observabilidade / produção (compartilhado)

Provedores de produção em **Python tipado** sobre o **padrão adapter** (interface
mínima; troca o backend sem tocar a app) herdado do `tempest-react-sdk`: telemetry
(console/Sentry/PostHog), logger com sinks, error boundary com fallback + report,
feature flags (InMemory/GrowthBook/LaunchDarkly) e auth de cliente (store + guarda
de rota + JWT + fila de refresh; servidor reusa `JWTUtils` do
`tempest-fastapi-sdk`). Idêntico nos dois modos. Detalhe fase-a-fase (O0–O4) no §7.

**Convergência:** o mesmo `view()`/state roda em A e B. `tempestweb build --mode
wasm|server` escolhe o transporte. `native/` (Trilho N) ganha dois backends por
capacidade; as camadas PWA (Trilho P) e produção (Trilho O) são compartilhadas. O
`view()`, o estado, as capacidades, a observabilidade e a casca PWA são escritos
**uma vez**; o `--mode` só troca o transporte.

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
- **B5 — Transporte SSE (alternativa ao WS).**
  - **Objetivo:** segundo transporte do Modo B onde o WebSocket é bloqueado por
    proxy/infra. Patches servidor→cliente por um stream SSE; eventos
    cliente→servidor por HTTP POST. Mesma `view()`, mesmo `app.py`.
  - **Arquivos:** `tempestweb/transports/sse.py` (impl Python do `PatchTransport`),
    `client/transport-sse.js` (impl JS da interface do W3), rota
    `GET /sse/{session}` (stream) + `POST /sse/{session}/event` no `server/`.
  - **Contrato:** servidor responde `text/event-stream`; cada tick vira um evento
    SSE cujo `data:` é o JSON do batch de patches (mesmo shape do WS — ver
    `docs/contract.md`). Heartbeat: evento nomeado `ping` em intervalo fixo p/
    manter a conexão viva e detectar queda. Eventos do cliente vão por `POST` com o
    corpo no shape `TWEvent` (`{type, key, payload}`), correlacionados à sessão pela
    URL. `namedEvents` opcional; `withCredentials` p/ cookie-auth.
  - **Reconnect:** o cliente reconecta com backoff exponencial (até 10 tentativas),
    reusando o `Last-Event-ID` para retomar do último tick — paridade com o
    `createEventStream` do `tempest-react-sdk`. Esgotou as tentativas → estado
    "desconectado" (banner do Trilho P).
  - **Depende de:** B0–B2 (host, sessão, ciclo de vida). Reusa o `client/dom.js`
    (W1) e a interface de transporte (W3) sem mudança.
  - **Feito quando:** o `counter` roda por SSE — click faz `POST`, o servidor
    reconcilia, o patch volta pelo stream, o DOM atualiza; derrubar a conexão e
    reconectar não duplica nem perde patch. **Mesmo `app.py` do Modo A.**
  - **Verificação:** teste de integração da rota SSE (FastAPI `TestClient` lendo o
    stream); teste jsdom do `transport-sse.js` com `EventSource` mockado cobrindo
    parse, heartbeat, reconnect e max-retries (espelhar os testes do React SDK).
  - **Cuidados:** SSE é **uni-direcional** (só servidor→cliente) — por isso os
    eventos sobem por POST, não pelo mesmo canal. Buffering de proxies pode atrasar
    o stream (`X-Accel-Buffering: no` no Nginx). Limite de conexões SSE por
    domínio no HTTP/1.1 (~6) — não é problema com 1 stream por aba.

### Trilho P — PWA / Offline-first / WebPush (fases detalhadas)

> Pré-requisitos transversais: **P1 (service worker)** é pré-requisito de **P3
> (WebPush)** e de boa parte do **P2 (offline runtime)**. **P0/P1/P3/P4** são
> compartilhados pelos dois modos; **P2** tem ramo por modo (ver nota no
> `roadmap.md`). O empacotamento do app-shell depende do **A3** (Modo A) e do
> **B0** (Modo B).

- **P0 — Manifest + ícones + install prompt.**
  - **Objetivo:** tornar o app **instalável** ("Add to Home Screen"), abrindo em
    janela `standalone`, com prompt de instalação em contexto.
  - **Arquivos:** geração de `manifest.webmanifest` no `tempestweb build` (ambos os
    modos); jogo de ícones (incl. **maskable** 192/512 + `apple-touch-icon`);
    `client/pwa/install-prompt.js` (captura `beforeinstallprompt`, guarda o evento,
    expõe `promptInstall()`); `<link rel="manifest">` injetado no `index.html`.
  - **Contrato do manifest:** `name`, `short_name`, `description`, `start_url`,
    `scope`, `display: "standalone"`, `theme_color`, `background_color`, `icons[]`
    (com `purpose: "any maskable"`). Valores default vêm do `tempestweb new`
    (Trilho C) e são sobrescrevíveis por config do projeto.
  - **Soft pre-prompt:** **não** disparar `prompt()` nativo a frio — pedir só após
    um gesto/contexto (ex.: o usuário usou o app por X). Padrão herdado do hook
    `useBeforeInstallPrompt` do React SDK.
  - **Depende de:** A3 (build estático) p/ o Modo A; W0 p/ o esqueleto de build.
  - **Feito quando:** Lighthouse marca **"installable"** verde; instalar abre em
    janela standalone; o pre-prompt aparece só em contexto e instala ao confirmar.
  - **Verificação:** teste do gerador de manifest (shape + ícones presentes);
    Lighthouse PWA no Trilho P4; verificação manual de instalação (registrar no
    commit — regra de verificação visual).
  - **Cuidados:** ícones maskable mal recortados estragam o ícone no Android; testar
    com a "safe zone". `start_url`/`scope` errados quebram a navegação standalone.

- **P1 — Service worker + app-shell + update lifecycle.**
  - **Objetivo:** **offline após o 1º load** via precache do app-shell, e atualizar
    o SW sem deixar o usuário preso em build velho.
  - **Arquivos:** `client/sw/sw.js` (worker), `client/sw/register.js` (thread
    principal: `registerServiceWorker({url, onUpdate, onError})`, `skipWaiting()`,
    `unregisterAll()`), passo de build que injeta o **precache manifest**
    (lista de assets com hash). Paridade com `registerServiceWorker`/`skipWaiting`/
    `unregisterAllServiceWorkers` do React SDK.
  - **Precache (app-shell):** sempre o cliente JS (`dom.js`/`style.js`/`events.js`/
    `tempestweb.js` + transporte) + `index.html` + ícones; no **Modo A** também o
    runtime Pyodide, o wheel do `tempest-core` e o `app.py`. Estratégia
    **cache-first** no shell (resolve o cold-start do WASM citado no §8).
  - **Update lifecycle:** ao detectar SW novo em `waiting`, dispara `onUpdate` →
    a UI mostra "nova versão, recarregar"; ao confirmar, `skipWaiting` +
    `clients.claim()` + `location.reload()`. No `activate`, **apaga caches antigos**
    (versão no nome do cache).
  - **Depende de:** P0 (estar num contexto PWA), A3/B0 (assets a precachear).
  - **Feito quando:** segundo load **offline** abre o app; publicar uma versão nova
    mostra o prompt de update e, ao confirmar, carrega a nova sem reload manual em
    loop; caches antigos somem no `activate`.
  - **Verificação:** testes jsdom/worker mock do `register.js` (eventos
    `updatefound`/`waiting`, `skipWaiting`, cleanup) — espelhar os testes do React
    SDK (`register-service-worker.update`/`unregister`). Teste offline no Trilho P4.
  - **Cuidados:** SW só sobe em **HTTPS** (ou `localhost`). `scope` do SW limita o
    que ele controla. Precache sem hash → usuário preso em asset velho; **sempre
    versionar**. Não cachear respostas de API no app-shell (vai p/ P2).

- **P2 — Offline-first em runtime (IndexedDB + Background Sync).**
  - **Objetivo:** dados/estado disponíveis offline e mutações que sobrevivem à
    falta de rede.
  - **Arquivos:** `client/offline/store.js` (wrapper IndexedDB **owner-scoped por
    domínio**, espelhando o `createOfflineStore`/dexie do React SDK), exposto ao
    Python como `native.storage` (Trilho N3); `client/offline/sync.js` (fila de
    mutations + Background Sync); estratégias de cache em runtime no `sw.js`.
  - **Store IndexedDB:** API `put`/`bulkPut`/`get`/`list(owner, {orderBy, reverse,
    limit})`/`update`/`updateMany`/`delete`/`clear`/`count`, com `databaseName`,
    `version`, `tableName`, `indexes`, `keyPath`, `ownerField`. Usos: rascunhos,
    cache de dados, histórico de eventos SSE.
  - **Persistência:** `navigator.storage.persist()` p/ a base não ser despejada sob
    pressão de disco. Estratégias por recurso: **stale-while-revalidate** p/ assets,
    **network-first** p/ dados.
  - **Fila offline + Background Sync:** mutations feitas offline entram numa fila
    durável (IndexedDB) com **idempotency key** (do `native.http`, N0); quando a
    rede volta, **Background Sync** (`sync`/`periodicsync`) reaplica com a **aba
    fechada**. Onde o Background Sync não existe (Safari), faz replay no reconnect
    com a aba aberta.
  - **Ramo por modo:** **Modo A** — estado/dados vivem no browser; offline é pleno.
    **Modo B** — offline mostra o último estado em cache (read-only) + enfileira os
    eventos; ao reconectar, o servidor reconcilia. Banner online/offline ligado ao
    `ConnectivityEvent` do core.
  - **Depende de:** P1 (SW), N0 (http com idempotency/retry).
  - **Feito quando:** com a rede desligada o app abre e lê dados do IndexedDB; uma
    mutation feita offline é enfileirada e **reaplica sozinha** ao voltar a rede
    (Background Sync onde houver), sem duplicar (idempotency); o banner reflete o
    estado de conectividade.
  - **Verificação:** testes do `store.js` (CRUD + owner-scoping + list ordenada —
    espelhar `create-offline-store.test`), teste da fila/replay com idempotency,
    teste do banner reagindo ao `ConnectivityEvent`.
  - **Cuidados:** quota e despejo de IndexedDB; conflitos de merge no replay
    (definir política — last-write-wins v1); Background Sync **não** existe no
    Safari (degradar p/ reconnect).

- **P3 — WebPush Notifications.**
  - **Objetivo:** notificações push que chegam **com a aba fechada**.
  - **Arquivos (cliente):** `client/push/web-push-client.js`
    (`subscribe`/`unsubscribe`/`isSubscribed`, permissão, `isPushSupported`,
    `urlBase64ToUint8Array`), exposto ao Python como `native.notifications`
    (`await notifications.subscribe()`); handlers no `client/sw/sw.js`
    (`installPushHandler`, `installNotificationClickHandler`). Paridade com
    `WebPushClient`/`usePushSubscription` + os handlers de SW do React SDK.
  - **Arquivos (servidor):** envio via `tempest-fastapi-sdk[webpush]` (pywebpush);
    **store de subscriptions** por usuário/tópico no app do usuário; endpoints
    `POST /webpush/subscribe` e `DELETE /webpush/my`.
  - **Divisão de responsabilidade:** **cliente faz o browser-flow** (permissão,
    `pushManager.subscribe`, ler/cancelar a subscription); **servidor é dono do
    endpoint** — recebe a subscription pelos callbacks e a persiste; o framework
    não decide o schema do teu endpoint.
  - **Recebimento (SW):** `installPushHandler({defaultTitle, defaultIcon,
    transform})` — `transform` pode **dropar** push silencioso (retornando `null`);
    `installNotificationClickHandler({focusOrOpenWindow, fallbackUrl})` — o clique
    foca/abre a janela e roteia via **`DeepLinkEvent` do core**. Suporte a
    **actions** (botões) na notificação e **Badging API** (contador no ícone).
  - **Lifecycle de subscriptions:** servidor limpa endpoints mortos (`410 Gone`) no
    envio; lida com rotação/expiração da chave VAPID (resubscribe no cliente).
  - **Depende de:** P1 (SW registrado é pré-requisito do `subscribe`).
  - **Feito quando:** o usuário concede permissão e se inscreve; o servidor envia e
    a notificação aparece **com a aba fechada**; clicar abre/foca a janela na rota
    certa (`DeepLinkEvent`); desinscrever para de receber; endpoint morto é limpo.
  - **Verificação:** testes do `web-push-client.js` (supported/unsupported/permission
    denied — espelhar os testes do React SDK), teste do `installPushHandler`/
    `installNotificationClickHandler` (worker mock), teste e2e no Trilho P4.
  - **Cuidados (ver §8):** **iOS/Safari** exige PWA **instalada** (16.4+,
    `standalone`, via APNs) — sem isso, push não funciona no iOS; detectar e
    degradar. **Chaves VAPID/segredos nunca commitados** (env/secret). Permissão:
    soft pre-prompt, não pedir a frio.

- **P4 — Gate PWA no CI.**
  - **Objetivo:** travar regressão de PWA/offline/push automaticamente.
  - **Arquivos:** job no CI rodando **Lighthouse PWA** (headless), teste de SW
    (precache + update), teste **e2e de push** (subscribe → envio → notificação)
    com browser headless (Playwright).
  - **Depende de:** P0–P3.
  - **Feito quando:** o CI reprova um PR que quebre "installable", o offline ou o
    fluxo de push; o relatório Lighthouse fica anexado ao job.
  - **Verificação:** o próprio gate é a verificação; rodar localmente antes do push.
  - **Cuidados:** Lighthouse headless é sensível a flakiness — fixar versão do
    Chromium e usar thresholds, não notas exatas.

- **P5 — Extras de manifest (valor de produto).**
  - **Objetivo:** integrações de SO que agregam valor: atalhos e receber conteúdo.
  - **Arquivos:** campos `shortcuts`, `share_target` e `file_handlers` no
    `manifest.webmanifest`; rota/handler do share target ligada ao `native.share`
    (Trilho N2).
  - **Depende de:** P0 (manifest), N2 (share).
  - **Feito quando:** atalhos aparecem no menu de contexto do ícone instalado;
    compartilhar conteúdo de outro app para o nosso entrega o payload na rota certa.
  - **Verificação:** validação do manifest estendido; verificação manual no Android
    (registrar no commit).
  - **Cuidados:** `share_target` exige `method`/`enctype` corretos e rota dedicada;
    suporte desigual entre browsers — tratar como progressive enhancement.

### Trilho N — capacidades `native/` (fases detalhadas)

> Cada capacidade tem **dois backends, uma API Python**. Modo A: chamada direta na
> Web API via `pyodide.ffi`. Modo B: **proxy por round-trip** — o servidor emite um
> "pedido nativo" pelo transporte (WS/SSE), o cliente executa a Web API e devolve o
> resultado tipado. O contrato (Pydantic) é o mesmo; só o transporte difere.
> Expande o A5 (que só listava geo/clipboard/notifications/storage).

- **N0 — `native.http` (cliente HTTP tipado).**
  - **Objetivo:** cliente HTTP pythônico com `retry`, **idempotency key**, upload
    com progresso e `poll` — base do replay offline (P2).
  - **Arquivos:** `tempestweb/native/http.py` (API tipada), backend Modo A
    (`fetch`/HTTPX-pyodide), backend Modo B (httpx no servidor).
  - **API:** `await http.request(method, url, *, json=..., headers=...,
    retry=RetryOptions(...), idempotency_key=...)`; `generate_idempotency_key()`;
    `await http.upload(url, file, on_progress=...)`; `await http.poll(url, *,
    interval, until=...)`. Espelha `createApiClient`/`retry`/
    `generateIdempotencyKey`/`uploadWithProgress`/`usePoll` do React SDK.
  - **Depende de:** A2 (loop async) p/ o Modo A.
  - **Feito quando:** uma requisição com `retry` reentrega com backoff; a mesma
    `idempotency_key` não duplica efeito no servidor; upload reporta progresso.
  - **Verificação:** testes com servidor HTTP mock (retry, idempotency, progresso).
  - **Cuidados:** no Modo A, CORS e ausência de alguns headers no `fetch`; retry só
    em métodos idempotentes ou com idempotency key.

- **N1 — `native.audio`.**
  - **Objetivo:** tocar sons curtos (chime de notificação/sucesso), pareando com
    WebPush (P3).
  - **Arquivos:** `tempestweb/native/audio.py`; backend cliente em
    `client/native/audio.js`.
  - **API:** `await audio.play(src, *, volume=1.0)`; `audio.stop()`; player isolado
    por canal. Espelha `playAudio`/`useAudio` do React SDK.
  - **Feito quando:** `await audio.play("/audio/plim.wav", volume=0.4)` toca após um
    gesto do usuário.
  - **Cuidados:** browsers **bloqueiam autoplay** até a 1ª interação — `play` antes
    disso resolve com falha graciosa (a UI "desbloqueia" no primeiro clique).

- **N2 — `native.share`.**
  - **Objetivo:** compartilhar via folha de compartilhamento do SO, com fallback.
  - **Arquivos:** `tempestweb/native/share.py`; `client/native/share.js`.
  - **API:** `await share(title=..., text=..., url=..., files=...)` →
    `ShareResult(shared|cancelled|unsupported)`; `is_share_supported()`. Espelha
    `share`/`isShareSupported` do React SDK; pareia com `share_target` (P5).
  - **Feito quando:** em browser suportado abre a folha de share; sem suporte, cai
    no fallback (ex.: clipboard) sem erro.
  - **Cuidados:** `navigator.share` exige gesto do usuário e contexto seguro;
    compartilhar arquivos tem suporte desigual.

- **N3 — `native.geolocation` / `clipboard` / `storage`.**
  - **Objetivo:** migrar o conteúdo do A5 p/ a forma de capacidade com dois
    backends, e ligar `storage` ao IndexedDB do P2.
  - **Arquivos:** `tempestweb/native/{geolocation,clipboard,storage}.py`; backends
    cliente correspondentes; `storage` por cima de `client/offline/store.js`.
  - **API:** `await geolocation.get()` → `Position`; `await clipboard.read()` /
    `clipboard.write(text)`; `storage` = a API do store owner-scoped (P2).
  - **Feito quando:** `await geolocation.get()` retorna a posição (com permissão);
    `storage.put/list` persiste e lê do IndexedDB.
  - **Cuidados:** todas exigem permissão e contexto seguro; tratar negação como
    caminho normal (não exceção fatal).

- **N4 — `native.camera` / mídia.**
  - **Objetivo:** captura de câmera/mídia — **sempre no cliente**; no Modo B,
    proxiada por WS (herda o B3).
  - **Arquivos:** `tempestweb/native/camera.py`; `client/native/camera.js`.
  - **API:** `await camera.capture()` → bytes/`Blob` tipado.
  - **Feito quando:** `await camera.capture()` no Modo A captura no browser; no Modo
    B, chamado "no servidor", dispara a captura no cliente e a foto volta tipada.
  - **Cuidados:** permissão de câmera; tamanho do payload no round-trip do Modo B
    (comprimir antes de subir).

### Trilho O — observabilidade / produção (fases detalhadas)

> Todos com **padrão adapter** (interface mínima; troca o backend sem tocar a app),
> herdado do `tempest-react-sdk`. Puro Python tipado, idêntico nos dois modos.

- **O0 — Telemetry.**
  - **Objetivo:** instrumentar eventos do framework e do app (SW, push, replay
    offline, erros) com provedor plugável.
  - **Arquivos:** `tempestweb/observability/telemetry.py` (provider + protocolo
    `TelemetryAdapter`), adapters `console`, `sentry`, `posthog`.
  - **API:** `telemetry.track(event, props)`, `telemetry.identify(user)`; provider
    recebe um adapter na inicialização. Espelha `TelemetryProvider`/`useTelemetry` +
    adapters do React SDK.
  - **Feito quando:** trocar o adapter (console→Sentry) não muda nenhuma chamada
    `track`; eventos de subscribe/entrega de push e de replay offline aparecem.
  - **Cuidados:** não vazar PII nos props; amostragem p/ não inundar o backend.

- **O1 — Logger.**
  - **Objetivo:** logging estruturado com sinks plugáveis e níveis tipados.
  - **Arquivos:** `tempestweb/observability/logger.py` (`create_logger`,
    `console_sink`, protocolo `LoggerSink`, `LogLevel`).
  - **API:** `log = create_logger(sinks=[console_sink])`; `log.info(msg, **fields)`.
  - **Feito quando:** um log estruturado sai no console e num sink custom ao mesmo
    tempo; o nível filtra corretamente.
  - **Cuidados:** no Modo A o sink default é o console do browser; sinks de rede
    devem ser async/não-bloqueantes.

- **O2 — Error boundary.**
  - **Objetivo:** capturar erro de **render** → fallback visual + report, sem
    derrubar o app.
  - **Arquivos:** `tempestweb/observability/error_boundary.py` (widget/decorator de
    fronteira); liga no O0 (report) e no rollback de state que o core já faz.
  - **API:** envolver uma subárvore; em erro, renderiza o fallback e chama o
    handler (que pode mandar p/ telemetry).
  - **Feito quando:** uma `view()` que lança em render mostra o fallback (o resto do
    app segue vivo) e dispara o report.
  - **Cuidados:** distinguir erro de render (boundary) de erro de handler async
    (vai p/ o tratamento do loop); não engolir o stack — reportar.

- **O3 — Feature flags.**
  - **Objetivo:** ligar/desligar features em runtime com rollout gradual.
  - **Arquivos:** `tempestweb/observability/feature_flags.py` (provider + protocolo
    `FeatureFlagsAdapter`), adapters `in_memory`, `growthbook`, `launchdarkly`.
  - **API:** `flags.is_enabled(key)`, `flags.get(key, default)`,
    `flags.on_change(listener)`. Espelha o `FeatureFlagsProvider` + adapters do
    React SDK; a interface do adapter é minúscula (~implementável em ~20 linhas).
  - **Feito quando:** com o adapter InMemory, mudar uma flag re-renderiza a parte
    que depende dela; trocar p/ GrowthBook/LaunchDarkly não muda as chamadas.
  - **Cuidados:** flags não são segredo; default seguro quando o backend está fora.

- **O4 — Auth de cliente.**
  - **Objetivo:** store de auth + guarda de rota + helpers de JWT + fila de refresh;
    OAuth.
  - **Arquivos:** `tempestweb/observability/auth.py` (ou `tempestweb/auth/`):
    `create_auth_store`, guarda de rota, `decode_jwt`, `is_jwt_expired`,
    `create_refresh_queue`. Servidor reusa `JWTUtils` do `tempest-fastapi-sdk`.
  - **API:** store com `login/logout/token/user`; guarda redireciona se não-autado;
    a fila de refresh **serializa** refresh concorrente (uma renovação, várias
    esperas). Espelha `createAuthStore`/`AuthGuard`/`createRefreshQueue` do React
    SDK.
  - **Feito quando:** rota protegida redireciona sem sessão; token expirado dispara
    **um** refresh enquanto várias chamadas aguardam; logout limpa tudo.
  - **Cuidados:** nunca guardar token em lugar inseguro; no Modo A o token vive no
    browser (storage) — tratar XSS como risco; no Modo B vive na sessão do servidor.

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
| WebPush não funciona no iOS sem PWA instalada | iOS/Safari 16.4+ só entrega push com a PWA **instalada** (`standalone`, via APNs); detectar suporte (`isPushSupported`) e degradar com elegância (P3) |
| Background Sync ausente no Safari | Replay offline cai no reconnect com a aba aberta onde não há Background Sync (P2); não prometer replay com aba fechada universal |
| Chaves VAPID / segredos de push vazarem | Vivem como env/secret, **nunca** commitados; servidor é dono do endpoint e do envio (P3) |
| IndexedDB despejado sob pressão de disco | `navigator.storage.persist()` (P2); tratar despejo como cache-miss, não como perda fatal de dados |
| Usuário preso em build velho do SW | Update lifecycle obrigatório (P1): precache versionado por hash, prompt de update, cleanup no `activate` |
| SSE sofrer buffering de proxy / timeout | `X-Accel-Buffering: no` + heartbeat `ping`; reconnect exponencial com `Last-Event-ID` (B5) |
| Gate de PWA flaky no CI | Fixar versão do Chromium e usar thresholds, não notas exatas do Lighthouse (P4) |

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
│   │   ├── websocket.py          # Modo B — WS
│   │   └── sse.py                # Modo B — SSE (B5): stream + POST de eventos
│   ├── runtime/
│   │   ├── wasm.py               # bootstrap Pyodide (A)
│   │   └── session.py            # sessão por conexão (B)
│   ├── server/                   # host FastAPI + tempest-fastapi-sdk (B)
│   │   ├── app.py
│   │   ├── ws.py
│   │   └── sse.py                # rotas GET stream + POST evento (B5)
│   ├── native/                   # Trilho N — capacidades (2 backends, 1 API)
│   │   ├── http.py               # N0 — retry + idempotency + upload + poll
│   │   ├── audio.py              # N1
│   │   ├── share.py              # N2
│   │   ├── geolocation.py        # N3
│   │   ├── clipboard.py          # N3
│   │   ├── storage.py            # N3 — por cima do store IndexedDB (P2)
│   │   ├── notifications.py      # P3 — subscribe/permission (WebPush)
│   │   └── camera.py             # N4 — captura (proxiada por WS no Modo B)
│   ├── observability/            # Trilho O — produção (padrão adapter)
│   │   ├── telemetry.py          # O0 — console / sentry / posthog
│   │   ├── logger.py             # O1 — sinks plugáveis
│   │   ├── error_boundary.py     # O2 — fallback + report
│   │   ├── feature_flags.py      # O3 — in_memory / growthbook / launchdarkly
│   │   └── auth.py               # O4 — store + guarda + JWT + refresh queue
│   ├── pwa/                      # Trilho P — geração de manifest + ícones (P0)
│   ├── devserver/                # dev loop, file watch, reload
│   └── cli/                      # tempestweb new/dev/build/run
├── client/                       # JavaScript PURO (sem build, sem TS)
│   ├── tempestweb.js             # entrypoint / orquestrador
│   ├── dom.js                    # aplicador de patches no DOM
│   ├── style.js                  # tradutor Style → CSS
│   ├── events.js                 # captura de eventos (W3)
│   ├── transport.js              # interface comum
│   ├── transport-wasm.js         # impl FFI Pyodide (A)
│   ├── transport-ws.js           # impl WebSocket (B)
│   ├── transport-sse.js          # impl SSE (B5)
│   ├── pwa/
│   │   └── install-prompt.js     # P0 — beforeinstallprompt + soft pre-prompt
│   ├── sw/
│   │   ├── sw.js                 # P1/P3 — worker: precache, update, push, click
│   │   └── register.js           # P1 — register + onUpdate + skipWaiting
│   ├── offline/
│   │   ├── store.js              # P2 — IndexedDB owner-scoped (≈ createOfflineStore)
│   │   └── sync.js               # P2 — fila de mutations + Background Sync
│   ├── push/
│   │   └── web-push-client.js    # P3 — subscribe/unsubscribe/isSubscribed
│   └── native/                   # backends JS das capacidades (audio, share, camera…)
├── examples/
│   └── counter/app.py            # roda igual em --mode wasm e --mode server
└── tests/
    ├── unit/                     # Python (transporte, native, observability, cli)
    ├── client/                   # JS via jsdom (dom, style, transport, sw, push, offline)
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

**Sequência dos trilhos de capacidade (N/O/P) e do SSE (B5):**

1. **Trilho N (N0 primeiro)** pode começar logo após **A2** (loop async) — o
   `native.http` com idempotency/retry é pré-requisito do replay offline (P2) e
   tem valor imediato no Modo A. As demais capacidades (N1–N4) seguem sob demanda.
2. **Trilho P** começa quando há artefato p/ empacotar: **P0/P1 após A3** (build
   estático do Modo A). **P3 (WebPush) depende de P1 (SW)**. **P2 (offline runtime)
   depende de N0 (http) + P1**. **P4 (gate CI)** fecha o trilho. **P5** é valor de
   produto, por último.
3. **B5 (SSE)** entra após **B0–B2** (host + sessão), em paralelo ao polimento do
   WS — é um segundo transporte, não bloqueia o caminho crítico.
4. **Trilho O** é ortogonal e pode correr em paralelo a qualquer momento após **W3**
   (a app já existe): comece por **O0 (telemetry)** + **O2 (error boundary)** —
   eles instrumentam justamente os fluxos novos de SW/push/offline e capturam
   regressão cedo. O1/O3/O4 entram conforme o app do usuário precisar.

> Regra que não muda: **uma fase por vez**, fechando no "feito quando", com os
> testes da fase verdes e **uma worktree por fase/agente**. Cada fase acima tem
> Objetivo / Arquivos / Contrato / Depende de / Feito quando / Verificação /
> Cuidados no §7 — o agente não precisa inferir nada do contexto da conversa.
