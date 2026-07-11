# Chat UI 💬

Construa uma **interface de chat completa** com lista de mensagens virtualizada,
campo de entrada bidirecional e aviso inline — tudo em Python puro.

Neste tutorial você vai aprender a:

- Usar `LazyColumn` para renderizar uma lista crescente sem penalizar o DOM.
- Conectar um `Input` controlado ao estado via `on_change`.
- Usar um `Button` para acionar mutações de estado.
- Exibir um `Banner` de aviso quando o usuário tenta enviar uma mensagem vazia.

---

## O que você vai construir 🚀

Um chat minimalista com:

- Barra de título com contador de mensagens.
- Lista virtualizada de bolhas de mensagem (usuário à direita, bot à esquerda).
- Compositor com campo de texto e botão **Send**.
- Aviso inline quando o campo está vazio ao clicar em Send.

---

## Pré-requisitos

!!! note "Nota — tutorial base"
    Se você ainda não passou pelo tutorial principal, comece em
    [Introdução](../tutorial/index.md) antes de continuar aqui.

Você precisa do tempestweb instalado:

```bash
pip install tempestweb
```

---

## Estrutura do projeto

Crie a pasta do exemplo:

```bash
mkdir -p examples/chat-ui
touch examples/chat-ui/app.py
```

---

## O código completo

Cole o arquivo abaixo em `examples/chat-ui/app.py`. Cada seção será explicada
em detalhe a seguir.

