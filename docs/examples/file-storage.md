# Notas no armazenamento do dispositivo 📝

Construa um CRUD de notas completo persistido no **IndexedDB do browser** via `tempestweb.native.storage` — e aprenda como injetar capacidades nativas no estado para que sua UI seja 100 % testável sem browser.

---

## O que você vai construir

Um gerenciador de notas com:

- ✏️ **Compositor** — campos de título e corpo + botões "Save" e "Reload list"
- 📋 **Lista de notas** — uma linha por nota salva com botões "Open" e "Delete"
- 📖 **Painel de visualização** — exibe título e conteúdo da nota aberta
- ⚠️ **Faixa de erro** — texto vermelho quando uma operação falha
- 🔄 **Indicador de progresso** — `Spinner` durante save e reload

As quatro operações de storage (`put` / `get` / `list_keys` / `remove`) são **injetadas no estado** do app — você pode substituí-las por doubles de teste sem instalar nenhuma ponte real.

!!! note "Tema — Capacidades nativas (Track N)"
    Este exemplo faz parte do tema **Native capabilities**. As capacidades nativas são APIs do browser (IndexedDB, geolocalização, câmera, etc.) expostas ao Python como awaitables tipados por `tempestweb.native`. A mesma chamada Python funciona nos dois modos de execução — WASM ou servidor.

---

## Pré-requisitos

Certifique-se de ter o tempestweb instalado:

```bash
pip install tempestweb
```

Leitura recomendada (opcional, mas útil):

- [Tutorial básico](../tutorial/index.md) — primeiros passos com `App`, `view` e `set_state`
- [Gerenciando estado](../tutorial/state.md) — como `set_state` funciona
- [Modos de execução](../tutorial/modes.md) — WASM vs. servidor
- [Capacidades nativas](../capabilities.md) — o que são pontes e por que são necessárias

---

## Criando o projeto

```bash
mkdir -p examples/file-storage
touch examples/file-storage/app.py
```

---

## Passo 1 — Por que os callables de storage ficam no estado?

Antes de escrever qualquer widget, vale entender o padrão de design central deste exemplo.

As funções `storage.put`, `storage.get`, etc. **só funcionam com uma ponte nativa instalada**. Durante o render inicial (o `build(view(app))` que o framework chama na montagem) nenhuma operação de I/O é executada — apenas a árvore de widgets é construída. A ponte não precisa estar presente nesse momento.

!!! warning "Capacidades nativas exigem uma ponte"
    Chamar `await storage.put(...)` (ou qualquer outra capacidade nativa) **sem uma ponte instalada** levanta `BrowserUnavailableError`. A ponte é instalada automaticamente pelo runtime:

    - **Modo A (WASM):** o bootstrap instala uma `FFIBridge` que despacha para `client/native/*.js` via FFI do Pyodide — sem round-trip de rede.
    - **Modo B (servidor):** o servidor instala uma `ProxyBridge` que serializa a chamada para o envelope `native_call`, envia pelo WebSocket, aguarda o `native_result` que o browser devolve.

    Em **testes unitários** — sem browser nem servidor — instale um fake bridge com `install_bridge(fake)` antes de acionar handlers async, e remova-o com `uninstall_bridge()` depois. O render inicial (construção da árvore de widgets) jamais chama os callables — não precisa de bridge.

A solução é colocar os callables como campos do estado com os valores reais como default. Assim:

- O `build(view(app))` inicial não toca I/O e funciona sem bridge.
- Os handlers async leem `app.state.put`, `app.state.get` etc. — e em testes você sobrescreve esses campos com fakes antes de acionar o handler.

```python
from collections.abc import Awaitable, Callable

from tempestweb.native import storage

Putter = Callable[[str, str], Awaitable[None]]
Getter = Callable[[str], Awaitable[str]]
Remover = Callable[[str], Awaitable[None]]
KeyLister = Callable[[], Awaitable[list[str]]]
```

