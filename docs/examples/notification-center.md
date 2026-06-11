# Notification Center — Central de Notificações 🚀

Construa uma caixa de entrada de notificações completa com `Banner`, `Badge` e `EmptyState` — e aprenda como modelar **estados de feedback agregado** com máquina de fases no tempestweb.

---

## O que você vai construir

Uma central de notificações com:

- 🔔 **Cabeçalho** com título, `Badge` vermelho mostrando o total de não lidas e botão de ação
- 📣 **Banner de status agregado** que reflete o alarme geral da caixa de entrada em tempo real
- 📋 **Lista preguiçosa** (`LazyColumn`) com um `Banner` por notificação — cada um com seu botão de dispensar
- 🔕 **Estado vazio** (`EmptyState`) quando todas as notificações são descartadas
- Três transições verificadas: *dismiss one*, *dismiss all* e *reset*

!!! note "Nota — máquina de fases"
    O app usa uma `StrEnum` chamada `Phase` com dois valores: `INBOX` (uma ou mais notificações presentes) e `CLEAR` (tudo dispensado). A `view` lê `app.state.phase` para decidir qual ramo renderizar — sem booleanos avulsos, sem condicionais aninhadas difíceis de rastrear.

---

## Pré-requisitos

Certifique-se de ter o tempestweb instalado:

```bash
pip install tempestweb
```

Leia antes (opcional, mas recomendado):

- [Tutorial básico](../tutorial/index.md) — primeiros passos com `App`, `view` e `set_state`
- [Gerenciando estado](../tutorial/state.md) — como `set_state` funciona
- [Modos de execução](../tutorial/modes.md) — WASM vs. servidor

---

## Criando o projeto

Crie a pasta e o arquivo do app:

```bash
mkdir -p examples/notification-center
touch examples/notification-center/app.py
```

---

## Passo 1 — Modelo de domínio

Antes da UI, precisamos representar uma notificação. Cada item tem um identificador único, uma mensagem, um **tom** (severity) e um flag `read`.

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import uuid4


#: Notification severity levels, mapped directly to Banner tones.
TONES: tuple[str, ...] = ("info", "success", "warning", "error")


@dataclass
class Notification:
    """A single notification entry.

    Attributes:
        id: Unique identifier used as a widget key.
        message: The human-readable message text.
        tone: One of ``"info"``, ``"success"``, ``"warning"`` or ``"error"``.
        read: Whether the notification has been seen by the user.
    """

    id: str
    message: str
    tone: str
    read: bool = False


def _seed() -> list[Notification]:
    """Return the initial set of seed notifications.

    Returns:
        A fresh list of four pre-built notifications covering every tone.
    """
    return [
        Notification(
            id=str(uuid4()),
            message="Your export has been queued and will be ready shortly.",
            tone="info",
        ),
        Notification(
            id=str(uuid4()),
            message="Payment processed — invoice #2048 is available.",
            tone="success",
        ),
        Notification(
            id=str(uuid4()),
            message="Your free-tier storage is 85 % full.  Consider upgrading.",
            tone="warning",
        ),
        Notification(
            id=str(uuid4()),
            message="Scheduled job 'nightly-backup' failed.  Check the logs.",
            tone="error",
        ),
    ]
```

!!! tip "Dica — `uuid4()` para chaves de widget"
    Cada notificação recebe um `id` aleatório na criação. Esse `id` é usado como `key` no widget `Banner` correspondente. Isso garante que o reconciliador identifique corretamente cada linha mesmo quando itens são removidos no meio da lista.

---

## Passo 2 — Fase e estado

A `Phase` é uma `StrEnum` simples. O estado principal combina a fase atual com a lista de itens e expõe uma propriedade calculada `unread_count`.

```python
class Phase(StrEnum):
    """Lifecycle phase of the notification center.

    Attributes:
        INBOX: One or more notifications are present.
        CLEAR: All notifications have been dismissed.
    """

    INBOX = "inbox"
    CLEAR = "clear"


