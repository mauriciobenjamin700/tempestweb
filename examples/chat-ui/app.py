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
    tempestweb dev --mode server  # Python on the server (FastAPI + WebSocket)
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