!!! tip "Dica — aliases de tipo para callables injetados"
    Nomear os tipos de callable (`Putter`, `Getter`, etc.) cumpre dois objetivos: o `mypy --strict` passa sem reclamações e a intenção fica documentada no campo do dataclass.

---

## Passo 2 — O estado da aplicação

```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class State:
    """Application state for the notes storage demo.

    Attributes:
        title_draft: The title currently typed in the title field.
        body_draft: The body currently typed in the body field.
        keys: The list of saved note keys fetched from storage.
        open_key: The key of the note currently open for reading, or ``""``.
        open_content: The content of the open note, or ``""``.
        saving: ``True`` while a save operation is in flight.
        loading: ``True`` while a list or open operation is in flight.
        error: Last error message, or ``""`` when there is no error.
        put: Injected callable matching :func:`~tempestweb.native.storage.put`.
        get: Injected callable matching :func:`~tempestweb.native.storage.get`.
        remove: Injected callable matching
            :func:`~tempestweb.native.storage.remove`.
        list_keys: Injected callable matching
            :func:`~tempestweb.native.storage.list_keys`.
    """

    title_draft: str = ""
    body_draft: str = ""
    keys: list[str] = field(default_factory=list)
    open_key: str = ""
    open_content: str = ""
    saving: bool = False
    loading: bool = False
    error: str = ""
    # Injected capabilities — real implementations by default; only called
    # inside async handlers, never during the initial mount/build.
    put: Putter = field(default=storage.put)
    get: Getter = field(default=storage.get)
    remove: Remover = field(default=storage.remove)
    list_keys: KeyLister = field(default=storage.list_keys)


def make_state() -> State:
    """Return the initial, blank application state.

    Returns:
        A fresh :class:`State` ready for the first render.
    """
    return State()
```

!!! info "Nota — `field(default=storage.put)` vs. `field(default_factory=...)`"
    Como `storage.put` é uma função (não um objeto mutável como uma lista), podemos usá-la diretamente como `default=` em vez de `default_factory=`. O dataclass armazenará uma referência para a função — que é exatamente o comportamento desejado.

---

## Passo 3 — O handler de salvar

Dentro de `view()` definimos os handlers como funções aninhadas. O handler de save é assíncrono porque chama `await app.state.put(...)`:

```python
async def save_note() -> None:
    """Persist the current draft to storage under ``title_draft``."""
    title = app.state.title_draft.strip()
    body = app.state.body_draft
    if not title:
        return
    app.set_state(lambda s: setattr(s, "saving", True))
    try:
        await app.state.put(title, body)

        def _on_saved(s: State) -> None:
            s.saving = False
            s.title_draft = ""
            s.body_draft = ""
            s.error = ""

        app.set_state(_on_saved)
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)

        def _on_save_error(s: State) -> None:
            s.saving = False
            s.error = msg

        app.set_state(_on_save_error)
```

!!! tip "Dica — otimismo + rollback"
    O handler ativa `saving=True` antes do `await` para dar feedback imediato. Nos dois ramos seguintes (`_on_saved` e `_on_save_error`) ele desativa `saving=False`. Esse padrão "otimista + rollback" evita que a UI fique travada se o await for cancelado antes de completar.

!!! warning "Aviso — `except Exception as exc` dentro de handlers"
    Capacidades nativas levantam `NativeError` (quota excedida, `not_found`, etc.) e `BrowserUnavailableError` (bridge não instalada). Capturar `Exception` genérico aqui é intencional: a UI deve mostrar o erro para o usuário em vez de explodir. O comentário `# noqa: BLE001` suprime o aviso de `broad-exception-caught` do ruff.

---

## Passo 4 — O handler de listar