```python
"""Chat UI — demonstrates LazyColumn message list with an Input + send Button.

A minimal but fully working chat interface. Each message carries a sender label
(``"You"`` vs a simulated ``"Bot"`` reply), a text body and a timestamp. Sending
appends the user message to state, clears the draft, then appends a canned bot
reply so the list always grows — making the virtualized :class:`LazyColumn`
scrolling behaviour obvious with a handful of sends.

An inline :class:`~tempest_core.components.feedback.Banner` acts as a toast
when the user tries to send an empty draft, keeping the demo self-contained and
exercising the feedback component without the overlay API.

Run in either mode unchanged::

    tempestweb dev --mode wasm    # Python in the browser (Pyodide)
    tempestweb run --mode server  # Python on the server (FastAPI + WebSocket)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from tempest_core import App, Style, Widget
from tempest_core.components.base import (
    ACCENT,
    BACKGROUND,
    MUTED,
    ON_MUTED,
    ON_SURFACE,
    SURFACE,
)
from tempest_core.components.feedback import Banner
from tempest_core.style import (
    AlignItems,
    Color,
    Edge,
    FontWeight,
    JustifyContent,
)
from tempest_core.widgets import (
    Button,
    Column,
    Container,
    Input,
    LazyColumn,
    Row,
    Text,
)
from tempest_core.widgets.events import TextChangeEvent

# ---------------------------------------------------------------------------
# Color palette additions specific to this example
# ---------------------------------------------------------------------------

#: Background for the user's own message bubbles.
_USER_BUBBLE: Color = ACCENT

#: Background for the bot's message bubbles.
_BOT_BUBBLE: Color = SURFACE

#: Simulated bot replies cycling in order.
_BOT_REPLIES: list[str] = [
    "Interesting! Tell me more.",
    "Got it. How can I help further?",
    "I see. Let me think about that…",
    "Great point! Anything else?",
    "Thanks for sharing that with me.",
    "Understood. What would you like to do next?",
]


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class Message:
    """A single chat message.

    Attributes:
        sender: Display name of the sender (e.g. ``"You"`` or ``"Bot"``).
        body: The message text.
        timestamp: The human-readable time string (``"HH:MM"``).
    """

    sender: str
    body: str
    timestamp: str


@dataclass
class ChatState:
    """Application state for the Chat UI demo.

    Attributes:
        draft: The text currently typed into the message input.
        messages: All chat messages in chronological order.
        show_empty_warning: Whether to show the "message is empty" banner.
        bot_turn: Index into ``_BOT_REPLIES`` for round-robin bot responses.
    """

    draft: str = ""
    messages: list[Message] = field(default_factory=list)
    show_empty_warning: bool = False
    bot_turn: int = 0


def make_state() -> ChatState:
    """Build the initial state with a seeded conversation.

    Returns:
        A fresh :class:`ChatState` pre-populated with a brief exchange so
        the first mount renders a non-empty :class:`LazyColumn`.
    """
    return ChatState(
        messages=[
            Message(
                sender="Bot",
                body="Hello! How can I help you today?",
                timestamp="09:00",
            ),
            Message(
                sender="You",
                body="Hi! I want to try this chat demo.",
                timestamp="09:01",
            ),
            Message(
                sender="Bot",
                body="Go ahead — type a message below and hit Send!",
                timestamp="09:01",
            ),
        ]
    )


# ---------------------------------------------------------------------------
# View helpers
# ---------------------------------------------------------------------------


def _now_hhmm() -> str:
    """Return the current wall-clock time as ``HH:MM``.

    Returns:
        A two-digit hour, colon and two-digit minute string.
    """
    return datetime.now().strftime("%H:%M")  # noqa: DTZ005


def _bubble(msg: Message, index: int) -> Widget:
    """Build the widget tree for one message bubble.

    User messages are right-aligned with the accent background; bot messages
    are left-aligned with the surface background.

    Args:
        msg: The message to render.
        index: The absolute list index (used for keying children).

    Returns:
        A :class:`Row` that pushes the bubble to the correct side.
    """
    is_user: bool = msg.sender == "You"
    bubble_bg: Color = _USER_BUBBLE if is_user else _BOT_BUBBLE
    align: JustifyContent = JustifyContent.END if is_user else JustifyContent.START

    bubble = Container(
        key=f"bubble-{index}",
        style=Style(
            background=bubble_bg,
            padding=Edge.symmetric(vertical=8.0, horizontal=14.0),
            radius=16.0,
        ),
        child=Column(
            style=Style(gap=4.0),
            children=[
                Text(
                    content=msg.sender,
                    key=f"sender-{index}",
                    style=Style(
                        font_size=11.0,
                        font_weight=FontWeight.BOLD,
                        color=ON_MUTED,
                    ),
                ),
                Text(
                    content=msg.body,
                    key=f"body-{index}",
                    style=Style(font_size=15.0, color=ON_SURFACE),
                ),
                Text(
                    content=msg.timestamp,
                    key=f"ts-{index}",
                    style=Style(font_size=10.0, color=ON_MUTED),
                ),
            ],
        ),
    )

    return Row(
        key=f"row-{index}",
        style=Style(
            justify=align,
            padding=Edge.symmetric(vertical=4.0, horizontal=8.0),
        ),
        children=[bubble],
    )


# ---------------------------------------------------------------------------
# Contract entry-points
# ---------------------------------------------------------------------------


def view(app: App[ChatState]) -> Widget:
    """Render the chat UI from the current state.

    Defines all event handlers as closures over ``app`` so state mutations
    are expressed as pure ``set_state`` calls with no global side-effects.

    Args:
        app: The application handle exposing ``state`` and ``set_state``.

    Returns:
        The full widget tree for the current state.
    """

    def on_draft_change(event: TextChangeEvent) -> None:
        """Update the draft text and clear any empty-message warning.

        Args:
            event: The text-change event carrying the current field value.
        """

        def _set_draft(s: ChatState) -> None:
            s.draft = event.value
            s.show_empty_warning = False

        app.set_state(_set_draft)

    def on_send() -> None:
        """Append the draft as a user message and synthesize a bot reply.

        If the draft is blank after stripping whitespace, shows the empty-
        message warning banner instead of appending.
        """

        def mutate(s: ChatState) -> None:
            text = s.draft.strip()
            if not text:
                s.show_empty_warning = True
                return
            s.show_empty_warning = False
            now = _now_hhmm()
            s.messages.append(Message(sender="You", body=text, timestamp=now))
            reply = _BOT_REPLIES[s.bot_turn % len(_BOT_REPLIES)]
            s.bot_turn += 1
            s.messages.append(Message(sender="Bot", body=reply, timestamp=now))
            s.draft = ""

        app.set_state(mutate)

    def build_message(index: int) -> Widget:
        """Materialize the message bubble at ``index`` for the :class:`LazyColumn`.

        Args:
            index: The absolute index into ``app.state.messages``.

        Returns:
            The bubble row widget for the message at that index.
        """
        return _bubble(app.state.messages[index], index)

    # ------------------------------------------------------------------
    # Build the tree
    # ------------------------------------------------------------------

    state: ChatState = app.state

    children: list[Widget] = []

    # Title bar
    children.append(
        Container(
            key="title-bar",
            style=Style(
                background=SURFACE,
                padding=Edge.symmetric(vertical=14.0, horizontal=16.0),
            ),
            child=Row(
                style=Style(
                    align=AlignItems.CENTER,
                    justify=JustifyContent.SPACE_BETWEEN,
                ),
                children=[
                    Text(
                        content="Chat",
                        key="title-text",
                        style=Style(
                            font_size=20.0,
                            font_weight=FontWeight.BOLD,
                            color=ON_SURFACE,
                        ),
                    ),
                    Text(
                        content=f"{len(state.messages)} messages",
                        key="count-text",
                        style=Style(font_size=13.0, color=ON_MUTED),
                    ),
                ],
            ),
        )
    )

    # Optional empty-draft warning
    if state.show_empty_warning:
        children.append(
            Banner(
                key="empty-warning",
                message="Please type a message before sending.",
                tone="warning",
            )
        )

    # Message list (virtualized)
    children.append(
        LazyColumn(
            key="messages",
            item_count=len(state.messages),
            item_builder=build_message,
            window_size=20,
            style=Style(grow=1.0, background=BACKGROUND),
        )
    )

    # Composer row: Input + Send button
    children.append(
        Container(
            key="composer-wrap",
            style=Style(
                background=SURFACE,
                padding=Edge.all(12.0),
            ),
            child=Row(
                key="composer",
                style=Style(gap=8.0, align=AlignItems.CENTER),
                children=[
                    Input(
                        key="draft-input",
                        value=state.draft,
                        placeholder="Type a message…",
                        on_change=on_draft_change,
                        style=Style(
                            grow=1.0,
                            background=MUTED,
                            color=ON_SURFACE,
                            radius=24.0,
                            padding=Edge.symmetric(vertical=10.0, horizontal=16.0),
                        ),
                    ),
                    Button(
                        key="send-btn",
                        label="Send",
                        on_click=on_send,
                        style=Style(
                            background=ACCENT,
                            color=ON_SURFACE,
                            radius=24.0,
                            padding=Edge.symmetric(vertical=10.0, horizontal=20.0),
                            font_weight=FontWeight.BOLD,
                        ),
                    ),
                ],
            ),
        )
    )

    return Column(
        key="root",
        style=Style(
            background=BACKGROUND,
            gap=0.0,
        ),
        children=children,
    )
```

