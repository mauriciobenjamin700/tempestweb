# NOTES — #118 storage sobre IndexedDB

Notas da branch `feat/118-storage-idb`. O que está aqui **não** foi implementado:
são pendências medidas, para virarem item da #118 (ou issue própria).

## Pendência 1 — o keyspace do `storage` é por origem, não por owner

**Estado:** aberto. A promessa foi removida da documentação nesta branch; a
capacidade continua sem escopo por owner.

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

## Pendência 3 — `onblocked` do open não é tratado

**Estado:** aberto, consequência conhecida, sem número medido.

`openDb()` fecha em `onsuccess` e em `onerror`. Se um dia o banco subir de versão,
`onblocked` (outra aba com a versão antiga aberta) não resolve nem rejeita: a
promise fica pendurada e a operação de `storage` nunca responde. Hoje é
inalcançável — a versão é `1` e nunca subiu —, então tratar agora seria código
sem teste possível. Vira obrigatório no mesmo commit que subir `DB_VERSION`.