```python
async def refresh_list() -> None:
    """Fetch all stored note keys and update the list."""
    app.set_state(lambda s: setattr(s, "loading", True))
    try:
        keys = await app.state.list_keys()

        def _on_keys(s: State) -> None:
            s.loading = False
            s.keys = keys
            s.error = ""

        app.set_state(_on_keys)
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)

        def _on_list_error(s: State) -> None:
            s.loading = False
            s.error = msg

        app.set_state(_on_list_error)
```

!!! info "Nota — `list_keys` nunca levanta NotFoundError"
    `storage.list_keys()` retorna `[]` quando o armazenamento está vazio — jamais levanta exceção de "não encontrado". Isso segue a convenção do framework: 404 só para lookups de recurso único; coleções retornam `[]`.

---

## Passo 5 — Os handlers de abrir e excluir

Como Open e Delete precisam saber *qual* nota estão operando, eles usam o padrão **factory de handler**: uma função síncrona recebe a chave e retorna um callable async sem parâmetros adequado para `Button.on_click`.

```python
def open_note_handler(note_key: str) -> Callable[[], Awaitable[None]]:
    """Return an async click handler that opens *note_key*.

    Args:
        note_key: The storage key to open.

    Returns:
        A parameterless async callable suitable for ``Button.on_click``.
    """

    async def _open() -> None:
        app.set_state(lambda s: setattr(s, "loading", True))
        try:
            content = await app.state.get(note_key)

            def _on_open(s: State) -> None:
                s.loading = False
                s.open_key = note_key
                s.open_content = content
                s.error = ""

            app.set_state(_on_open)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)

            def _on_open_error(s: State) -> None:
                s.loading = False
                s.error = msg

            app.set_state(_on_open_error)

    return _open


def delete_note_handler(note_key: str) -> Callable[[], Awaitable[None]]:
    """Return an async click handler that deletes *note_key*.

    Args:
        note_key: The storage key to delete.

    Returns:
        A parameterless async callable suitable for ``Button.on_click``.
    """

    async def _delete() -> None:
        try:
            await app.state.remove(note_key)

            # Also remove from local list immediately for a snappy UI.
            def _on_delete(s: State) -> None:
                s.keys = [k for k in s.keys if k != note_key]
                if s.open_key == note_key:
                    s.open_key = ""
                    s.open_content = ""
                s.error = ""

            app.set_state(_on_delete)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            app.set_state(lambda s: setattr(s, "error", msg))

    return _delete
```

!!! tip "Dica — remoção otimista da lista local em `_delete`"
    Depois que `await app.state.remove(note_key)` retorna com sucesso, o handler filtra `app.state.keys` imediatamente — sem fazer um novo round-trip de `list_keys`. Isso deixa a UI responsiva: o item desaparece na hora. Um `Reload list` posterior sincroniza com o estado real do IndexedDB.

!!! tip "Dica — factory de handler vs. `lambda _k=key: ...`"
    Você poderia usar `lambda _k=note_key: _open_impl(_k)` dentro do loop para capturar o valor atual, mas a factory `open_note_handler(key)` é mais legível e permite anotar o tipo de retorno com precisão — o que o `mypy --strict` exige.

---

## Passo 6 — O handler de fechar

```python
def close_note() -> None:
    """Clear the open-note panel."""

    def _close(s: State) -> None:
        s.open_key = ""
        s.open_content = ""

    app.set_state(_close)
```

Este handler é **síncrono** — não acessa storage, apenas limpa dois campos de estado.

---

## Passo 7 — Montando a UI

A `view` monta três seções em colunas empilhadas na raiz. Veja cada seção:

### Compositor