@dataclass
class NotificationState:
    """Top-level state for the notification-center app.

    Attributes:
        phase: Current lifecycle phase (INBOX or CLEAR).
        items: Ordered list of active notifications.
    """

    phase: Phase = Phase.INBOX
    items: list[Notification] = field(default_factory=_seed)

    @property
    def unread_count(self) -> int:
        """Count notifications that have not yet been read.

        Returns:
            Number of items whose ``read`` flag is ``False``.
        """
        return sum(1 for n in self.items if not n.read)


def make_state() -> NotificationState:
    """Build the initial application state with seed notifications.

    Returns:
        A fresh :class:`NotificationState` pre-populated with four items so
        the first mount shows a non-empty notification list.
    """
    return NotificationState()
```

!!! info "Nota — `@property` vs. campo de estado"
    `unread_count` é uma **propriedade derivada**, não um campo do estado. Ela é recalculada a cada chamada a partir da lista `items`. Isso é intencional: manter o estado mínimo e calcular o que é possível dentro da `view` (ou em propriedades do dataclass) evita inconsistências — você nunca esquece de atualizar um contador separado.

---

## Passo 3 — Os handlers de transição

Dentro de `view()`, definimos três handlers. Cada um chama `app.set_state(mutador)` onde o mutador recebe o estado atual e o altera in-place:

```python
def dismiss_one(notification_id: str) -> None:
    """Remove a single notification and mark the inbox clear if empty.

    Args:
        notification_id: The ``id`` of the notification to remove.
    """

    def mutate(s: NotificationState) -> None:
        s.items = [n for n in s.items if n.id != notification_id]
        if not s.items:
            s.phase = Phase.CLEAR

    app.set_state(mutate)


def dismiss_all() -> None:
    """Remove every notification and switch to the CLEAR phase."""

    def mutate(s: NotificationState) -> None:
        s.items = []
        s.phase = Phase.CLEAR

    app.set_state(mutate)


def reset() -> None:
    """Restore the seed notifications and switch back to INBOX phase."""

    def mutate(s: NotificationState) -> None:
        s.items = _seed()
        s.phase = Phase.INBOX

    app.set_state(mutate)
```

!!! tip "Dica — transição de fase automática em `dismiss_one`"
    Repare que `dismiss_one` verifica `if not s.items` após filtrar a lista. Quando o último item é dispensado, a fase muda automaticamente para `CLEAR` — não é necessário um botão separado nem um handler especial para o "último item".

---

## Passo 4 — O cabeçalho com Badge

O cabeçalho combina um `Text` com `grow=1.0` (ocupa o espaço sobrando), um `Badge` com o contador de não lidas e um botão condicional que muda de "Dismiss all" para "Reset" dependendo da fase:

```python
from tempestweb._core import App, Style, Widget
from tempestweb._core.components.feedback import Badge, Banner, EmptyState
from tempestweb._core.style import Edge
from tempestweb._core.widgets import Button, Column, LazyColumn, Row, Text


def view(app: App[NotificationState]) -> Widget:
    """Render the notification-center UI from the current state."""

    # ... (handlers definidos aqui — ver Passo 3)

    unread = app.state.unread_count
    badge_label = str(unread) if unread > 0 else "0"

    header_children: list[Widget] = [
        Text(
            content="Notifications",
            style=Style(font_size=20.0, grow=1.0),
            key="nc-title",
        ),
        Badge(label=badge_label, tone="error", key="nc-badge"),
    ]

    if app.state.phase is Phase.INBOX:
        header_children.append(
            Button(label="Dismiss all", on_click=dismiss_all, key="nc-dismiss-all")
        )
    else:
        header_children.append(Button(label="Reset", on_click=reset, key="nc-reset"))

    header: Widget = Row(
        style=Style(gap=10.0, padding=Edge.symmetric(vertical=8.0, horizontal=0.0)),
        children=header_children,
        key="nc-header",
    )
