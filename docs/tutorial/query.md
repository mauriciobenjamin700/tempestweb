# Lendo dados remotos (`tempestweb.query`)

!!! tip "O que você vai aprender"
    A guardar a resposta de um `GET` com chave, invalidar tudo sobre um recurso
    quando uma mutação entra, paginar, e aplicar uma mudança na tela **antes** de
    o servidor concordar — desfazendo se ele recusar. 🚀

O tempestweb já tinha as duas pontas difíceis do dado remoto:

| Já existia | O que faz |
| --- | --- |
| [`native.http`](../advanced/native-reference.md) | requisição com retry, backoff e idempotência |
| [`native.offline`](../advanced/offline-sync.md) | fila durável de mutações, dead-letter, lane de conflito |
| [`native.sync`](../advanced/offline-sync.md) | delta-sync de coleção grande, por watermark |

Faltava o lado da **leitura**. Sem ele, cada app escrevia um `dict` dentro do
próprio `State` — e a parte que sempre saía errada era a invalidação.

## O problema

```python
# ❌ O cache escrito à mão
if "users-1" not in state.cache:
    state.cache["users-1"] = await fetch_users(page=1)

# ...e depois de renomear um usuário:
del state.cache["users-1"]     # e a página 2? e o detalhe? e o contador?
```

Você precisa de "jogue fora tudo que fala de usuário", e não há a quem
perguntar: ou você mantém um segundo registro de quais chaves significam
usuário, ou limpa o cache inteiro. As duas saídas são o bug.

## Passo 1 — a chave é hierárquica

```python
from tempestweb.query import keys

USERS = keys("users")

USERS.all()            # ('users',)
USERS.list(page=1)     # ('users', 'list', 'page=1')
USERS.detail(7)        # ('users', 'detail', '7')
```

Uma chave é **tupla**, então uma é prefixo da outra por comparação direta. É
isso que torna "invalide tudo sobre usuários" uma pergunta que existe.

!!! note "Ordem de parâmetro não parte o cache"
    `USERS.list(page=1, size=20)` e `USERS.list(size=20, page=1)` são a **mesma**
    chave: os parâmetros são ordenados antes de entrar. Sem isso, a mesma query
    escrita de dois jeitos cacheia duas vezes e a segunda escrita nunca invalida
    a primeira.

## Passo 2 — o primeiro `fetch`

Um programa completo:

```python
from dataclasses import dataclass, field

from tempest_core import App, Column, Text, Widget

from tempestweb import native
from tempestweb.query import OffsetPage, QueryCache, empty_offset_page, keys, offset_page

USERS = keys("users")


@dataclass
class State:
    """O estado da tela."""

    cache: QueryCache = field(default_factory=QueryCache)
    page: OffsetPage = field(default_factory=empty_offset_page)


async def load(app: App[State], page: int) -> None:
    """Carrega uma página, do cache quando ele ainda está fresco."""
    response = await app.state.cache.fetch(
        USERS.list(page=page),
        lambda: native.http.request("GET", f"/api/users?page={page}"),
    )
    app.set_state(lambda s: setattr(s, "page", offset_page(response.json)))


def view(app: App[State]) -> Widget:
    """Desenha as linhas que a página trouxe."""
    return Column(
        key="body",
        children=[
            Text(key=f"row-{index}", content=str(row))
            for index, row in enumerate(app.state.page.items)
        ],
    )
```

Chame `load` duas vezes seguidas e a segunda **não vai à rede**: a resposta
ainda está dentro da janela de frescor (30 s por default).

!!! info "O cache é estado da app, não singleton escondido"
    Repare que `QueryCache` mora no `State`, como qualquer outra coisa. Não
    existe instância de módulo nem contexto implícito: a `view` lê do cache que
    recebeu, e um teste constrói o seu com um relógio falso.

### Duas leituras concorrentes viram uma requisição

```python
import asyncio

await asyncio.gather(
    cache.fetch(USERS.list(), carregar),
    cache.fetch(USERS.list(), carregar),
    cache.fetch(USERS.list(), carregar),
)
# carregar rodou UMA vez
```

Isso é *single-flight*, e é o que uma tela com três widgets lendo a mesma query
precisa. Sem ele, montar a tela dispara três requisições idênticas.

## Passo 3 — invalidar por prefixo

```python
cache.invalidate(USERS.all())    # alcança list(page=1), list(page=2), detail(7)…
```

Uma chamada, um prefixo, tudo que está embaixo. E o **valor continua lá**:

!!! note "Stale não é vazio"
    `invalidate` marca velho e **mantém o valor**, então a tela segue mostrando a
    última resposta boa enquanto o refetch está no ar. A diferença entre isso e
    uma tela que pisca vazia é exatamente essa linha.

    Quando o valor é sabidamente **errado** (e não só velho), use `drop`, que
    remove.

!!! danger "Prefixo é por segmento, nunca por caractere"
    `("users",)` é prefixo de `("users", "list")` e **não** é prefixo de
    `("users-archive",)`. Um `startswith` sobre strings juntadas erra o segundo
    caso — e erra em silêncio, invalidando um recurso que só por acaso divide o
    nome.