```python
composer_children: list[Widget] = [
    Text(content="New note", key="composer-title"),
    Input(
        value=app.state.title_draft,
        placeholder="Title",
        key="title-input",
        on_change=lambda e: app.set_state(
            lambda s: setattr(s, "title_draft", e.value)
        ),
    ),
    TextArea(
        value=app.state.body_draft,
        placeholder="Write your note here…",
        key="body-input",
        on_change=lambda e: app.set_state(
            lambda s: setattr(s, "body_draft", e.value)
        ),
    ),
    Row(
        style=Style(gap=8.0),
        key="composer-actions",
        children=[
            Button(
                label="Save" if not app.state.saving else "Saving…",
                on_click=save_note,
                key="save-btn",
            ),
            Button(label="Reload list", on_click=refresh_list, key="reload-btn"),
        ],
    ),
]

if app.state.saving:
    composer_children.append(Spinner(key="save-spinner"))
```

!!! tip "Dica — label condicional no botão"
    `label="Save" if not app.state.saving else "Saving…"` é o jeito idiomático de dar feedback visual durante uma operação assíncrona sem mudar a estrutura da árvore — o mesmo nó de botão com `key="save-btn"` é atualizado, não substituído.

### Lista de notas

```python
list_children: list[Widget] = [
    Text(content="Saved notes", key="list-title"),
]

if app.state.loading:
    list_children.append(Spinner(key="list-spinner"))
elif not app.state.keys:
    list_children.append(
        Text(
            content="No notes yet — type a title and hit Save.",
            key="empty-hint",
        )
    )
else:
    for key in app.state.keys:
        list_children.append(
            Row(
                style=Style(gap=8.0),
                key=f"row-{key}",
                children=[
                    Text(content=key, key=f"key-{key}"),
                    Button(
                        label="Open",
                        on_click=open_note_handler(key),
                        key=f"open-{key}",
                    ),
                    Button(
                        label="Delete",
                        on_click=delete_note_handler(key),
                        key=f"delete-{key}",
                    ),
                ],
            )
        )
```

!!! info "Nota — três estados da lista"
    | Condição | O que é renderizado |
    |---|---|
    | `app.state.loading` é `True` | `Spinner` |
    | `app.state.keys` é `[]` | Texto de dica "No notes yet" |
    | Há chaves | Uma `Row` por nota com Open e Delete |

### Painel de visualização

```python
viewer_children: list[Widget] = []
if app.state.open_key:
    viewer_children = [
        Text(content=f"Note: {app.state.open_key}", key="viewer-title"),
        Text(content=app.state.open_content, key="viewer-body"),
        Button(label="Close", on_click=close_note, key="close-btn"),
    ]
```

O painel só aparece quando `open_key` não está vazio — o viewer inteiro é adicionado condicionalmente à lista `all_sections`.

### Montagem final

```python
all_sections: list[Widget] = [
    Column(
        style=Style(gap=8.0, padding=Edge.all(8)),
        key="composer",
        children=composer_children,
    ),
    Column(
        style=Style(gap=6.0, padding=Edge.all(8)),
        key="note-list",
        children=list_children,
    ),
]

if viewer_children:
    all_sections.append(
        Column(
            style=Style(gap=6.0, padding=Edge.all(8)),
            key="viewer",
            children=viewer_children,
        )
    )

if app.state.error:
    all_sections.append(
        Text(content=f"Error: {app.state.error}", key="error-strip")
    )

return Column(
    style=Style(gap=16.0, padding=Edge.all(16)),
    key="root",
    children=all_sections,
)
```

---

## O app completo

Arquivo completo pronto para copiar:

