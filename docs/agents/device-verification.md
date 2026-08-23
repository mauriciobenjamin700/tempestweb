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
| captura de câmera real | N4 | ⏳ falta hardware ou Chrome com fake device |
| Background Sync com a aba fechada | P2 | ⏳ falta device + browser com a permissão |
| WebPush com a aba fechada + `pushsubscriptionchange` | P3 | ⏳ falta push service e par VAPID de teste |
| Web Audio além de `tone` (grafo de síntese/análise) | T24 | ➖ não é verificação: é feature futura |

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

## O que falta, e o que exatamente rodar

### captura de câmera real (N4)

Este Chrome (o do harness) respondeu `NotFoundError: Requested device not found` a
`getUserMedia({ video: true })` — não há device nem fake device. Duas saídas:

```bash
# 1) fake device: mede o caminho inteiro sem hardware
chromium \
  --use-fake-device-for-media-stream \
  --use-fake-ui-for-media-stream \
  http://127.0.0.1:8000/

# 2) device real (o que a issue pede de fato)
uv run --frozen tempestweb run --mode server --path examples/photo-capture --port 8000
# abrir num celular na mesma rede, por HTTPS (a câmera exige contexto seguro;
# localhost conta, um IP na LAN não)
```

O que medir: a foto voltando **tipada** ao Python (`Photo` com bytes base64 e
dimensões), o prompt de permissão negado (a app tem de dizer o motivo, não travar),
e `CameraPreview.on_frame` recebendo frames no intervalo declarado.

### Background Sync com a aba fechada (P2)

```bash
uv run --frozen tempestweb run --mode server --path examples/offline-queue --port 8000
```

Procedimento: enfileirar itens offline → **fechar a aba** (não só perder o foco) →
voltar a rede → reabrir e conferir que a fila drenou **uma vez**. O ponto da
medição é a corrida entre o drain do SW e o replay da página: hoje ela é coberta só
por idempotência (double-send seguro), e o que falta saber é se ela acontece.

Precisa de Chrome com `chrome://flags` de Background Sync ativo e de uma rede que
se possa cortar de verdade (o DevTools offline não dispara `sync`).

### WebPush com a aba fechada e `pushsubscriptionchange` (P3)

```bash
uv run --frozen python examples/webpush-server/server.py   # precisa de par VAPID
uv run --frozen tempestweb run --mode server --path examples/pwa-webpush --port 8000
```

O que falta: um par VAPID de teste e um push service alcançável. Medir: notificação
chegando com a **aba fechada**, o clique abrindo o deep link certo, e a rotação de
chave disparando `pushsubscriptionchange` com re-subscribe.

### Web Audio além de `tone` (T24)

Não é verificação pendente: o grafo de síntese/análise (`AudioContext`) está
marcado como **futuro** no roadmap. Sai daqui quando existir.

## Como registrar a próxima medição

1. Rode o procedimento da seção correspondente, sem atalho.
2. Anote **números e strings observadas** — não adjetivos. "Status virou
   `error: permission_denied`" vale; "funcionou" não.
3. Achou defeito? Abra issue própria e linke na
   [#118](https://github.com/mauriciobenjamin700/tempestweb/issues/118).
4. Passou? Suba o item de 🔶 para ✅ no `docs/roadmap.md` **com a data e o que foi
   medido**, e atualize o placar acima. A tabela é o registro.
