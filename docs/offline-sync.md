# Offline + sincronização com backend

!!! abstract "O que você vai aprender"
    Como ligar a **fila offline** do tempestweb (cliente) a um **backend FastAPI
    feito com o [`tempest-fastapi-sdk`](https://pypi.org/project/tempest-fastapi-sdk/)**
    para ter um app **offline-first de ponta a ponta**: o app enfileira mutações
    localmente quando não há rede e **sincroniza** quando a conexão volta — sem
    aplicar nada duas vezes. 🚀

A página [PWA e offline](pwa.md) mostra a fila offline **do lado do cliente**
(service worker, IndexedDB, `native.offline`). Aqui fechamos o círculo: o outro
lado da mutação é um **servidor real** que recebe, persiste e deduplica os
replays. Nada de novo no seu `view()` — só um endpoint bem construído do outro
lado. ✅

---

## Por que offline-first

Um app tradicional escreve direto na rede: sem rede, a escrita **falha** e o
usuário perde o que digitou. Offline-first inverte isso:

1. **Enfileira local primeiro.** Toda mutação vai para uma fila durável no
   IndexedDB — a escrita "dá certo" na hora, mesmo sem rede.
2. **Sincroniza ao voltar a rede.** Quando a conexão volta (evento `online`,
   Background Sync ou replay explícito), a fila é drenada em ordem **FIFO** contra
   o backend.
3. **Nunca aplica duas vezes.** Cada mutação carrega uma **chave de idempotência**;
   o servidor deduplica, então reenviar uma mutação já aplicada é inofensivo.

!!! info "Duas direções, dois mecanismos"
    - **Push (escrita)** — o app → servidor. É o que a fila `native.offline` faz por
      você: enfileira, replay, idempotência.
    - **Pull (leitura)** — o servidor → app. Não há fila para isso; é um padrão de
      **delta-sync** que você monta com `native.http` + o filtro `updated_at__gt`
      do repositório. Cobrimos os dois abaixo.

---

## Arquitetura

```text
┌──────────────────────── Browser (app tempestweb) ─────────────────────────┐
│                                                                            │
│  view()  ──enqueue──►  native.offline  ──►  OfflineQueue  ──►  IndexedDB   │
│  (Python)              (escrita durável)    (FIFO + chave)    (tempestweb- │
│                                                                offline /   │
│                                                                mutations)  │
│                                                                            │
│  online / Background Sync / replay()  ──drena FIFO──►  fetch               │
│                                                         header:            │
│                                                         idempotency-key    │
└─────────────────────────────────────────────────────────────┬────────────┘
                                                               │  HTTPS
                                                               ▼
┌──────────────── Backend (FastAPI + tempest-fastapi-sdk) ───────────────────┐
│                                                                            │
│  IdempotencyMiddleware  ──(method, path, key)──►  store (Memory | Redis)   │
│       │ 1ª vez                        │ retry / replay → resposta em cache │
│       ▼                               ▼                                    │
│  router  ──►  BaseRepository.add()  ──►  Postgres / SQLite                 │
│               (id, created_at, updated_at automáticos)                     │
│                                                                            │
│  pull:  GET /api/notes?since=<ts>  ──►  repo.list({"updated_at__gt": ts})  │
└────────────────────────────────────────────────────────────────────────────┘
```

O ponto de encontro é a **chave de idempotência**: o cliente a envia no header, o
`IdempotencyMiddleware` do SDK a usa para cachear a resposta por
`(método, caminho, chave)`. Um replay repetido devolve a **resposta cacheada** —
zero linha duplicada no banco.

!!! note "Backend separado, de propósito"
    O backend é um **serviço FastAPI próprio** (o mesmo que você já teria com o
    SDK). Ele não precisa saber que o cliente é um app tempestweb — recebe um
    `POST`/`PUT` normal com um header de idempotência. Isso vale para os três modos
    de execução do tempestweb (WASM, servidor, transpile).

---

## Parte A — Enfileirar mutações no app tempestweb

A capacidade `native.offline` é a API real do cliente. Você enfileira uma mutação
em vez de bater na rede diretamente:

```python
from tempestweb import native


async def save_note(text: str) -> None:
    """Enfileira a criação de uma nota (sobrevive a estar offline)."""
    await native.offline.enqueue("POST", "/api/notes", {"text": text})
```

A assinatura completa:

```python
await native.offline.enqueue(
    method,                 # "POST" | "PUT" | "PATCH" | "DELETE"
    url,                    # o endpoint do seu backend
    body=None,              # corpo JSON-able
    *,
    idempotency_key=None,   # gerada automaticamente quando omitida
    owner=None,             # escopo opcional (ex.: por usuário)
)
```

O retorno é uma `Mutation` (`id`, `owner`, `idempotency_key`, `method`, `url`,
`attempts`, `status`). O `status` é `"pending"` até drenar; uma mutação que falha
de forma permanente vira `"failed"` (dead-letter) e um conflito `409` vira
`"conflict"` — nenhum dos dois trava a fila. Você também pode **inspecionar** e
**drenar** a fila:

| Chamada | Faz | Retorna |
|---|---|---|
| `native.offline.enqueue(...)` | Enfileira uma mutação durável. | `Mutation` |
| `native.offline.pending(owner=None)` | Lista as pendentes, mais antigas primeiro. | `list[Mutation]` |
| `native.offline.size(owner=None)` | Conta as pendentes. | `int` |
| `native.offline.replay(owner=None)` | Drena a fila **agora** (FIFO). | `ReplayResult(sent, remaining, failed, conflicts)` |
| `native.offline.failed(owner=None)` | Lista as mutações **dead-lettered** (falha permanente / tentativas esgotadas). | `list[Mutation]` |
| `native.offline.conflicts(owner=None)` | Lista as mutações paradas na **lane de conflito** (servidor devolveu `409`). | `list[Mutation]` |

### O app completo

Um "log de atividade" mínimo: digitar e apertar **Enfileirar** grava na fila; o
contador vem de `size()`; **Sincronizar** dispara o replay (que o runtime também
faz sozinho ao voltar a rede). Este é o [`examples/offline-queue/app.py`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/offline-queue/app.py):

```python
from __future__ import annotations

from dataclasses import dataclass, field

from tempest_core import App, Style, Widget
from tempest_core.style import Edge
from tempest_core.widgets import Button, Column, Input, Row, Text
from tempest_core.widgets.events import TextChangeEvent
from tempestweb import native


@dataclass
class QueueState:
    """Estado do demo de fila offline."""

    draft: str = ""
    queued: int = 0
    status: str = ""
    log: list[str] = field(default_factory=list)


def make_state() -> QueueState:
    """Estado inicial."""
    return QueueState()


def view(app: App[QueueState]) -> Widget:
    """Input + contador de pendentes + controle de replay."""

    def on_draft(event: TextChangeEvent) -> None:
        value = event.value
        app.set_state(lambda s: setattr(s, "draft", value))

    async def queue_note() -> None:
        text = app.state.draft
        await native.offline.enqueue("POST", "/api/notes", {"text": text})  # (1)!
        size = await native.offline.size()

        def _update(s: QueueState) -> None:
            s.queued = size
            s.draft = ""
            s.log = [*s.log, text]
            s.status = f"enfileirado: {text}"

        app.set_state(_update)

    async def sync_now() -> None:
        result = await native.offline.replay()  # (2)!

        def _update(s: QueueState) -> None:
            s.queued = result.remaining
            s.status = f"enviadas {result.sent}, faltam {result.remaining}"

        app.set_state(_update)

    return Column(
        style=Style(gap=10.0, padding=Edge.all(16)),
        children=[
            Text(content=f"Pendentes: {app.state.queued}", key="pending"),
            Row(
                style=Style(gap=6.0),
                children=[
                    Input(
                        value=app.state.draft,
                        placeholder="uma nota para sincronizar",
                        on_change=on_draft,
                        key="draft",
                    ),
                    Button(label="Enfileirar", on_click=queue_note, key="queue"),
                    Button(label="Sincronizar", on_click=sync_now, key="replay"),
                ],
            ),
            Text(content=app.state.status, key="status"),
        ],
    )
```

1.  Enfileira em vez de dar `fetch`. Funciona **sem rede** — a escrita vai para o
    IndexedDB.
2.  Drena a fila agora. O runtime **também** faz isso sozinho quando a conexão
    volta (evento `online` + Background Sync), então este botão é opcional.

!!! tip "A chave de idempotência é automática"
    Você não precisa gerar a chave: quando você omite `idempotency_key`, a fila
    gera uma estável e a envia no header `idempotency-key` a cada replay. É essa
    chave que o backend usa para não aplicar a mesma escrita duas vezes.

---

## Parte B — O endpoint de sync no backend com o SDK

Do outro lado, um serviço FastAPI construído com o `tempest-fastapi-sdk`. Três
peças: o **modelo**, os **schemas** e o **endpoint** — mais o
`IdempotencyMiddleware` que faz o replay ser seguro.

```bash
uv add "tempest-fastapi-sdk[cache]"   # [cache] só se for usar o store Redis
```

### O modelo e os schemas

O `BaseModel` do SDK já traz `id` (UUID), `is_active`, `created_at` e
`updated_at` — este último **atualizado automaticamente** a cada `UPDATE`, o que
é exatamente o que o delta-sync (Parte E) precisa.

```python
from sqlalchemy.orm import Mapped, mapped_column
from tempest_fastapi_sdk import BaseModel, BaseResponseSchema, BaseSchema


class NoteModel(BaseModel):
    """Uma nota persistida."""

    __tablename__ = "notes"

    text: Mapped[str] = mapped_column()


class NoteCreateSchema(BaseSchema):
    """Corpo de criação de nota (o que o cliente enfileira)."""

    text: str


class NoteResponseSchema(BaseResponseSchema):
    """Resposta de nota — herda id/is_active/created_at/updated_at."""

    text: str
```

!!! info "`BaseRepository` sem subclasse"
    Para CRUD simples você **instancia o `BaseRepository` direto**:
    `BaseRepository(session, model=NoteModel)`. Ele expõe `add()`, `list()`,
    `get_by_id()`, `update()`, `delete()` e mais. Só faça uma subclasse quando
    precisar de queries próprias.

### O app FastAPI

```python
from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession
from tempest_fastapi_sdk import (
    AsyncDatabaseManager,
    BaseRepository,
    IdempotencyMiddleware,
    MemoryIdempotencyStore,
    register_exception_handlers,
)

db = AsyncDatabaseManager("sqlite+aiosqlite:///./notes.db")
app = FastAPI(title="notes-backend")

# Deduplica replays: um POST repetido com a mesma Idempotency-Key devolve a
# resposta cacheada — nenhuma linha duplicada.
app.add_middleware(
    IdempotencyMiddleware,
    store=MemoryIdempotencyStore(),   # troque por RedisIdempotencyStore em multi-réplica
    ttl_seconds=24 * 3600,
)
register_exception_handlers(app)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Uma sessão async por request."""
    async for session in db.session_dependency():
        yield session


@app.on_event("startup")
async def _startup() -> None:
    """Cria as tabelas no boot (em produção use migrations)."""
    await db.create_tables()


@app.post("/api/notes", response_model=NoteResponseSchema, status_code=201)
async def create_note(
    data: NoteCreateSchema,
    session: AsyncSession = Depends(get_session),
) -> NoteResponseSchema:
    """Persiste uma nota. Idempotente via header Idempotency-Key."""
    repo = BaseRepository(session, model=NoteModel)
    note = await repo.add(NoteModel(text=data.text))
    return NoteResponseSchema.model_validate(note)
```

!!! success "Como a idempotência se conecta ponta a ponta"
    O `native.offline` replay envia o header `idempotency-key`; o
    `IdempotencyMiddleware` lê `Idempotency-Key` — e headers HTTP são
    **case-insensitive**, então os dois casam sem você fazer nada. O middleware só
    age em `POST`/`PUT`/`PATCH`/`DELETE` e **só** quando o header está presente;
    requests sem chave passam direto.

---

## Parte C — Replay e confirmação ao voltar online

O replay é **responsabilidade do runtime do cliente** — o SDK não impõe protocolo
de sync. O tempestweb drena a fila em três gatilhos:

- **Evento `online`.** Assim que o browser reporta conectividade, a fila é
  drenada (aba aberta).
- **Background Sync.** Onde o navegador suporta (Chromium), o service worker
  drena a fila **mesmo com a aba fechada**.
- **Explícito.** O seu app chama `await native.offline.replay()` quando quiser
  (ex.: um botão "Sincronizar" ou ao abrir a tela).

O replay é **FIFO** e classifica cada falha, sem deixar a fila travar:

- **Falha transitória** (erro de rede, `5xx`, `408`/`425`/`429`): a mutação fica
  pendente (com `attempts` incrementado) e o replay **para** ali, preservando a
  ordem. Depois de `maxAttempts` tentativas (default 5) ela é **dead-lettered**
  (`status="failed"`) e o replay segue drenando o resto.
- **Erro permanente** (`4xx` não-retentável, ex.: `400`/`422`): dead-letter
  **na primeira tentativa** — não adianta reenviar um corpo que o servidor sempre
  rejeita, então ele não bloqueia a fila.
- **Conflito** (`409`): a mutação vai pra **lane de conflito** (`status="conflict"`)
  para você reconciliar (Parte D); também não bloqueia.

Assim uma única "poison message" nunca prende todas as escritas atrás dela. O
`ReplayResult` te diz o resultado (`sent`, `remaining`, `failed`, `conflicts`):

```python
from tempestweb import native


async def sync_and_report() -> str:
    """Drena a fila e devolve uma linha de status legível."""
    result = await native.offline.replay()
    if result.remaining == 0:
        return f"tudo sincronizado ({result.sent} enviadas)"
    return f"enviadas {result.sent}, {result.remaining} ainda pendentes"
```

!!! warning "O replay não devolve o recurso criado ao app"
    `replay()` retorna apenas **contagens** (`sent` / `remaining`), não os corpos
    de resposta do servidor. Ou seja, o app não recebe de volta o `id`/`created_at`
    da nota criada por uma mutação enfileirada. Se você precisa desses dados no
    cliente, **releia** do servidor com um pull (Parte E) depois do replay — é o
    padrão canônico offline-first (escreve otimista, reconcilia relendo).

---

## Parte D — Idempotência e conflito

### Idempotência (resolvido)

O `IdempotencyMiddleware` cacheia a resposta por `(método, caminho, chave)`. Um
replay com a mesma chave devolve o **mesmo** resultado — nunca insere duas vezes.
É o padrão de Stripe/AWS/GitHub, e é o que torna o replay seguro por construção.

!!! danger "Escolha o store certo em produção"
    O `MemoryIdempotencyStore` é **por processo** — em multi-réplica uma réplica
    não vê a chave cacheada por outra, e o replay pode duplicar. Com mais de uma
    réplica use o `RedisIdempotencyStore`:

    ```python
    from redis.asyncio import Redis
    from tempest_fastapi_sdk import IdempotencyMiddleware, RedisIdempotencyStore

    app.add_middleware(
        IdempotencyMiddleware,
        store=RedisIdempotencyStore(Redis.from_url("redis://localhost:6379/0")),
        ttl_seconds=24 * 3600,
    )
    ```

### Conflito (decisão sua)

Idempotência resolve **replay duplicado**, não **conflito de conteúdo** (dois
clientes editando a mesma linha). O modelo default da fila do tempestweb é
**last-write-wins**: a última escrita a chegar vence. Para a maioria dos apps
(notas, logs, formulários) isso basta.

Se você precisa de resolução por **versão** (rejeitar uma escrita baseada numa
versão obsoleta), isso é uma decisão de **aplicação** — nem o tempestweb nem o SDK
impõem um protocolo. Um padrão comum é versionar a linha e recusar escritas
obsoletas:

```python
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession


@app.put("/api/notes/{note_id}", response_model=NoteResponseSchema)
async def update_note(
    note_id: str,
    data: NoteUpdateSchema,             # inclui um campo `version: int`
    session: AsyncSession = Depends(get_session),
) -> NoteResponseSchema:
    """Atualiza uma nota rejeitando escritas baseadas numa versão velha."""
    repo = BaseRepository(session, model=NoteModel)
    note = await repo.get_by_id(note_id)              # 404 se não existe
    if data.version < note.version:                    # conflito → o cliente relê
        raise HTTPException(status_code=409, detail="stale version")
    note.text = data.text
    note.version = data.version + 1
    return NoteResponseSchema.model_validate(await repo.update(note))
```

Quando o servidor responde `409`, o cliente **não descarta nem reenvia em loop** a
mutação: ela sai das pendentes e vai pra **lane de conflito**. O replay continua
drenando o resto da fila e o app reconcilia depois, lendo essa lane:

```python
from tempestweb import native


async def reconcile_conflicts() -> None:
    """Relê e reconcilia as mutações que o servidor rejeitou com 409."""
    for m in await native.offline.conflicts():
        fresh = await native.http.request("GET", m.url)   # relê o estado atual
        ...                                                # merge/UI a seu critério
```

!!! note "Honestidade sobre a fronteira"
    O trecho do endpoint acima é **código de aplicação**, não uma API do framework
    — o campo `version` é seu. O tempestweb entrega a mutação de forma idempotente
    e **parqueia** o `409` na lane de conflito para você; **como reconciliar é você
    quem decide** (last-write-wins, versão, merge por campo, CRDT…).

---

## Parte E — Pull: trazer as mudanças do servidor de volta

A fila cuida do **push**. Para o **pull** (o servidor tem dados novos que o app
ainda não viu), o padrão é **delta-sync**: guardar um *watermark* (o maior
`updated_at` que você já viu) e pedir só o que mudou desde então.

O `BaseRepository` suporta o filtro `updated_at__gt` para exatamente isso:

```python
from datetime import datetime

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession


@app.get("/api/notes", response_model=list[NoteResponseSchema])
async def list_notes(
    since: datetime | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[NoteResponseSchema]:
    """Lista as notas alteradas desde `since` (delta-sync)."""
    repo = BaseRepository(session, model=NoteModel)
    filters = {"updated_at__gt": since} if since else None
    notes = await repo.list(filters=filters, order_by=NoteModel.updated_at)
    return [NoteResponseSchema.model_validate(n) for n in notes]
```

No cliente, você lê o delta com `native.http` (não com a fila — leitura não
precisa de fila durável) e avança o watermark:

```python
from tempestweb import native


async def pull_since(watermark: str | None) -> tuple[list[dict], str | None]:
    """Busca as notas alteradas desde `watermark`; devolve (notas, novo_watermark)."""
    url = "/api/notes" + (f"?since={watermark}" if watermark else "")
    response = await native.http.request("GET", url)
    if not response.ok:
        return [], watermark
    notes = response.json_body or []
    newest = max((n["updated_at"] for n in notes), default=watermark)
    return notes, newest
```

!!! info "Gap honesto: o pull é padrão de app, não uma API pronta"
    O tempestweb **não** tem uma "fila de leitura" nem um mecanismo de pull
    embutido — a fila `native.offline` é **só de escrita**. O delta-sync acima é um
    padrão que você monta com `native.http` (cliente) + o filtro `updated_at__gt`
    (SDK). Guardar o watermark localmente é decisão sua (ex.: `native.storage`).

---

## Recap

- **Push é resolvido pela fila.** `native.offline.enqueue(...)` grava local; o
  runtime drena FIFO ao voltar a rede (`online` + Background Sync) ou via
  `replay()`. Cada mutação carrega uma **chave de idempotência**.
- **A fila nunca trava.** Falha transitória repete até `maxAttempts` e então vira
  **dead-letter** (`native.offline.failed()`); erro permanente (`4xx`) é
  dead-lettered na hora; `409` vai pra **lane de conflito**
  (`native.offline.conflicts()`). Uma poison message não prende o resto.
- **O backend é FastAPI + SDK.** `BaseRepository.add()` persiste; o
  `IdempotencyMiddleware` (header `Idempotency-Key`, case-insensitive) deduplica os
  replays por `(método, caminho, chave)` — zero linha duplicada.
- **Conflito é decisão sua.** O default é last-write-wins; a lane de conflito
  entrega o `409` pra você reconciliar — versão/merge é código de aplicação.
- **Pull é delta-sync manual.** `native.http` + o filtro `updated_at__gt` do
  repositório; a fila **não** faz leitura, e o replay devolve só contagens (releia
  o recurso se precisar do `id`/timestamps).

Pronto para publicar o backend? Veja o [Deploy em produção](deploy.md) e a
[Segurança (Modo B)](security.md). 🚀