```python
"""Notes CRUD — persisted via the device storage capability (N3).

A genuinely useful demo of ``tempestweb.native.storage``: the user types a note
title and body, saves it to IndexedDB via ``storage.put``, lists all saved keys,
opens any note, and deletes it.  The four storage callables
(:func:`~tempestweb.native.storage.put`, :func:`~tempestweb.native.storage.get`,
:func:`~tempestweb.native.storage.list_keys`,
:func:`~tempestweb.native.storage.remove`) are **injected into** :class:`State`
so the example is deterministic under test and ``build(view(app))`` is green with
no bridge installed.

The demo runs identically in both execution modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from tempest_core import App, Style, Widget
from tempest_core.style import Edge
from tempest_core.widgets import (
    Button,
    Column,
    Input,
    Row,
    Spinner,
    Text,
    TextArea,
)
from tempestweb.native import storage

# ---------------------------------------------------------------------------
# Callable type aliases for the injected storage capabilities.
# ---------------------------------------------------------------------------

Putter = Callable[[str, str], Awaitable[None]]
Getter = Callable[[str], Awaitable[str]]
Remover = Callable[[str], Awaitable[None]]
KeyLister = Callable[[], Awaitable[list[str]]]


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class State:
    """Application state for the notes storage demo.

    Attributes:
        title_draft: The title currently typed in the title field.
        body_draft: The body currently typed in the body field.
        keys: The list of saved note keys fetched from storage.
        open_key: The key of the note currently open for reading, or ``""``.
        open_content: The content of the open note, or ``""``.
        saving: ``True`` while a save operation is in flight.
        loading: ``True`` while a list or open operation is in flight.
        error: Last error message, or ``""`` when there is no error.
        put: Injected callable matching :func:`~tempestweb.native.storage.put`.
        get: Injected callable matching :func:`~tempestweb.native.storage.get`.
        remove: Injected callable matching
            :func:`~tempestweb.native.storage.remove`.
        list_keys: Injected callable matching
            :func:`~tempestweb.native.storage.list_keys`.
    """

    title_draft: str = ""
    body_draft: str = ""
    keys: list[str] = field(default_factory=list)
    open_key: str = ""
    open_content: str = ""
    saving: bool = False
    loading: bool = False
    error: str = ""
    # Injected capabilities — real implementations by default; only called
    # inside async handlers, never during the initial mount/build.
    put: Putter = field(default=storage.put)
    get: Getter = field(default=storage.get)
    remove: Remover = field(default=storage.remove)
    list_keys: KeyLister = field(default=storage.list_keys)


def make_state() -> State:
    """Return the initial, blank application state.

    Returns:
        A fresh :class:`State` ready for the first render.
    """
    return State()


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


def view(app: App[State]) -> Widget:
    """Render the notes CRUD UI from the current state.

    Layout:

    * **Composer** — title + body inputs + Save / Reload buttons.
    * **Note list** — scrollable column of (key, Open, Delete) rows.
    * **Note viewer** — title + content shown when a note is open.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The full widget tree for the current state.
    """

    # ------------------------------------------------------------------ handlers

    async def save_note() -> None:
        """Persist the current draft to storage under ``title_draft``."""
        title = app.state.title_draft.strip()
        body = app.state.body_draft
        if not title:
            return
        app.set_state(lambda s: setattr(s, "saving", True))
        try:
            await app.state.put(title, body)

            def _on_saved(s: State) -> None:
                s.saving = False
                s.title_draft = ""
                s.body_draft = ""
                s.error = ""

            app.set_state(_on_saved)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)

            def _on_save_error(s: State) -> None:
                s.saving = False
                s.error = msg

            app.set_state(_on_save_error)

    async def refresh_list() -> None:
        """Fetch all stored note keys and update the list."""
        app.set_state(lambda s: setattr(s, "loading", True))
        try:
            keys = await app.state.list_keys()

            def _on_keys(s: State) -> None:
                s.loading = False
                s.keys = keys
                s.error = ""

            app.set_state(_on_keys)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)

            def _on_list_error(s: State) -> None:
                s.loading = False
                s.error = msg

            app.set_state(_on_list_error)

    def open_note_handler(note_key: str) -> Callable[[], Awaitable[None]]:
        """Return an async click handler that opens *note_key*.

        Args:
            note_key: The storage key to open.

        Returns:
            A parameterless async callable suitable for ``Button.on_click``.
        """

        async def _open() -> None:
            app.set_state(lambda s: setattr(s, "loading", True))
            try:
                content = await app.state.get(note_key)

                def _on_open(s: State) -> None:
                    s.loading = False
                    s.open_key = note_key
                    s.open_content = content
                    s.error = ""

                app.set_state(_on_open)
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)

                def _on_open_error(s: State) -> None:
                    s.loading = False
                    s.error = msg

                app.set_state(_on_open_error)

        return _open

    def delete_note_handler(note_key: str) -> Callable[[], Awaitable[None]]:
        """Return an async click handler that deletes *note_key*.

        Args:
            note_key: The storage key to delete.

        Returns:
            A parameterless async callable suitable for ``Button.on_click``.
        """

        async def _delete() -> None:
            try:
                await app.state.remove(note_key)

                # Also remove from local list immediately for a snappy UI.
                def _on_delete(s: State) -> None:
                    s.keys = [k for k in s.keys if k != note_key]
                    if s.open_key == note_key:
                        s.open_key = ""
                        s.open_content = ""
                    s.error = ""

                app.set_state(_on_delete)
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)
                app.set_state(lambda s: setattr(s, "error", msg))

        return _delete

    def close_note() -> None:
        """Clear the open-note panel."""

        def _close(s: State) -> None:
            s.open_key = ""
            s.open_content = ""

        app.set_state(_close)

    # ---------------------------------------------------------- composer section

    composer_children: list[Widget] = [
        Text(content="New note", key="composer-title"),
        Input(
            value=app.state.title_draft,
            placeholder="Title",
            key="title-input",
            on_change=lambda e: app.set_state(
                lambda s: setattr(s, "title_draft", e.value)
            ),
        ),
        TextArea(
            value=app.state.body_draft,
            placeholder="Write your note here…",
            key="body-input",
            on_change=lambda e: app.set_state(
                lambda s: setattr(s, "body_draft", e.value)
            ),
        ),
        Row(
            style=Style(gap=8.0),
            key="composer-actions",
            children=[
                Button(
                    label="Save" if not app.state.saving else "Saving…",
                    on_click=save_note,
                    key="save-btn",
                ),
                Button(label="Reload list", on_click=refresh_list, key="reload-btn"),
            ],
        ),
    ]

    if app.state.saving:
        composer_children.append(Spinner(key="save-spinner"))

    # ----------------------------------------------------------------- note list

    list_children: list[Widget] = [
        Text(content="Saved notes", key="list-title"),
    ]

    if app.state.loading:
        list_children.append(Spinner(key="list-spinner"))
    elif not app.state.keys:
        list_children.append(
            Text(
                content="No notes yet — type a title and hit Save.",
                key="empty-hint",
            )
        )
    else:
        for key in app.state.keys:
            list_children.append(
                Row(
                    style=Style(gap=8.0),
                    key=f"row-{key}",
                    children=[
                        Text(content=key, key=f"key-{key}"),
                        Button(
                            label="Open",
                            on_click=open_note_handler(key),
                            key=f"open-{key}",
                        ),
                        Button(
                            label="Delete",
                            on_click=delete_note_handler(key),
                            key=f"delete-{key}",
                        ),
                    ],
                )
            )

    # --------------------------------------------------------------- note viewer

    viewer_children: list[Widget] = []
    if app.state.open_key:
        viewer_children = [
            Text(content=f"Note: {app.state.open_key}", key="viewer-title"),
            Text(content=app.state.open_content, key="viewer-body"),
            Button(label="Close", on_click=close_note, key="close-btn"),
        ]

    # --------------------------------------------------------------- error strip

    all_sections: list[Widget] = [
        Column(
            style=Style(gap=8.0, padding=Edge.all(8)),
            key="composer",
            children=composer_children,
        ),
        Column(
            style=Style(gap=6.0, padding=Edge.all(8)),
            key="note-list",
            children=list_children,
        ),
    ]

    if viewer_children:
        all_sections.append(
            Column(
                style=Style(gap=6.0, padding=Edge.all(8)),
                key="viewer",
                children=viewer_children,
            )
        )

    if app.state.error:
        all_sections.append(
            Text(content=f"Error: {app.state.error}", key="error-strip")
        )

    return Column(
        style=Style(gap=16.0, padding=Edge.all(16)),
        key="root",
        children=all_sections,
    )
```