---

## Rodando o exemplo

=== "Modo WASM (Pyodide)"

    Python roda **dentro do browser** — nenhum servidor necessário.

    ```bash
    tempestweb dev --mode wasm --path examples/chat-ui
    ```

=== "Modo Servidor (FastAPI + WebSocket)"

    Python roda no servidor; o cliente recebe patches via WebSocket.

    ```bash
    tempestweb run --mode server --path examples/chat-ui
    ```

!!! tip "Dica — mesmo código, dois modos"
    O arquivo `app.py` não muda entre os modos. A seam de transporte fica
    inteiramente dentro do framework.

Abra `http://localhost:8000` no browser após o servidor iniciar.

---

## Entendendo o código passo a passo

### 1. Estado da aplicação

```python
@dataclass
class Message:
    sender: str
    body: str
    timestamp: str


@dataclass
class ChatState:
    draft: str = ""
    messages: list[Message] = field(default_factory=list)
    show_empty_warning: bool = False
    bot_turn: int = 0
```

Toda a aplicação vive nesses dois dataclasses.

- `draft` — espelho exato do texto que está no campo `Input`.
- `messages` — a lista crescente de bolhas renderizadas pelo `LazyColumn`.
- `show_empty_warning` — flag booleana que decide se o `Banner` aparece.
- `bot_turn` — índice cíclico para escolher a próxima resposta do bot.

