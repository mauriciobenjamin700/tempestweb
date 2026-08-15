# Quando dá errado

!!! abstract "Como usar esta página"
    Cada entrada começa pela **mensagem literal** que aparece no terminal ou no
    console, ou pelo **sintoma** quando não há mensagem nenhuma. Se você chegou
    aqui com um erro na tela, cole um pedaço dele na busca do site (a lupa no
    topo) — a entrada certa aparece.

    As mensagens desta página são verificadas contra o código-fonte por um teste
    automatizado, então elas não envelhecem em silêncio.

---

## Falta um extra

De longe a categoria mais comum, e a mais fácil de resolver: o tempestweb
instala **enxuto**. Cada capacidade pesada mora num extra, e a mensagem sempre
diz qual.

| Mensagem contém | Instale |
|---|---|
| `serving Mode B needs the 'server' extra (FastAPI + uvicorn)` | `pip install "tempestweb[server]"` |
| `the dev server needs the 'server' extra` | `pip install "tempestweb[server]"` |
| `the dev watcher needs watchfiles` | `pip install "tempestweb[cli]"` |
| `tomlkit is required for` `tempestweb sync` | `pip install "tempestweb[cli]"` |
| `PyJWT is required for verify_jwt` | `pip install "tempestweb[auth]"` |
| `redis is required for RedisSessionRouter` | `pip install "tempestweb[server]"` + redis |
| `pywebpush is required to send WebPush` | `pip install "tempestweb[webpush]"` |
| `cryptography is required to generate VAPID keys` | `pip install "tempestweb[webpush]"` |
| `FastAPI is required for webpush_router` | `pip install "tempestweb[server]"` |

!!! tip "Na dúvida, leia a própria mensagem"
    Toda mensagem dessa família termina com o comando exato. Elas foram escritas
    para serem a documentação — não é preciso procurar em lugar nenhum.

---

## Capacidades nativas

### `no native bridge installed (off-platform, or bootstrap incomplete)`

```text
no native bridge installed (off-platform, or bootstrap incomplete)
```

Um `await native.<capacidade>()` rodou onde não existe browser do outro lado da
ponte. Três causas, em ordem de frequência:

1. **Você está num teste ou num script**, fora de uma sessão. Não há browser —
   injete um duplo, ou mova a chamada para dentro de um handler.
2. **O bootstrap do Modo A não completou.** O `bootstrap.js` gerado instala a
   ponte antes de chamar o `bootstrap()` Python; se a página quebrou antes
   disso, o erro aparece na primeira interação.
3. **A sessão do Modo B foi fechada** e um handler ainda em voo tentou usar a
   ponte.

Referência: [Capacidades nativas](advanced/capabilities.md).

### `the installed native bridge does not support the event channel`

```text
the installed native bridge does not support the event channel
```

Você chamou um `watch()` / `listen()` (geolocalização contínua, rede, sensores)
numa ponte que só resolve chamadas de uma vez. No Modo A isso acontece quando o
`bootstrap()` recebeu `dispatch` mas não recebeu `subscribe`/`unsubscribe` — o
que dá esta variante mais específica:

```text
mode A native event channel is not wired (no subscribe callable)
```

O `bootstrap.js` gerado pelo `tempestweb build` passa os três. Se você monta o
bootstrap à mão, passe também os dois de streaming.

Referência: [Canal de eventos nativo](advanced/native-events.md).

---

## Sessão e handlers

### A interface travou — nenhum botão responde

Sem erro nenhum, a tela simplesmente para. A sessão despacha **um evento por
vez**: enquanto um handler roda, nada mais é lido. Um `await` demorado dentro do
handler — inferência de modelo, API externa lenta, arquivo grande — congela a
conexão inteira daquele usuário, e nem um "Cancelar" adianta (o clique entra na
fila **atrás** do trabalho que deveria interromper).

Tire o trabalho do handler com `spawn`:

```python
from tempestweb.runtime import spawn


async def analisar(app: App[State]) -> None:
    app.set_state(lambda s: setattr(s, "status", "processando…"))

    async def trabalho() -> None:
        resultado = await algo_demorado()
        app.set_state(lambda s: setattr(s, "resultado", resultado))

    spawn(trabalho())
```