---

## Rodando o exemplo ▶

### Modo A — Python no browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm --path examples/file-storage
```

Python roda **dentro do browser** via Pyodide. A `FFIBridge` é instalada automaticamente. As chamadas a `storage.put/get/list_keys/remove` vão direto para `client/native/storage.js`, que usa o IndexedDB do browser.

### Modo B — Python no servidor (FastAPI + WebSocket)

```bash
tempestweb dev --mode server --path examples/file-storage
```

Python roda no servidor; a `ProxyBridge` é instalada automaticamente. Cada chamada nativa serializa um envelope `native_call` pelo WebSocket, o browser executa o IndexedDB e devolve um envelope `native_result`.

!!! check "Verificação"
    Em qualquer modo, você deve ver:

    1. Seção "New note" com campo de título, campo de corpo, botões "Save" e "Reload list"
    2. Seção "Saved notes" com o texto *"No notes yet — type a title and hit Save."*
    3. Digite um título, um corpo e clique **Save** → os campos limpam; "Saving…" aparece brevemente
    4. Clique **Reload list** → a nota aparece na lista com botões **Open** e **Delete**
    5. Clique **Open** → painel de visualização aparece com título e conteúdo
    6. Clique **Close** → painel fecha
    7. Clique **Delete** → linha desaparece imediatamente; recarregue para confirmar

---

## Verificação automatizada ✅

Rode os cinco checks antes de commitar:

```bash
# Lint
ruff check .