## Passo 4 — mudança otimista, e o desfazer

A tela precisa mudar **agora**, não depois do round-trip. E se o servidor
recusar, precisa voltar.

```python
from tempestweb import native
from tempestweb.query import upsert_by_id


async def rename(cache: QueryCache, user_id: int, name: str) -> None:
    """Renomeia na tela primeiro, e desfaz se o servidor recusar."""
    edited = {"id": user_id, "name": name}
    with cache.optimistic(USERS.all(), lambda rows: upsert_by_id(rows, edited)):
        await native.http.request(
            "PATCH", f"/api/users/{user_id}", json={"name": name}
        )
```

Se o `PATCH` levantar, o bloco **restaura exatamente as entradas que
substituiu** — sem rede, sem refetch, e funcionando offline.

!!! warning "Invalidar não é desfazer"
    A saída óbvia — `cache.invalidate(...)` no `except` — é uma ida à rede, não
    um desfazer. Ela deixa a mudança errada na tela até o refetch chegar, e
    offline não faz nada. O rollback é síncrono e exato.

Precisa do controle na mão? `patch` devolve o rollback:

```python
rollback = cache.patch(USERS.all(), lambda rows: upsert_by_id(rows, edited))
try:
    await native.http.request("PATCH", f"/api/users/{user_id}", json=edited)
except Exception:
    rollback()
    raise
```

!!! info "O patch alcança um prefixo, não uma chave"
    Um rename tem que chegar em **toda página cacheada** onde a linha aparece.
    Patchar só `("users", "list", "page=1")` deixa a página 2 mostrando o nome
    velho até algo mais invalidar.

    E é atômico: se o patch levantar no meio, o que já foi aplicado volta. Duas
    entradas mostrando duas verdades diferentes é pior que nenhuma mudança.

## Passo 5 — as duas formas de paginar

```python
from tempestweb.query import cursor_page, is_offset_page, offset_page

if is_offset_page(response.json):
    page = offset_page(response.json)
    page.pages, page.has_next, page.has_previous
else:
    page = cursor_page(response.json)
    page.next_cursor, page.has_next
```

| Forma | Sabe | Custa |
| --- | --- | --- |
| **Offset** (`page` + `total`) | pular para a página 7, mostrar "de 12" | pula ou repete linha se a lista mudar entre páginas |
| **Cursor** (`next_cursor`) | não pular nem repetir | não sabe quantas páginas existem |

!!! note "Página malformada renderiza vazia, não levanta"
    `offset_page({"items": "isso não é lista"})` devolve uma página vazia. Uma
    listagem vazia é recuperável; uma exceção no caminho de renderizar é tela
    branca.

Antes da primeira resposta, use `empty_offset_page()` no estado em vez de
`None` — a `view` nunca precisa checar antes de ler `.items`.

## Passo 6 — sobreviver ao reload

```python
from tempestweb import native
from tempestweb.query import persist, restore

await restore(cache, native.storage)   # no boot
...
await persist(cache, native.storage)   # quando a tela termina
```

O armazenamento é o `native.storage` que já existe, sobre o IndexedDB
owner-scoped do `client/offline/store.js` — **nada foi reimplementado**. O
parâmetro é um `QueryStorage`, que aquele módulo satisfaz como está; um teste
passa um dicionário falso.

!!! warning "Só valor JSON-able persiste"
    Uma entrada guardando um `HttpResponse`, uma dataclass ou um `datetime` não
    vira JSON. O `persist` **pula** essas e reporta quantas pulou, em vez de
    levantar: uma entrada não-serializável não pode impedir as outras nove de
    serem salvas.

Entradas voltam **frescas**. Revivê-las velhas mandaria a tela de boot direto
para a rede, que é justamente o que persistir queria evitar.

## Quando **não** usar isto

!!! info "Não substitui o `native.sync`"
    Delta-sync continua sendo o caminho para reconciliar uma **coleção grande**
    contra um watermark. Este cache é para ler uma tela.

!!! warning "Modo A e Modo B — o Modo C recusa"
    O Modo C transcreve o Python da sua app para JavaScript e serve um conjunto
    fechado de módulos. Importar `tempestweb.query` numa app Modo C é recusado no
    build, com erro nomeado.

## Recap

- `keys("users")` faz chaves **hierárquicas**, e é o que torna a invalidação por
  prefixo possível.
- `cache.fetch(chave, loader)` responde do cache quando fresco, e leituras
  concorrentes da mesma chave viram **uma** requisição.
- `invalidate(prefixo)` marca velho e mantém o valor na tela; `drop(prefixo)`
  remove.
- `optimistic(prefixo, patch)` aplica agora e **desfaz exatamente** se o bloco
  levantar — sem ida à rede.
- `offset_page` / `cursor_page` cobrem as duas formas, e renderizam vazio em vez
  de levantar.
- `persist`/`restore` usam o store que já existe, e só valor JSON-able passa.
