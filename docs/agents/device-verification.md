# Verificação em device/browser real dos itens 🔶

Registro das medições que o gate verde **não** pega: permissão concedida e negada,
ciclo de vida do service worker com a aba fechada, e hardware. Cada item tem o
procedimento exato para reproduzir, o que foi observado, e — quando não foi
possível — o que falta e por quê.

Este arquivo é o rastro que a issue
[#118](https://github.com/mauriciobenjamin700/tempestweb/issues/118) pedia: "a
saída aceitável é o registro da medição manual, não um teste automatizado fingindo
cobrir".

## Placar

| Item | Roadmap | Estado |
|---|---|---|
| geolocation real (concedida, negada, recuperação) | N3 | ✅ medido — 2026-08-23 |
| clipboard real (escrita + conteúdo lido de volta) | N3 | ✅ medido — 2026-08-23 |
| `storage` sobre IndexedDB, sobrevivendo a reload | N3 | ✅ medido — 2026-08-27 (**achou defeito**: caía em `localStorage` nos Modos A e B) |
| captura de câmera real | N4 | ✅ medido — 2026-08-27 (câmera virtual do OBS, por CDP no Chrome do Windows) |
| Background Sync com a aba fechada | P2 | ✅ medido — 2026-08-25 (**achou defeito**: #169) |
| WebPush: handler → notificação, com a aba fechada | P3 | ✅ medido — 2026-08-25 |
| WebPush: envio por push service real + `pushsubscriptionchange` | P3 | ⏳ falta par VAPID e endpoint de push alcançável |
| Web Audio além de `tone` (grafo de síntese/análise) | T24 | ✅ entregue e medido — v0.112.0, registro no `docs/roadmap.md` |

## O que foi medido

### geolocation — concedida, negada e recuperação (N3) ✅

```bash
uv run --frozen tempestweb run --mode server --path examples/geo_demo --port 8280
```

Concedida, com posição injetada:

```js
await context.grantPermissions(["geolocation"], { origin: "http://127.0.0.1:8280" });
await context.setGeolocation({ latitude: -8.0476, longitude: -34.877, accuracy: 12 });
```

Observado: `Status: idle` → **`Status: located`**, coords **`-8.048, -34.877`** — a
posição injetada, atravessando cliente → proxy nativo → Python → patch.

Negada **de verdade**:

```js
const cdp = await context.newCDPSession(page);
await cdp.send("Browser.setPermission", {
  origin: "http://127.0.0.1:8280",
  permission: { name: "geolocation" },
  setting: "denied",
});
```

Observado: **`Status: error: permission_denied: User denied Geolocation`**. O erro
atravessa a mesma cadeia, com o código estável que
`client/native/geolocation.js` mapeia.

Voltando para concedida com outra posição: **`Status: located`**, coords
**`51.500, -0.120`** — a app não fica presa no estado de erro.

!!! danger "`clearPermissions()` não é negar"
    A primeira tentativa usou `context.clearPermissions()` e a app ficou em
    **`Status: locating…` para sempre** — o que parece defeito e não é: sem
    concessão, o browser abre um prompt, e em automação **não há ninguém para
    responder**. `getCurrentPosition` então nunca chama sucesso nem erro. Negar de
    verdade exige `Browser.setPermission` com `setting: "denied"` via CDP. Quem
    repetir a medição com `clearPermissions` vai "achar" um bug que não existe.

### clipboard — escrita e conteúdo real (N3) ✅

```bash
uv run --frozen tempestweb run --mode server --path examples/clipboard-share --port 8281
```

```js
await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin });
// clicar em copy-btn, depois:
await page.evaluate(() => navigator.clipboard.readText());
```

Observado: status **`Copied to clipboard!`**, e o clipboard do sistema lido de
volta continha **`tempestweb — write UIs in typed Python, run them everywhere.`** —
o mesmo texto do snippet na tela. Ou seja, o dado atravessou de verdade, não só a
UI mudou de mensagem.

!!! note "A negação de *escrita* não é observável aqui"
    Com `clipboard-write` negado por CDP e as permissões limpas, a cópia
    **continuou funcionando**. Não é defeito: em contexto seguro e com gesto do
    usuário (a *transient activation* do clique), o Chrome libera
    `clipboard.writeText` sem permissão explícita — a permissão governa a
    **leitura**. Uma medição de negação precisa de um app que **lê** o clipboard;
    o exemplo atual só escreve e compartilha.

### Background Sync com a aba fechada (P2) ✅

Medido na 0.110.0, em duas origens virgens, mesmo procedimento — e a medição
**achou defeito**, corrigido em
[#169](https://github.com/mauriciobenjamin700/tempestweb/pull/169).

O `replayFromSync` alcançava `client/offline/{store,sync}.js` com `await import(...)`,
e nenhum service worker pode fazer isso:

```text
TypeError: import() is disallowed on ServiceWorkerGlobalScope by the HTML specification.
```

([w3c/ServiceWorker#1356](https://github.com/w3c/ServiceWorker/issues/1356).) Todo
`sync`/`periodicsync` estourava e caía no fallback que pinga clientes abertos — e com
a aba fechada não existe cliente para pingar. A fila ficava parada, **em silêncio**.

Procedimento: app aberto → rede **offline** → duas notas enfileiradas (`Pending: 2`,
**0** requests no servidor) → aba **fechada** → rede de volta.

| Worker | Requests após fechar a aba | Fila no IndexedDB |
|---|---|---|
| antigo (`import()` dinâmico) | **0** | **2 presas** |
| novo (import estático) | **2** | **vazia** |

```text
aba fechada   1787668388.034
rede de volta 1787668389.042
POST /api/log 1787668389.045   +1,011 s após fechar, +0,003 s após o reconnect
POST /api/log 1787668389.047   +1,013 s após fechar, +0,005 s após o reconnect
```

Zero páginas da origem abertas nas duas medições, `Idempotency-Key` distintas, corpo
correto. **Nenhum dispatch sintético**: o `sync` do Chrome disparou sozinho no
reconnect, porque a tag (`tw-offline-replay`) já era registrada pelo `enqueue`.

Guards em `tests/unit/test_sw_static_imports.py` — a suíte em Node **não** podia
pegar isto, porque `import()` funciona lá. Verificado que mordem: os quatro reprovam
contra o `sw.js` antigo.

!!! note "A corrida SW-drain × replay-da-página segue coberta só por idempotência"
    A medição prova que o drain do worker acontece com a aba fechada. Ela **não**
    observou a corrida com um replay de página simultâneo — para isso é preciso
    reabrir a aba no exato instante do reconnect. O double-send continua seguro por
    `Idempotency-Key`, que é o que a torna aceitável.

### WebPush: handler → notificação, com a aba fechada (P3) ✅

Mesma origem, permissão de notificação concedida, **0** páginas da origem abertas,
push entregue por CDP (`ServiceWorker.deliverPushMessage`): o handler recebeu o
payload intacto e chamou `showNotification` com título e corpo corretos.

```json
{"title":"Fila sincronizada","body":"2 mutações enviadas","tag":"tw-test"}
```

Isso mede **push → notificação dentro do worker, com a aba fechada**. O que
deliberadamente **não** cobre está na seção seguinte.

## O que falta, e o que exatamente rodar

### `storage` sobre IndexedDB (N3) — medido 2026-08-27

**Achou defeito, e não era persistência.** Um app Modo A buildado gravou duas
chaves e o que o browser mostrou foi:

```text
indexedDB.databases() → []
localStorage          → note (18 chars), bulk (142.890 chars, crus)
storage.configure(codec="deflate") → active=deflate supported=True
```

`native/storage.js` prefere `deps.store` (IndexedDB) e cai para `localStorage`
quando não recebe um — e **nada injetava esse store**: o `browserDeps()` de
`client/native/index.js` não o listava, então só o Modo C (que monta o seu em
`client/transpile/native.js`) usava IndexedDB. Modos A e B ficavam com o
`localStorage`: ~5 MB de teto, escrita **síncrona** na main thread, invisível
para o service worker — e o codec `deflate`, que configura o store de IndexedDB,
virava no-op enquanto respondia `supported=True`.

Persistência sozinha **não pega isso**: o `localStorage` também sobrevive a
reload. O que pega é olhar em qual backend o valor caiu.

Depois da correção (`store` injetado no `browserDeps()`, com o fallback de
`localStorage` alcançável também quando o IndexedDB existe e não abre), o mesmo
app:

| Passo | Medido |
| --- | --- |
| Escrita | `indexedDB.databases()` → `["tempestweb@1"]`, `localStorage` **vazio** |
| `bulk`, 142.890 caracteres | envelope `$twcodec=deflate`, **10.276 bytes** no disco |
| Reload | `note=persisted-value-42`, `bulk` `intact=True`, `keys=['bulk','note']` |
| `remove()` de tudo | `note=<not_found>`, `keys=[]`, object store vazio |
| Quota (`navigator.storage.estimate`) | **10.738.498.004 bytes** |

Procedimento, se for repetir: buildar um app que grave, ler no console
`indexedDB.databases()` **e** `Object.keys(localStorage)` — a pergunta é *onde
caiu*, não *se voltou* —, recarregar, ler de volta, limpar. E limpar service
worker e caches antes de medir, ou a página serve o precache do build anterior.

### captura de câmera real (N4) — medido 2026-08-27

O Chrome do harness (Linux, WSL2) não tem `/dev/video*`: `getUserMedia` responde
`NotFoundError`, e a capacidade reporta `code=unavailable` — "Requested device not
found" —, que é o caminho *sem device*, não o de permissão. Para o resto é preciso
um browser com câmera de verdade, e uma **câmera virtual do OBS no Windows**
serve: ela aparece como device real para o Chrome do Windows.

A ponte, sem instalar nada no Windows além do Chrome que já existe:

```powershell
# no Windows, com a Virtual Camera do OBS ligada
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --remote-debugging-port=9222 --remote-allow-origins=* `
  --user-data-dir="$env:TEMP\tw-cam"
```

```bash
# no WSL: sirva o artefato em 0.0.0.0 e dirija o Chrome do Windows por CDP
python3 -m http.server 8821 --bind 0.0.0.0    # de dist/wasm
node -e 'import("playwright-core").then(...)'  # chromium.connectOverCDP("http://127.0.0.1:9222")
```

Em WSL2 com rede **mirrored** o `127.0.0.1:9222` do WSL já alcança o Chrome do
Windows; sem mirrored, um `netsh interface portproxy` resolve. A página tem de ser
aberta em `http://localhost:<porta>` — `localhost` é contexto seguro e a câmera
funciona; um IP de LAN não é, e o `getUserMedia` some.

**Permissão sem prompt bloqueando**: conceder com
`context.grantPermissions(["camera"], {origin})` **na mesma sessão** que dirige (a
concessão morre no disconnect), e negar com
`browser.newBrowserCDPSession()` + `Browser.setPermission({origin, permission:
{name: "camera"}, setting: "denied"})` — o nome é `camera`, não `videoCapture`.

Medido, com a OBS Virtual Camera (2560×1080 @ 60 fps):

| O que | Resultado |
| --- | --- |
| `camera.capture()` | `Photo` tipado: `image/jpeg`, **2560×1080**, 22.772 chars de base64, `ref=blob:tw:1`, em **72 ms** |
| `capture(include_bytes=False)` | `bytes_b64=0`, `ref=blob:tw:2`, dimensões intactas — os pixels ficam no cliente |
| `CameraPreview.on_frame` (250 ms declarados) | 12 frames, gaps **[243, 250, 248, 248, 250, 264, 258, 249, 249, 242, 250]** |
| Frame entregue | `2560x1080 rotation=0`, 22.772 chars — **JPEG**, não RGB cru |
| Permissão negada (`Browser.setPermission`) | `capture` levanta `NativeError(code=permission_denied)`; o preview não monta `<video>`; o app reporta e **não trava** |
| Sem device (o Chrome do WSL) | `code=unavailable`, "Requested device not found" |

**O que a medição esclareceu:** o `CameraFrameEvent.data` do core é documentado
como "base64 do buffer RGB cru H×W×3" — que é a forma do Android. No browser o
cliente amostra o `<video>` num canvas e envia **JPEG** (22.772 chars contra os
~11 MB que o RGB cru daria). Não é defeito do cliente (RGB cru a cada 250 ms seria
impraticável), é uma diferença de plataforma que não estava escrita: agora está,
em `docs/advanced/capabilities.md`.

### WebPush: envio por push service real e `pushsubscriptionchange` (P3)

```bash
uv run --frozen python examples/webpush-server/server.py   # precisa de par VAPID
uv run --frozen tempestweb run --mode server --path examples/pwa-webpush --port 8000
```

O caminho de dentro do worker já foi medido (seção acima). O que falta é o que só um
push service real exerce: um par VAPID de teste e um endpoint alcançável (FCM).
Medir o round-trip completo — `pywebpush` → push service → worker → notificação com a
**aba fechada** —, o clique abrindo o deep link certo, e a rotação de chave
disparando `pushsubscriptionchange` com re-subscribe.

`ServiceWorker.deliverPushMessage` por CDP **não** substitui isto: ele injeta o
payload direto no worker, pulando exatamente a parte que pode falhar em produção
(assinatura VAPID, `410 Gone`, expiração de subscription).

### Web Audio além de `tone` (T24) — resolvido

Deixou de ser pendência: o grafo de síntese/análise saiu na **v0.112.0**
(`sequence`/`stop`/`levels`), com a medição em Chrome registrada na linha T24 do
`docs/roadmap.md`. Fica aqui só como ponteiro.

## Como registrar a próxima medição

1. Rode o procedimento da seção correspondente, sem atalho.
2. Anote **números e strings observadas** — não adjetivos. "Status virou
   `error: permission_denied`" vale; "funcionou" não.
3. Achou defeito? Abra issue própria e linke na
   [#118](https://github.com/mauriciobenjamin700/tempestweb/issues/118).
4. Passou? Suba o item de 🔶 para ✅ no `docs/roadmap.md` **com a data e o que foi
   medido**, e atualize o placar acima. A tabela é o registro.

### Receita para medir service worker com a aba fechada

Foi o que tornou a medição do Background Sync possível, e é reutilizável:

1. **Servidor que registra evidência**, não `http.server` puro: subclasse com
   `do_POST`/`do_PUT` que responde 200 e escreve uma linha JSON por request. Uma
   linha gravada **sem página aberta** é a prova de que o worker agiu sozinho.
2. **Playwright dirigindo o browser**: `context.setOffline(true/false)` para o
   offline, `page.close()` para fechar de verdade (não só perder o foco), e
   `context.pages()` para provar que não sobrou página da origem.
3. **`context.serviceWorkers().find(w => w.url().includes(porta)).evaluate(fn)`**
   roda **dentro do worker**, sem página. É como se lê o IndexedDB do outbox e se
   instrumenta `showNotification`. Foi este passo que devolveu o `TypeError` do
   `import()` — nada no lado da página o mostrava.
4. **CDP para o que só o browser faz**: `ServiceWorker.dispatchSyncEvent` e
   `ServiceWorker.deliverPushMessage`, a partir de uma página `about:blank` de
   âncora (`ServiceWorker.enable` não existe em sessão de browser, só de página).

!!! danger "Uma porta nova por **build**, não só por execução"
    O service worker da origem continua servindo o precache anterior, então medir
    num artefato rebuildado numa porta reusada mede **o build antigo** — e o sintoma
    parece bug de runtime. Já custou um issue inválido
    ([#171](https://github.com/mauriciobenjamin700/tempestweb/issues/171)).

!!! tip "Dispatch sintético é o último recurso"
    O `sync` do Chrome dispara sozinho no reconnect quando a tag foi registrada pelo
    `enqueue`. Uma medição que **precisa** de dispatch sintético para acontecer está
    provando menos do que parece — anote qual dos dois foi.