```

!!! tip "Dica — `grow=1.0` no `Text`"
    `grow=1.0` faz o widget de texto esticar para ocupar todo o espaço disponível na `Row`, empurrando o `Badge` e o botão para a direita — o comportamento clássico de um cabeçalho flexível, sem CSS externo.

---

## Passo 5 — O Banner de status agregado

Um único `Banner` no topo da página reflete o estado geral da caixa de entrada. Seu `tone` e `message` são calculados a partir da fase e do contador de não lidas:

```python
    if app.state.phase is Phase.CLEAR:
        status_tone = "success"
        status_message = "All caught up — your inbox is empty."
    elif unread > 0:
        status_tone = "warning"
        plural = "s" if unread != 1 else ""
        status_message = f"You have {unread} unread notification{plural}."
    else:
        status_tone = "info"
        status_message = "No new notifications."

    status_banner: Widget = Banner(
        message=status_message,
        tone=status_tone,
        key="nc-status-banner",
    )
```

!!! info "Nota — três estados do banner agregado"
    | Situação | Tom | Mensagem |
    |---|---|---|
    | Fase `CLEAR` | `success` ✅ | "All caught up — your inbox is empty." |
    | Há não lidas | `warning` ⚠️ | "You have N unread notification(s)." |
    | Sem não lidas, mas fase `INBOX` | `info` ℹ️ | "No new notifications." |

---

## Passo 6 — Lista preguiçosa vs. EmptyState

Este é o coração do app: quando há itens, renderizamos uma `LazyColumn` com um `Banner` por notificação; quando não há, mostramos um `EmptyState` com botão de restaurar.

```python
    if app.state.phase is Phase.CLEAR or not app.state.items:
        restore_btn: Widget = Button(
            label="Restore notifications", on_click=reset, key="nc-restore"
        )
        inbox_body: Widget = EmptyState(
            glyph="🔕",
            title="Your inbox is empty",
            subtitle="All notifications have been dismissed.",
            action=restore_btn,
            key="nc-empty",
        )
    else:
        items_snapshot = list(app.state.items)

        def build_row(index: int) -> Widget:
            """Build one notification row inside the lazy list.

            Args:
                index: Position in the current items snapshot.

            Returns:
                A ``Banner`` with a dismiss button in its action slot.
            """
            n = items_snapshot[index]
            dismiss_btn: Widget = Button(
                label="✕",
                on_click=lambda _nid=n.id: dismiss_one(_nid),
                key=f"dismiss-{n.id}",
            )
            return Banner(
                message=n.message,
                tone=n.tone,
                action=dismiss_btn,
                key=f"notif-{n.id}",
            )

        inbox_body = LazyColumn(
            item_count=len(items_snapshot),
            item_builder=build_row,
            key="nc-list",
        )
```

!!! warning "Aviso — capture a lista antes de entrar no `build_row`"
    Repare em `items_snapshot = list(app.state.items)`. A `build_row` é chamada *durante* o render com índices fixos. Se `app.state.items` pudesse mudar entre chamadas (em ambientes concorrentes), usar o state diretamente causaria bugs de índice-fora-de-limite. O snapshot garante consistência durante toda a passagem de build.

!!! tip "Dica — `lambda _nid=n.id: dismiss_one(_nid)` (default capture)"
    Python fecha sobre *variáveis*, não sobre *valores*. Dentro de um laço, `lambda: dismiss_one(n.id)` capturaria a variável `n`, que no final do laço aponta para o último item — todos os botões dispensariam o mesmo item. O padrão `_nid=n.id` cria um **argumento padrão** que captura o *valor atual* de `n.id` para cada closure. Sempre use isso em callbacks gerados dentro de laços.

---

## Passo 7 — Montando a página completa

Com o cabeçalho, o banner de status e o corpo da caixa de entrada prontos, montamos a árvore final em uma `Column`:

```python
    return Column(
        style=Style(gap=12.0, padding=Edge.all(16.0)),
        children=[
            header,
            status_banner,
            inbox_body,
        ],
    )