# Formatação
ruff format --check .

# Tipos
mypy --strict tempestweb

# Testes (7 testes, todos verdes)
pytest -q
```

Todos passam em verde. O check `build(view(app))` sem bridge é o **Teste 1** da suite — garante que o render inicial é determinístico mesmo sem browser.

---

## Como testar com capacidades nativas

O padrão de injeção de dependência que você viu no estado facilita muito os testes. Veja como o `FakeBridge` da suite funciona:

```python
from typing import Any

from tempestweb.native import install_bridge, uninstall_bridge


class FakeBridge:
    """In-memory storage bridge for testing native.storage calls.

    Backs ``storage.put`` / ``storage.get`` / ``storage.list`` /
    ``storage.remove`` with a plain Python ``dict``.  Any other capability
    returns ``ok: False`` so tests fail explicitly if something unexpected is
    invoked.

    Attributes:
        store: The backing dictionary (``{key: content}``).
        calls: Every envelope dispatched through the bridge (audit log).
    """

    def __init__(self) -> None:
        """Initialise with an empty store and empty call log."""
        self.store: dict[str, str] = {}
        self.calls: list[dict[str, Any]] = []

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a native call envelope to the in-memory store."""
        self.calls.append(envelope)
        cap: str = envelope.get("capability", "")
        args: dict[str, Any] = envelope.get("args", {})

        if cap == "storage.put":
            self.store[args["name"]] = args["content"]
            return {"ok": True, "value": {}}

        if cap == "storage.get":
            name = args["name"]
            if name not in self.store:
                return {"ok": False, "error": "not_found", "message": f"{name!r} not found"}
            return {"ok": True, "value": {"content": self.store[name]}}

        if cap == "storage.list":
            return {"ok": True, "value": {"keys": list(self.store.keys())}}

        if cap == "storage.remove":
            name = args["name"]
            if name not in self.store:
                return {"ok": False, "error": "not_found", "message": f"{name!r} not found"}
            del self.store[name]
            return {"ok": True, "value": {}}

        return {"ok": False, "error": "unavailable", "message": f"unknown cap {cap!r}"}
```

E a fixture pytest que instala e remove o fake automaticamente:

```python
import pytest

@pytest.fixture(autouse=True)
def _clean_bridge():
    """Install a fresh FakeBridge before each test; remove it after."""
    bridge = FakeBridge()
    install_bridge(bridge)
    yield bridge
    uninstall_bridge()
```

!!! tip "Dica — por que `install_bridge` em vez de apenas substituir os campos do estado?"
    Você poderia sobrescrever `app.state.put = fake_put` antes de cada teste — isso também funciona. A vantagem de instalar um `FakeBridge` completo é que ele intercepta *qualquer* capacidade nativa que o código venha a chamar, não apenas as que você antecipou. O log `self.calls` também permite verificar os envelopes enviados — útil para auditar que a API contratual está correta.

---

## Como funciona por dentro

### O ciclo de atualização com I/O assíncrono

```
Clique em "Save"  (save_note)
      │
      ▼
app.set_state(saving=True)    ← re-render imediato: label muda para "Saving…"
      │
      ▼
await app.state.put(title, body)
      │  Mode A: FFI direto para IndexedDB (sem rede)
      │  Mode B: native_call → WebSocket → browser → native_result → aqui
      ▼
app.set_state(_on_saved)      ← re-render: campos limpos, saving=False
      │
      ▼
view(app) chamada novamente → nova árvore de widgets
      │
      ▼
reconciliador calcula diff (patches)
      │
      ▼
DOM atualizado — apenas os nós que mudaram
```

### Comparação: `storage.put` vs. `storage.get`

| Função | Retorna | Levanta em erro |
|---|---|---|
| `storage.put(name, content)` | `None` | `NativeError("quota_exceeded")` |
| `storage.get(name)` | `str` | `NativeError("not_found")` |
| `storage.remove(name)` | `None` | `NativeError("not_found")` |
| `storage.list_keys()` | `list[str]` (pode ser `[]`) | nunca levanta NotFoundError |

### Por que `key=f"open-{key}"` e não `key=f"open-{index}"`?

Se você usasse `key=f"open-{index}"`, excluir a nota no índice 0 faria a antiga nota do índice 1 herdar a chave `"open-0"` — o reconciliador interpretaria isso como uma *atualização* do nó existente, não como uma *remoção + inserção*. Com `key=f"open-{key}"` (baseado no próprio nome da nota), cada linha tem identidade estável e o reconciliador faz a remoção corretamente.

---

## Recapitulando

Neste tutorial você aprendeu:

- ✅ Usar `tempestweb.native.storage` para persistir dados em IndexedDB nos dois modos
- ✅ Injetar callables de capacidade nativa no estado para que o render inicial seja bridge-free
- ✅ Escrever handlers assíncronos com o padrão "otimismo + rollback" (`saving=True` antes do await)
- ✅ Usar o padrão **factory de handler** para closures com chave capturada
- ✅ Implementar remoção otimista da lista local sem round-trip adicional
- ✅ Testar capacidades nativas com um `FakeBridge` in-memory e `install_bridge`/`uninstall_bridge`
- ✅ Garantir que `build(view(app))` sem bridge nunca levanta exceção

---

## Próximos passos

Experimente estender o exemplo:

- 💡 Adicione um campo `created_at` às notas (serialize como JSON no `content`) e ordene a lista por data
- 💡 Implemente edição de notas: clique em Open para carregar o draft nos campos e salve sobre a mesma chave
- 💡 Adicione uma busca por prefixo filtrando `app.state.keys` na renderização — sem round-trip extra
- 💡 Explore `tempestweb.native.clipboard` para copiar o conteúdo de uma nota com um botão (veja o exemplo [Clipboard & Share](./clipboard-share.md))
- 💡 Combine com [PWA Web Push](./notification-center.md) para notificar o usuário quando uma nota é salva em outro dispositivo