Referência: [Trabalho longo: o dispatch é serial](tutorial/best-practices.md#trabalho-longo-o-dispatch-e-serial).

### `spawn() needs a running tempestweb session`

```text
spawn() needs a running tempestweb session; call it from an event handler, or await the coroutine directly
```

`spawn` pendura a task na sessão que está no contexto, e não há sessão nenhuma
no contexto de onde você chamou — tipicamente um teste, um script, ou código de
módulo que roda no import. Dentro de um handler sempre há. Fora dele, só
`await` a corrotina direto.

### O handler roda, mas a tela não muda

Sem erro. Quase sempre é mutação de estado **fora** de um `set_state`:

```python
# ❌ o estado muda, mas nada reconstrói a árvore
async def marcar(app: App[State]) -> None:
    app.state.feito = True

# ✅
async def marcar(app: App[State]) -> None:
    app.set_state(lambda s: setattr(s, "feito", True))
```

O repaint é agendado pelo `set_state`, não pela mudança do objeto.

---

## Build e Modo C

### `TranspileError` com `file:line`

O compilador do Modo C aceita um subconjunto de Python tipado, e recusa cedo com
a linha exata. Os mais frequentes:

```text
plain `import x` is not supported; use `from ... import ...`
```

```text
variadic parameters (*args / **kwargs) are not supported
```

```text
function decorators are not supported
```

E o que mais aparece ao portar um app já pronto:

```text
is not supported (only tempest_core and `tempestweb.native`)
```

O Modo C só enxerga `tempest_core` e `tempestweb.native`. Isso inclui
`tempestweb.presets` e `tempestweb.components` — telas montadas com presets
rodam nos Modos A e B, não em C.

Referência: [Modo C — transpile](advanced/transpile.md).

### O app carrega com a versão **antiga** do código

Nenhum erro, nenhum aviso: você reconstruiu, recarregou, e a correção não está
lá. É o **service worker**.

Por decisão de projeto o worker não chama `skipWaiting` — quem controla a
atualização é a página, com um prompt para o usuário. A consequência em
desenvolvimento é que, depois de um `build`, o worker novo instala mas fica
**esperando**, e o antigo continua servindo o app-shell do cache dele. Um F5
comum não troca: a aba segue controlada pelo worker velho.

Diagnóstico e correção, no Chrome DevTools → **Application** → **Service
Workers**:

1. Se aparecer um worker com o rótulo **waiting to activate**, é isso.
2. Marque **Update on reload** enquanto estiver desenvolvendo — cada reload
   passa a ativar o worker novo.
3. Para limpar de vez: **Unregister**, e em **Application → Storage** use
   **Clear site data**, então recarregue.

Em produção o caminho é o outro: a página detecta o worker esperando e oferece o
prompt de atualização, que envia `{type:"SKIP_WAITING"}`.

Referência: [PWA e offline](advanced/pwa.md).

---

## Conexão (Modo B)

### `websocket disconnected` / `sse transport is closed`

```text
websocket disconnected
```

```text
sse transport is closed
```

O cliente sumiu (aba fechada, rede caiu, proxy cortou) e algo tentou escrever no
transporte depois disso. Como erro de servidor é esperado e não exige ação. Se
acontece o tempo todo em produção com usuários ativos, olhe o **reverse proxy**:
timeout de idle curto ou falta do upgrade de WebSocket derruba conexões
saudáveis.

Se a sua infraestrutura simplesmente não deixa WebSocket passar, troque o shell
por SSE — está em [Deploy](advanced/deploy.md#infra-que-bloqueia-websocket-troque-o-shell-por-sse).

### O editor não completa nada de `tempestweb`

O mypy trata tudo como `Any` e o autocomplete não sugere nada. Isso é sintoma de
uma versão **anterior à 0.64.0**, que não trazia o marcador `py.typed` — sem
ele, a PEP 561 manda o verificador ignorar os tipos, por mais anotado que o
pacote esteja.

```bash
pip install --upgrade tempestweb
```

---

## Desenvolvendo o tempestweb

### `MODULE_NOT_FOUND` ao rodar os testes de cliente

A forma com diretório quebra no Node 24+:

```bash
node --test tests/client/        # ❌ MODULE_NOT_FOUND
node --test "tests/client/*.test.js"   # ✅
```

Use sempre o glob, entre aspas para o shell não expandir antes.

---

## Recapitulando

- **Mensagem de extra faltando** já contém o comando — leia-a antes de procurar
  aqui.
- **Ponte nativa ausente** significa "não há browser deste lado": teste, script
  ou bootstrap incompleto.
- **Interface travada sem erro** é o dispatch serial; a resposta é `spawn`.
- **Tela que não muda** é mutação sem `set_state`.
- **Código velho depois do build** é o service worker esperando; ligue *Update
  on reload* durante o desenvolvimento.
- **Não achou aqui?** Veja o [FAQ](faq.md) ou
  [abra uma issue](https://github.com/mauriciobenjamin700/tempestweb/issues).