```

Simples, declarativo e fácil de ler. A `view` inteira não ultrapassa 150 linhas.

---

## O app completo

Aqui está o arquivo completo, pronto para copiar:

```python
"""Notification center — exercises Banner, Badge and EmptyState feedback components.

Like :mod:`examples.counter.app`, this exact ``view`` runs unchanged in both modes::

    tempestweb dev --mode wasm     # Python in the browser (Pyodide)
    tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)

This demo shows how to compose ``Banner``, ``Badge`` and ``EmptyState`` to model a
real-world notification inbox.  The panel header carries a red ``Badge`` with the
unread count.  Each notification row is an inline ``Banner`` (info / success /
warning / error tones) with a dismiss ``Button`` in its ``action`` slot.  Dismissing
all items clears the list and reveals an ``EmptyState`` telling the user their inbox
is clean.  A persistent ``Banner`` at the top surface the aggregate alarm level
(warning when any unread item exists, success once everything is dismissed).

State machine
-------------
* ``Phase.INBOX``  — one or more notifications are present.
* ``Phase.CLEAR``  — all notifications have been dismissed.

Transitions
-----------
* *dismiss one* → removes one notification; if the list empties, moves to CLEAR.
* *dismiss all* → removes every notification at once; moves to CLEAR.
* *reset*        → restores the seed notifications; moves back to INBOX.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import uuid4

from tempestweb._core import App, Style, Widget
from tempestweb._core.components.feedback import Badge, Banner, EmptyState
from tempestweb._core.style import Edge
from tempestweb._core.widgets import Button, Column, LazyColumn, Row, Text

# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------

#: Notification severity levels, mapped directly to Banner tones.
TONES: tuple[str, ...] = ("info", "success", "warning", "error")


@dataclass
class Notification:
    """A single notification entry.

    Attributes:
        id: Unique identifier used as a widget key.
        message: The human-readable message text.
        tone: One of ``"info"``, ``"success"``, ``"warning"`` or ``"error"``.
        read: Whether the notification has been seen by the user.
    """

    id: str
    message: str
    tone: str
    read: bool = False


def _seed() -> list[Notification]:
    """Return the initial set of seed notifications.

    Returns:
        A fresh list of four pre-built notifications covering every tone.
    """
    return [
        Notification(
            id=str(uuid4()),
            message="Your export has been queued and will be ready shortly.",
            tone="info",
        ),
        Notification(
            id=str(uuid4()),
            message="Payment processed — invoice #2048 is available.",
            tone="success",
        ),
        Notification(
            id=str(uuid4()),
            message="Your free-tier storage is 85 % full.  Consider upgrading.",
            tone="warning",
        ),
        Notification(
            id=str(uuid4()),
            message="Scheduled job 'nightly-backup' failed.  Check the logs.",
            tone="error",
        ),
    ]


class Phase(StrEnum):
    """Lifecycle phase of the notification center.

    Attributes:
        INBOX: One or more notifications are present.
        CLEAR: All notifications have been dismissed.
    """

    INBOX = "inbox"
    CLEAR = "clear"


# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------


@dataclass
class NotificationState:
    """Top-level state for the notification-center app.

    Attributes:
        phase: Current lifecycle phase (INBOX or CLEAR).
        items: Ordered list of active notifications.
    """

    phase: Phase = Phase.INBOX
    items: list[Notification] = field(default_factory=_seed)

    @property
    def unread_count(self) -> int:
        """Count notifications that have not yet been read.

        Returns:
            Number of items whose ``read`` flag is ``False``.
        """
        return sum(1 for n in self.items if not n.read)


def make_state() -> NotificationState:
    """Build the initial application state with seed notifications.

    Returns:
        A fresh :class:`NotificationState` pre-populated with four items so
        the first mount shows a non-empty notification list.
    """
    return NotificationState()


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


def view(app: App[NotificationState]) -> Widget:
    """Render the notification-center UI from the current state.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The widget tree for the current state.
    """

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def dismiss_one(notification_id: str) -> None:
        """Remove a single notification and mark the inbox clear if empty.

        Args:
            notification_id: The ``id`` of the notification to remove.
        """

        def mutate(s: NotificationState) -> None:
            s.items = [n for n in s.items if n.id != notification_id]
            if not s.items:
                s.phase = Phase.CLEAR

        app.set_state(mutate)

    def dismiss_all() -> None:
        """Remove every notification and switch to the CLEAR phase."""

        def mutate(s: NotificationState) -> None:
            s.items = []
            s.phase = Phase.CLEAR

        app.set_state(mutate)

    def reset() -> None:
        """Restore the seed notifications and switch back to INBOX phase."""

        def mutate(s: NotificationState) -> None:
            s.items = _seed()
            s.phase = Phase.INBOX

        app.set_state(mutate)

    # ------------------------------------------------------------------
    # Header row: title + unread badge + action buttons
    # ------------------------------------------------------------------

    unread = app.state.unread_count
    badge_label = str(unread) if unread > 0 else "0"

    header_children: list[Widget] = [
        Text(
            content="Notifications",
            style=Style(font_size=20.0, grow=1.0),
            key="nc-title",
        ),
        Badge(label=badge_label, tone="error", key="nc-badge"),
    ]

    if app.state.phase is Phase.INBOX:
        header_children.append(
            Button(label="Dismiss all", on_click=dismiss_all, key="nc-dismiss-all")
        )
    else:
        header_children.append(Button(label="Reset", on_click=reset, key="nc-reset"))

    header: Widget = Row(
        style=Style(gap=10.0, padding=Edge.symmetric(vertical=8.0, horizontal=0.0)),
        children=header_children,
        key="nc-header",
    )

    # ------------------------------------------------------------------
    # Status banner (aggregate state feedback)
    # ------------------------------------------------------------------

    if app.state.phase is Phase.CLEAR:
        status_tone = "success"
        status_message = "All caught up — your inbox is empty."
    elif unread > 0:
        status_tone = "warning"
        plural = "s" if unread != 1 else ""
        status_message = f"You have {unread} unread notification{plural}."
    else:
        status_tone = "info"
        status_message = "No new notifications."

    status_banner: Widget = Banner(
        message=status_message,
        tone=status_tone,
        key="nc-status-banner",
    )

    # ------------------------------------------------------------------
    # Notification list or empty state
    # ------------------------------------------------------------------

    if app.state.phase is Phase.CLEAR or not app.state.items:
        restore_btn: Widget = Button(
            label="Restore notifications", on_click=reset, key="nc-restore"
        )
        inbox_body: Widget = EmptyState(
            glyph="🔕",
            title="Your inbox is empty",
            subtitle="All notifications have been dismissed.",
            action=restore_btn,
            key="nc-empty",
        )
    else:
        items_snapshot = list(app.state.items)

        def build_row(index: int) -> Widget:
            """Build one notification row inside the lazy list.

            Args:
                index: Position in the current items snapshot.

            Returns:
                A ``Banner`` with a dismiss button in its action slot.
            """
            n = items_snapshot[index]
            dismiss_btn: Widget = Button(
                label="✕",
                on_click=lambda _nid=n.id: dismiss_one(_nid),
                key=f"dismiss-{n.id}",
            )
            return Banner(
                message=n.message,
                tone=n.tone,
                action=dismiss_btn,
                key=f"notif-{n.id}",
            )

        inbox_body = LazyColumn(
            item_count=len(items_snapshot),
            item_builder=build_row,
            key="nc-list",
        )

    # ------------------------------------------------------------------
    # Assemble the full page
    # ------------------------------------------------------------------

    return Column(
        style=Style(gap=12.0, padding=Edge.all(16.0)),
        children=[
            header,
            status_banner,
            inbox_body,
        ],
    )
```

---

## Rodando o exemplo ▶

### Modo A — Python no browser (Pyodide / WASM)

```bash
tempestweb dev --mode wasm examples/notification-center/app.py
```

O Python roda **dentro do browser** via Pyodide. Sem servidor necessário.

### Modo B — Python no servidor (FastAPI + WebSocket)

```bash
tempestweb dev --mode server examples/notification-center/app.py
```

O Python roda no servidor; o browser recebe patches JSON pelo WebSocket e aplica ao DOM.

!!! check "Verificação"
    Em qualquer modo, você deve ver:

    1. Cabeçalho com **"Notifications"**, badge vermelho **"4"** e botão **"Dismiss all"**
    2. Banner de aviso: *"You have 4 unread notifications."*
    3. Quatro `Banner` coloridos (azul / verde / amarelo / vermelho) com botão **"✕"** em cada um
    4. Clique **"✕"** em qualquer notificação → ela desaparece; o badge atualiza
    5. Clique **"✕"** na última → `EmptyState` aparece; banner vira verde *"All caught up"*
    6. Clique **"Restore notifications"** → lista volta; badge volta para **"4"**
    7. Clique **"Dismiss all"** → transição direta para `EmptyState`

---

## Verificação automatizada ✅

Rode os quatro checks antes de commitar:

```bash
# Lint
ruff check .

# Formatação
ruff format --check .

# Tipos
mypy --strict tempestweb

# Testes
pytest -q
```

Todos devem passar em verde. O exemplo foi projetado para ser `mypy --strict` clean — toda variável, parâmetro e retorno é anotado explicitamente.

---

## Como funciona por dentro

### O ciclo de atualização

```
Clique em "✕" (dismiss_one)
      │
      ▼
app.set_state(mutate)
      │  filtra a lista, troca Phase se vazia
      ▼
tempestweb aplica o mutador → novo estado
      │
      ▼
view(app) chamada novamente → nova árvore de widgets
      │
      ▼
reconciliador calcula diff (patches)
      │
      ▼
DOM atualizado — apenas o Banner removido + Badge + status Banner
```

### LazyColumn vs. Column para listas

| | `Column` | `LazyColumn` |
|---|---|---|
| Quando usar | Listas curtas e estáticas | Listas longas ou dinâmicas |
| Como constrói os filhos | Lista `children` pronta | Callback `item_builder(index)` |
| Custo de build | Todos os filhos na construção da árvore | Apenas os filhos visíveis |

Para uma caixa de entrada real com centenas de notificações, `LazyColumn` é a escolha certa.

### Por que `key` começa com `notif-{n.id}` e não `notif-{index}`?

Se você usasse `key=f"notif-{index}"`, dispensar o item do índice 1 faria o item que era índice 2 virar "índice 1" — o reconciliador interpretaria isso como uma *atualização* do nó existente, não como uma *remoção*. Com `key=f"notif-{n.id}"`, cada notificação tem uma identidade estável baseada no seu `id`, e o reconciliador faz a remoção corretamente.

---

## Recapitulando

Neste tutorial você aprendeu:

- ✅ Modelar **estados de feedback de UI** com uma `StrEnum` de fase (`Phase`)
- ✅ Usar `Badge` para exibir contadores de notificação com tom de cor
- ✅ Usar `Banner` tanto no nível de item quanto no nível agregado da página
- ✅ Usar `EmptyState` para o estado de "caixa de entrada vazia" com ação de restaurar
- ✅ Usar `LazyColumn` com `item_builder` para listas dinâmicas eficientes
- ✅ Capturar valores em closures com o padrão `lambda _nid=n.id: ...`
- ✅ Fazer snapshot da lista antes de entrar no `item_builder` para consistência

---

## Próximos passos

Experimente estender o exemplo:

- 💡 Adicione um campo `timestamp` em `Notification` e mostre a hora relativa ("2 min atrás") em cada Banner
- 💡 Implemente "marcar como lida" (muda `read=True`) sem remover o item — observe o `Badge` diminuir
- 💡 Filtre as notificações por `tone` com um seletor de abas (veja o exemplo [Tabs Profile](./tabs-profile.md))
- 💡 Explore o [Stopwatch](./stopwatch.md) para outro padrão de estado com máquina de fases temporal
- 💡 Leia sobre os [componentes de feedback](../tutorial/index.md) para ver `Snackbar` e `ProgressBar`
