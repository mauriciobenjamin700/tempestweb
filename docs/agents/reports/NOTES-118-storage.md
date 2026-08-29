# NOTES — #118 storage sobre IndexedDB

Notas da branch `feat/118-storage-idb`. O que está aqui **não** foi implementado:
são pendências medidas, para virarem item da #118 (ou issue própria).

## Pendência 1 — o keyspace do `storage` é por origem, não por owner

**Estado: FECHADA na 0.127.0 (#195).** `storage.configure(owner=...)` escopa o
keyspace; o dono default (`""`) grava a chave crua, então nada do que já está no
disco se move.

A nota supunha que o bloqueio era achar de onde tirar a identidade do dono. Era
mesmo, e a resposta é que **não há** de onde: o Modo A não tem sessão, e o
`session_id` do Modo B identifica um transporte e muda a cada reconexão. O dono
virou parâmetro do app.

O que a nota **não** dizia, e é o dano concreto que a correção fecha:
`tempestweb/query/persistence.py` restaura o cache percorrendo `list_keys()`, então
o boot de um usuário enchia o `QueryCache` com respostas de API persistidas por
outro no mesmo device. Isso saiu de graça, sem uma linha em `query/`.

Quatro docstrings e um typedef prometiam "the owner-scoped store from
`client/offline/store.js` (T9/P2)":

- `tempestweb/native/storage.py` (docstring de módulo + `put`/`get`/`remove`)
- `client/native/storage.js` (cabeçalho)
- `client/native/index.js` (typedef `NativeDeps.store`)
- `tempestweb/query/persistence.py` e `docs/tutorial/query.md`/`.en.md`, que
  repetiam a mesma frase sobre o mesmo store

Nenhum caminho injetava aquele store. O que `browserDeps()` injeta é o
`createIdbKv()` — banco `tempestweb`, object store `kv`, **chave igual ao nome
cru** que o app passou. Logo:

- dois owners na mesma origem (Modo B, dois logins no mesmo device) compartilham
  um keyspace: a chave que um grava o outro lê e sobrescreve;
- `storage.list_keys()` devolve as chaves de **todos** os owners;
- `remove()` de um alcança o dado do outro.

Mitigação hoje: prefixar a chave no app (`f"{user_id}:notes"`).

**Por que não foi feito aqui:** derivar chave por owner exige uma identidade de
owner que o Modo A não define (não há sessão, não há login do lado do servidor).
Escolher de onde essa identidade vem — parâmetro de `configure`, sessão do Modo
B, algo do app — é decisão de design, não fix de review. Além disso, ligar o
escopo depois quebra dado já gravado: as chaves existentes deixam de ser
encontradas, então junto vem uma migração (mesma forma da nota de migração da
0.123.0 no `CHANGELOG.md`).

`docs/plan.md:617` ainda descreve o desenho original (`storage` = a API do store
owner-scoped do P2). Ficou como está de propósito: é o plano, e esta nota é o
registro de que o entregue diverge dele.

## Pendência 2 — candidata a issue: um `indexedDB.open()` por operação

**Estado:** aberto, com número medido. Não implementado nesta branch.

`client/native/idb-kv.js` abre e fecha o banco em cada operação. Medido com um
`IDBFactory` instrumentado (store construído **uma vez**, 5 `put` + 5 `get`):

```text
store built once; 10 operations -> 10 indexedDB.open() calls
```

O cache de `_kvStore` em `browserDeps()` evita realocar o objeto do store, e
nada além disso — a JSDoc que prometia economia de open foi corrigida nesta
branch, porque prometia o que não entrega.

**Por que não foi resolvido aqui:** a correção óbvia é segurar a conexão aberta,
e conexão viva bloqueia `versionchange` (outra aba que suba uma versão nova fica
presa no `onblocked`) e muda o ciclo de vida do store — risco novo dentro de um
PR que é só fix. Se virar issue, o desenho precisa cobrir: `onversionchange` →
`db.close()`, reabertura preguiçosa depois disso, e o que acontece com uma
transação em vôo no meio da troca.

Ordem de grandeza antes de priorizar: o open é o custo dominante só em rajada de
operações pequenas; para o caso que a #118 mediu (um valor de 142.890
caracteres) o open desaparece ao lado do encode e da escrita.

**Atualização: FECHADA na 0.127.0 (#195).** A conexão passou a ser aberta uma vez
e reusada, com single-flight. Medido com um `IDBFactory` que conta: **10 operações
→ 1 open**, e 8 escritas concorrentes → **1 open**.

Os três itens que o desenho pedia estão cobertos: `onversionchange` → `db.close()`
(entregue pela pendência 3), reabertura preguiçosa na chamada seguinte, e a
transação em vôo — medido que `db.close()` **não** aborta transação já aberta, a
escrita ainda commita. Somou-se um retry único em `InvalidStateError`, para o
caller que pegou a conexão microssegundos antes de ela fechar.

Duas coisas apareceram só ao reusar, e as duas viraram correção no mesmo commit:

1. **`forgetKvStore()` vazava a conexão.** Ele largava a referência do store sem
   fechar; com conexão retida isso deixaria uma conexão viva e inalcançável —
   e conexão aberta é o que bloqueia upgrade. O store ganhou `close()`.
2. **`VersionError` degradava para `localStorage`.** A reabertura pós-upgrade é
   um caminho normal agora, e o build antigo pedindo a versão que conhece recebia
   `VersionError` → `StoreUnavailableError` → degrade permanente, partindo o dado
   do app entre dois backends. Ganhou código próprio, `stale`.

A nota anterior deste arquivo já apontava o risco do `VersionError`; ele saiu de
"vale uma linha quando o bump vier" para corrigido, porque o reuso o pôs no
caminho quente.

## Pendência 3 — `onblocked` do open não é tratado

**Estado: FECHADA na 0.127.0 (#195).**

`openDb()` fechava em `onsuccess` e em `onerror`. Se o banco subisse de versão,
`onblocked` não resolvia nem rejeitava: a promise ficava pendurada e a operação de
`storage` nunca respondia.

**A nota original errou em dois pontos, e vale registrar quais.**

Primeiro, "hoje é inalcançável, tratar agora seria código sem teste possível"
estava errado: `fake-indexeddb` já está no `devDependencies` e roteiriza a
sequência inteira. `tests/client/native-idb-blocked.test.js` são 8 casos, sem
subir versão de banco nenhuma.

Segundo, e mais importante, "vira obrigatório no mesmo commit que subir
`DB_VERSION`" estava exatamente ao contrário. O `onversionchange` é o handler que
faz a aba **antiga** soltar a conexão, então ele precisa estar no build **já
implantado** quando alguém sobe a versão — entregá-lo junto do bump é entregá-lo
uma release tarde demais.

E medindo apareceu um terceiro fato que o desenho da nota não cobria: a aba que
apenas **usa** o banco enquanto outra faz upgrade **não recebe evento nenhum** —
nem `blocked`, nem `success`, nem `error`. Fica enfileirada em silêncio. Um prazo
armado dentro do `onblocked` salvaria só quem faz o upgrade e deixaria toda
espectadora pendurada, que é o caso comum. Por isso o prazo (`OPEN_TIMEOUT_MS`)
cobre todo open, e conexão que chega depois dele é fechada — segurá-la deixaria
uma conexão inalcançável na versão antiga, bloqueando o upgrade seguinte.