!!! note "Nota — `field(default_factory=list)`"
    Sempre use `field(default_factory=list)` para coleções em dataclasses.
    Usar `messages: list[Message] = []` compartilharia a mesma lista entre
    todas as instâncias — um bug clássico de Python.

---

### 2. Estado inicial com `make_state`

```python
def make_state() -> ChatState:
    return ChatState(
        messages=[
            Message(
                sender="Bot",
                body="Hello! How can I help you today?",
                timestamp="09:00",
            ),
            Message(
                sender="You",
                body="Hi! I want to try this chat demo.",
                timestamp="09:01",
            ),
            Message(
                sender="Bot",
                body="Go ahead — type a message below and hit Send!",
                timestamp="09:01",
            ),
        ]
    )
```

O tempestweb chama `make_state()` uma única vez, no primeiro mount. Pré-popular a
lista garante que o `LazyColumn` renderize algo imediatamente, sem estado vazio.

!!! tip "Dica — sem `make_state`, sem estado inicial"
    Se sua aplicação não precisa de estado inicial com dados, você pode omitir
    `make_state` e o framework usará os defaults do dataclass.

---

### 3. Bolha de mensagem com `_bubble`

```python
def _bubble(msg: Message, index: int) -> Widget:
    is_user: bool = msg.sender == "You"
    bubble_bg: Color = _USER_BUBBLE if is_user else _BOT_BUBBLE
    align: JustifyContent = JustifyContent.END if is_user else JustifyContent.START

    bubble = Container(
        key=f"bubble-{index}",
        style=Style(
            background=bubble_bg,
            padding=Edge.symmetric(vertical=8.0, horizontal=14.0),
            radius=16.0,
        ),
        child=Column(
            style=Style(gap=4.0),
            children=[
                Text(
                    content=msg.sender,
                    key=f"sender-{index}",
                    style=Style(
                        font_size=11.0,
                        font_weight=FontWeight.BOLD,
                        color=ON_MUTED,
                    ),
                ),
                Text(
                    content=msg.body,
                    key=f"body-{index}",
                    style=Style(font_size=15.0, color=ON_SURFACE),
                ),
                Text(
                    content=msg.timestamp,
                    key=f"ts-{index}",
                    style=Style(font_size=10.0, color=ON_MUTED),
                ),
            ],
        ),
    )

    return Row(
        key=f"row-{index}",
        style=Style(
            justify=align,
            padding=Edge.symmetric(vertical=4.0, horizontal=8.0),
        ),
        children=[bubble],
    )
```

Essa função helper transforma um `Message` em árvore de widgets.

- `JustifyContent.END` empurra a bolha do usuário para a direita.
- `JustifyContent.START` mantém a bolha do bot à esquerda.
- As `key`s incluem o `index` — fundamental para que o reconciliador do
  tempestweb identifique cada bolha de forma única na lista.

!!! warning "Aviso — chaves únicas em listas"
    Sempre forneça `key` único para cada filho dentro de um `LazyColumn` ou
    qualquer outro container com filhos dinâmicos. Sem chaves, o reconciliador
    pode reutilizar o nó errado ao aplicar patches.

---

### 4. `LazyColumn` — lista virtualizada

```python
LazyColumn(
    key="messages",
    item_count=len(state.messages),
    item_builder=build_message,
    window_size=20,
    style=Style(grow=1.0, background=BACKGROUND),
)
```

O `LazyColumn` **não materializa todos os itens de uma vez**. Ele recebe:

- `item_count` — quantos itens existem no total.
- `item_builder` — uma função `(index: int) -> Widget` chamada só quando o item
  entra na janela de renderização.
- `window_size` — quantos itens manter materializados simultaneamente.

!!! info "Info — por que virtualizar?"
    Em um chat real com centenas de mensagens, materializar todos os nós no DOM
    seria lento. O `LazyColumn` resolve isso mantendo apenas `window_size` itens
    no DOM por vez, descartando os demais enquanto o usuário rola a lista.

---

### 5. `Input` controlado

