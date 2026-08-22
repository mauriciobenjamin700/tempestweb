# Overlays and modals

A scene is two things: the screen tree and a z-ordered **overlay layer**. Dialogs,
bottom sheets, action sheets, menus, popovers and toasts live in that layer — the
client renders them into their own host above the tree, and the reconciler diffs
both together.

## Opening and closing

The API is imperative, because opening a dialog is an event and not a state
derived from the screen:

```python
from tempest_core import App, Button, Text, Widget
from tempest_core.widgets.overlays import Dialog


def view(app: App[State]) -> Widget:
    """Render a button that opens a dismissable dialog."""

    def close() -> None:
        if app.state.dialog_id is not None:
            app.dismiss(app.state.dialog_id)
            app.set_state(lambda state: setattr(state, "dialog_id", None))

    def open_dialog() -> None:
        dialog = Dialog(
            title="Delete item?",
            children=[
                Text(content="This cannot be undone.", key="body"),
                Button(label="Cancel", on_click=close, key="cancel"),
            ],
            on_dismiss=lambda _event: close(),
        )
        overlay_id = app.show_dialog(dialog, barrier=True)
        app.set_state(lambda state: setattr(state, "dialog_id", overlay_id))

    return Button(label="Delete", on_click=open_dialog, key="delete")
```

* `app.show_dialog` / `app.show_sheet` / `app.show_menu` push an overlay and
  return a **stable id**; keep it so you can call `app.dismiss(id)` later.
* `barrier=True` puts a scrim behind the overlay: it blocks the pointer, and it is
  what makes the overlay *modal*.
* `on_dismiss` fires when the user clicks the scrim or presses `Escape`. The
  overlay does **not** close itself — the app decides, by calling `dismiss`.

!!! warning "With no `on_dismiss`, the scrim is decoration"
    A modal overlay with neither `on_dismiss` nor a close button traps the user:
    the scrim takes the click, the client reports the event, and nobody answers.
    When the widget declares no `on_dismiss` (`ActionSheet` is one such case),
    leave an action that closes it — selecting an item, for instance.

## The keyboard contract

While a modal overlay is open, **the keyboard belongs to it**:

* focus moves to the first control inside the overlay when it opens (or to the
  overlay itself, when it has no controls);
* `Tab` and `Shift+Tab` cycle inside it and wrap at both ends, instead of walking
  the page behind the scrim;
* on close, focus returns to the element that opened the overlay.

You write none of this: the client does it in all three modes. A non-modal overlay
— `Menu`, `Popover`, `Toast` — does not steal focus, because stealing it would
break the widget that opened it.

## Menus with icons

`MenuItem` declares `label`, `value` and `icon`, and the icon resolves through the
same two registries the `Icon` widget uses: a bare name is Lucide, a `material:`
prefix is Material. You can mix them per item.

```python
from tempest_core.widgets.events import MenuSelectEvent
from tempest_core.widgets.overlays import ActionSheet, MenuItem


def open_actions() -> None:
    """Push an action sheet whose items carry icons."""

    def chose(event: MenuSelectEvent) -> None:
        app.set_state(lambda state: setattr(state, "chosen", event.label))
        close_sheet()

    sheet = ActionSheet(
        title="Row actions",
        items=[
            MenuItem(label="Edit", value="edit", icon="material:edit"),
            MenuItem(label="Duplicate", value="duplicate", icon="plus"),
            MenuItem(label="Delete", value="delete", icon="trash"),
        ],
        on_select=chose,
    )
    app.set_state(lambda state: setattr(state, "sheet_id", app.show_sheet(sheet)))
```

The handler receives a `MenuSelectEvent` carrying the clicked item's `value` and
`label`.

!!! tip "An icon name that does not exist will not break the screen"
    An unknown name clears the glyph and keeps the box, so the layout does not
    jump — but it does not warn either. Check the name against the registries
    (`client/icons/`) when an item shows up without its icon.

## Anchored overlays

`Menu` and `Popover` carry the `key` of the widget they anchor to, and the client
places them just below it after layout, clamped into the viewport so a menu opened
near an edge stays reachable:

```python
from tempest_core.widgets.overlays import Menu

Menu(
    key="row-menu",
    anchor="row-42-more",
    items=[MenuItem(label="Rename", value="rename", icon="pencil")],
    on_select=chose,
)
```

## Toast

`Toast` is the overlay that asks nothing of the user: it carries a `message`,
announces itself with `role=status` and `aria-live=polite`, and the app removes it
on a timer.

## Recap

* Overlays live in their own layer; `show_*` returns an id, `dismiss(id)` closes.
* `barrier=True` draws the scrim, which is what makes an overlay modal — and a
  modal with neither `on_dismiss` nor a close button traps the user.
* The keyboard contract (focus in, `Tab` trapped, focus back on close) belongs to
  the client and holds in all three modes; non-modal overlays leave focus alone.
* `MenuItem.icon` takes Lucide (bare name) and Material (`material:`).

The complete example — a dismissable dialog, an action sheet with icons, and focus
walking through all of it — lives in
[`examples/overlay_demo/app.py`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/overlay_demo/app.py):

```bash
tempestweb run --mode server --path examples/overlay_demo
```
