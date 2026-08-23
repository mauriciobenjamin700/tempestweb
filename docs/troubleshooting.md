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
is not available in Mode C
```

`import x` funciona para os módulos que o Modo C serve (`re`, `json`, `math`,
`base64`, `asyncio`) e para nada além disso — a mensagem de um módulo recusado
**diz o que fazer no lugar** (`datetime` → formate no estado e passe a string).

```text
variadic parameters (*args / **kwargs) are not supported
```

```text
function decorators are not supported
```

E o que mais aparece ao portar um app já pronto:

```text
is not supported (only tempest_core, `tempestweb.components` and `tempestweb.native`)
```

O Modo C enxerga `tempest_core`, `tempestweb.components` e `tempestweb.native`
— este último nas três formas: `from tempestweb import native`,
`from tempestweb.native import storage` e
`from tempestweb.native.geolocation import get_position`. Já `import
tempestweb.native` não: a mensagem diz qual forma escrever no lugar.
Import de stdlib **só de anotação** (`collections.abc`, `typing`) também passa: o
nome existe para o type-checker e não custa import nenhum no JS — mas usá-lo como
**valor** é erro (`'Any' is a type-only name`), porque nada o importaria.

Fora dessa lista, `tempestweb.presets` e `tempestweb.observability` não são
alcançáveis: telas montadas com presets rodam nos Modos A e B, não em C.

Capacidade nativa que o Modo C não tem em processo (`camera`) é recusada
dizendo **qual modo a tem**:

```text
`camera` is not served in Mode C: the facade in `native.js` has no `camera`,
so the capability needs Mode A (Pyodide) or Mode B (server)
```

Nome legal em módulo legal ainda pode faltar no cliente — aí o erro cita o
**nome**, não o módulo:

```text
is not available in Mode C (the transpile client exports no such name)
```

Referência: [Modo C — transpile](advanced/transpile.md).

### `object is not iterable` ou `X.pop is not a function` (Modo C)

Um clique morre no console e a tela não muda. É um **dict** sendo tratado como
lista.

- **`dict(outro)`** compilava para `Object.fromEntries(outro)`, que exige um
  iterável de pares e explode num mapeamento. O compilador não sabe qual dos dois
  você tem — `dict(pares)` também é legítimo — então desde 0.93.0 a decisão é em
  runtime.
- **`d.pop(chave, default)`** caía no `pop` de array, que num objeto não existe.

Medidos no `examples/form`, cujo submit morria seis vezes por clique com a página
renderizada e o formulário inerte.

---

### `_pattern.match is not a function` (Modo C)

O validador com `re.compile(...)` morre, mas o mesmo código com atribuição sem
anotação funciona.

O compilador rastreia qual nome guarda um padrão compilado — é isso que deixa
`.match()` virar o helper certo sem sequestrar um `.match()` alheio — mas só
rastreava a forma **sem** anotação. `_pattern: re.Pattern[str] = re.compile(…)`,
que é a forma que as regras de estilo deste repo pedem, perdia o rastro e emitia
`.match` cru num `RegExp`, que não tem esse método. Corrigido em 0.93.0; vale
também para `form: Form = Form(…)`.

---

### `c.isupper is not a function` (Modo C)

A tabela de predicados de `str` do Modo C tinha `isdigit`/`isalpha`/`isalnum`/
`isspace` e faltavam os de caixa. Adicionados em 0.93.0, com a semântica do
Python: exige ao menos um caractere com caixa, então `"1".isupper()` é `False`.

---

### `Theme.from_seed is not a function` (Modo C)

Página em branco, um erro só no console, e o build tinha passado.

`_served.py` responde "o cliente exporta esse nome?" — não responde "esse nome
tem esse método?". `Theme` **é** servido (o do Modo C carrega o modo), mas a
paleta Material 3 semeada não é portada: quem pinta os tokens é a folha de
estilo base.

Desde 0.92.0 isso é **erro de compilação** com `arquivo:linha`:

```text
the client's own object carries no such member
```

O manifesto de membros (`tempestweb/transpile/_members.py`) é gerado
introspectando o cliente no Node, que é a única fonte honesta — o JS é o que o
browser carrega. `Color.from_hex`, `Edge.all` e `Edge.symmetric` continuam
passando, porque esses o cliente carrega de verdade.

---

### `Invalid left-hand side in assignment` (Modo C)

Um clique não faz nada e o console mostra isso. É `xs[:] = [...]`.

Uma fatia **lê** como `.slice(...)`, então a atribuição saía
`xs.slice(0) = [...]` — que *parseia*, e por isso o `node --check` do build
passava. Corrigido em 0.92.0: vira `xs.splice(0, xs.length, ...novo)`, que é a
substituição no lugar que o Python faz. Fatia parcial (`xs[1:3] = …`) é recusada
no build, porque ela pode crescer ou encolher a lista.

---

### O `on_change` do componente não dispara (Modo C)

O componente aparece, o texto que você digita fica na caixa, e o handler nunca
roda — clicar em "Entrar" não faz nada.

Os props de widget viajam em `camelCase` no builder gerado (`on_submit` vira
`onSubmit`), e a renomeação era decidida resolvendo o nome no `tempest_core`.
Um componente que só existe no facade — `LoginForm`, `SignupForm`, `TextField`,
`EmailField`, `PasswordField` — não resolvia lá, então os props saíam no
`snake_case` do fio e o builder, que desestrutura `camelCase`, descartava
**todos os handlers em silêncio**.

Corrigido em 0.90.0 — o nome é procurado no `tempest_core` e depois em
`tempestweb.components`. Como efeito colateral bom, o kwarg desconhecido volta
a ser recusado no build: `LoginForm(subtitle="x")` agora falha com
`arquivo:linha`.

```bash
uv add "tempestweb>=0.90.0"
```

---

### `Color.from_hex is not a function` / `Class constructor X cannot be invoked without 'new'`

Página em branco, um erro só no console, e o build tinha passado.

- **`Color.from_hex`**: no core, `Color` é um modelo com o classmethod
  `from_hex` — o jeito de escrever cor literal (65 chamadas nos exemplos). O
  Modo C exportava só a fábrica, então a chamada compilava e morria na
  montagem. Portado em 0.90.0.
- **`field(default_factory=OutraDataclass)`**: dataclass compila para classe
  JS, e chamar classe sem `new` é `TypeError` duro. O default aninhado saía
  `(Address)()` e o app morria no primeiro `makeState()`. Corrigido em 0.90.0.

Os dois são a mesma família do `Edge` que não era chamável (0.86.0): valor do
core cujo helper faltava no cliente. O guard de build roda `node --check`, que
faz *parse* sem executar — por isso passavam.

---

### O campo com mensagem de erro não fica vermelho (Modo C)

O `Input` mostra a mensagem embaixo, mas a borda e o texto continuam na cor
normal — em Modo A ou B, o mesmo código pinta os dois de vermelho.

Um campo com `error` preenchido está **inválido**, e o core repinta a borda e o
texto no papel `error` **na hora de construir**. Essa regra mora no estilo
construído, não na folha de estilo, então o builder do Modo C, que é
passthrough, a perdia em silêncio: o campo compilava, montava e mentia.

Corrigido em 0.88.0 — `Input` resolve por `resolveFieldStyle`, que aplica a
regra do core (borda de 1px no papel `error`, `SideBorder` só embaixo quando o
`field_variant` é `flushed`, e o `style` do chamador ainda ganha por último).

Se você vê isso, atualize o pacote:

```bash
uv add "tempestweb>=0.88.0"
```

---

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