```python
Input(
    key="draft-input",
    value=state.draft,
    placeholder="Type a message…",
    on_change=on_draft_change,
    style=Style(
        grow=1.0,
        background=MUTED,
        color=ON_SURFACE,
        radius=24.0,
        padding=Edge.symmetric(vertical=10.0, horizontal=16.0),
    ),
)
```

O `Input` é **controlado**: `value=state.draft` significa que o campo sempre
reflete o estado. O evento `on_change` atualiza o estado a cada tecla digitada:

```python
def on_draft_change(event: TextChangeEvent) -> None:
    def _set_draft(s: ChatState) -> None:
        s.draft = event.value
        s.show_empty_warning = False

    app.set_state(_set_draft)
```

Repare que limpar `show_empty_warning` dentro do mesmo `set_state` é eficiente:
o reconciliador fará um único diff em vez de dois.

---

### 6. Botão Send e a lógica de envio

```python
Button(
    key="send-btn",
    label="Send",
    on_click=on_send,
    style=Style(
        background=ACCENT,
        color=ON_SURFACE,
        radius=24.0,
        padding=Edge.symmetric(vertical=10.0, horizontal=20.0),
        font_weight=FontWeight.BOLD,
    ),
)
```

O handler `on_send` faz três coisas:

1. Verifica se o draft está vazio → exibe `Banner` e retorna.
2. Adiciona a mensagem do usuário e uma resposta do bot à lista.
3. Limpa o draft (`s.draft = ""`).

```python
def on_send() -> None:
    def mutate(s: ChatState) -> None:
        text = s.draft.strip()
        if not text:
            s.show_empty_warning = True
            return
        s.show_empty_warning = False
        now = _now_hhmm()
        s.messages.append(Message(sender="You", body=text, timestamp=now))
        reply = _BOT_REPLIES[s.bot_turn % len(_BOT_REPLIES)]
        s.bot_turn += 1
        s.messages.append(Message(sender="Bot", body=reply, timestamp=now))
        s.draft = ""

    app.set_state(mutate)
```

!!! tip "Dica — mutação via função"
    `app.set_state` recebe uma função `(state) -> None`. Isso garante que a
    mutação seja aplicada sobre o estado mais recente, evitando condições de
    corrida em modo servidor onde múltiplos eventos podem chegar em sequência.

---

### 7. `Banner` de aviso inline

```python
if state.show_empty_warning:
    children.append(
        Banner(
            key="empty-warning",
            message="Please type a message before sending.",
            tone="warning",
        )
    )
```

O `Banner` só é adicionado à árvore quando `show_empty_warning` é `True`. O
reconciliador detecta a inserção/remoção e aplica o patch mínimo ao DOM. Quando
o usuário digita qualquer coisa, `on_draft_change` seta `show_empty_warning =
False` e o banner desaparece sem reload da página.

!!! check "Verificação — o banner some ao digitar"
    Tente clicar em Send com o campo vazio. O banner aparece. Comece a digitar
    qualquer caractere — o banner desaparece imediatamente. ✅

---

## Verificação final ✅

Antes de commitar, rode os quatro checks:

```bash
ruff check .
ruff format --check .
mypy tempestweb
pytest -q
```

Todos devem terminar com zero erros.

---

## Recapitulando

Neste tutorial você viu:

- **`LazyColumn`** virtualiza listas longas via `item_builder` + `window_size`.
- **`Input` controlado** espelha `state.draft` e dispara `on_change` a cada tecla.
- **`Button`** com `on_click` encapsula toda a lógica de envio em `set_state`.
- **`Banner`** aparece e desaparece reativamente via flag booleana no estado.
- **Chaves únicas** são obrigatórias para que o reconciliador faça diffs corretos
  em listas dinâmicas.

---

## Próximos passos

- 💡 Experimente o exemplo [Data Table](./data-table.md) para ver `LazyColumn`
  com dados paginados.
- 💡 Explore o exemplo [Tabs & Profile](./tabs-profile.md) para navegação entre
  seções.
- 📖 Volte ao [Tutorial principal](../tutorial/index.md) para conhecer outros
  widgets.
