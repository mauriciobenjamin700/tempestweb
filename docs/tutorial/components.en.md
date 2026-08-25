# Ready-made components

You **don't** have to build a login form field by field. tempestweb ships
ready-made, validated, good-looking-by-default components — you write the minimum,
the component does the rest. 🚀

Everything comes from one obvious place:

```python
from tempestweb.components import EmailField, PasswordField, LoginForm, validate_email
```

!!! info "Where the components come from"
    `tempestweb.components` gathers **two** origins under a single import:

    - **From [`tempest-core`](https://pypi.org/project/tempest-core/)** — the
      Material 3 catalog (scaffolds, app bars, navigation, cards, tables, charts,
      etc.). tempestweb **re-exports** those classes without reimplementing them:
      each name is the very class from `tempest_core.components`, so behavior and
      typing match the core.
    - **tempestweb-native** — the higher-level helpers built here: the fields
      (`EmailField`/`PasswordField`/`TextField` + the BR fields), the forms
      (`LoginForm`/`SignupForm`) and the MD3 button builders (`filled_button` and
      friends).

    The **transparent catalog** further down lists **every** item and **where it
    comes from**. The **primitives** (`Column`, `Row`, `Text`, `Button`,
    `Container`, `Input`…) you import straight from `tempest_core`
    (`from tempest_core import Column, Row, Text`).

## Ready-made fields

Each field is **controlled**: pass the current `value` and an `on_change` that
stores the new text; pass `error` to show a validation message.

```python
from tempest_core import App, Column, Widget
from tempestweb.components import EmailField


def view(app: App[State]) -> Widget:
    def set_email(value: str) -> None:
        app.set_state(lambda s: setattr(s, "email", value))

    return Column(
        children=[
            EmailField(
                value=app.state.email,
                on_change=set_email,
                error=app.state.email_error,  # "" when valid
                key="email",
            ),
        ],
    )
```

The available fields:

| Field | For | Validator |
|---|---|---|
| `EmailField` | E-mail (e-mail keyboard, icon) | `validate_email` |
| `PasswordField` | Password (secure field) | — |
| `PhoneField` | Masked BR phone `(99) 99999-9999` | `validate_phone` |
| `CPFField` | Masked CPF | `validate_cpf` |
| `CNPJField` | Masked CNPJ | `validate_cnpj` |
| `AddressField` | Address | — |

!!! tip "Validators return `None` when OK"
    `validate_email("you@example.com")` returns `None`; an invalid value returns
    the error message (a string). Store that string in the field's `error`:

    ```python
    error = validate_email(app.state.email) or ""
    ```

## Who names the field

A field lowers to a `Column` — a **role-less** `<div>` — wrapping an `Input`, and
the caption is a sibling `Text`, **not** a `<label for=…>`. Nothing associates the
two: until 0.113.0 the control was named by whatever the `placeholder` happened to
say. A `PasswordField` has no default placeholder, so it was an anonymous control —
and `LoginForm` shipped that violation (axe `label`, **critical**) to every app
that used it.

Now a field **always** names its control, in this order:

1. the `semantics` you passed;
2. the visible caption.

```python
from tempest_core import App, Column, Row, Semantics, Text, Widget
from tempestweb.components import TextField


def view(app: App[State]) -> Widget:
    """Render one header row over caption-less, named cells."""

    def set_quantity(value: str) -> None:
        app.set_state(lambda s: setattr(s, "quantity", value))

    return Column(
        children=[
            Row(children=[Text(content="Qty."), Text(content="Unit price")]),
            Row(
                children=[
                    TextField(
                        value=app.state.quantity,
                        label="",
                        semantics=Semantics(label="Quantity for item 3"),
                        on_change=set_quantity,
                        key="i3-quantity",
                    ),
                ],
            ),
        ],
    )
```

The name lands on the `<input>`, not on the column around it:

```html
<div data-tw-key="i3-quantity">
  <input aria-label="Quantity for item 3" value="1,200" />
</div>
```

!!! tip "This is what unlocks a grid with one header row"
    A dense grid does not repeat the caption in every cell — twenty items share the
    same eight columns. Without `semantics`, a field with no visible caption has no
    accessible name at all, and a screen-reader user hears "edit box" twenty times.

!!! warning "Not where an `aria-label` would land on its own"
    An `aria-label` on a role-less `<div>` is a **prohibited** attribute
    (`aria-prohibited-attr`) and names an element no reader stops at: the reader
    stops at the control inside it, which would still be anonymous (`label`,
    critical). That is why the field picks the destination instead of forwarding
    as-is.

!!! info "Caption and `semantics` together"
    `semantics` wins — it is what the app said explicitly. Keep the caption's text
    inside it (WCAG 2.5.3, *Label in Name*): `Semantics(label="Quantity for item
    3")` over the caption `Qty.` is fine; a name that does not contain the caption
    leaves voice-control users with no way to address the field.

This holds for `TextField`, `EmailField` and `PasswordField`; `LoginForm` and
`SignupForm` carry `semantics` to the form root, which is where a `role="form"`
belongs.

## A complete login form

`LoginForm` composes email + password + a submit button in **one call**. You only
keep the values in state; the form handles layout, labels and errors.

```python
from dataclasses import dataclass

from tempest_core import App, Column, Text, Widget
from tempestweb.components import LoginForm, validate_email


@dataclass
class LoginState:
    email: str = ""
    password: str = ""
    email_error: str = ""
    status: str = ""


def make_state() -> LoginState:
    return LoginState()


def view(app: App[LoginState]) -> Widget:
    def set_email(value: str) -> None:
        app.set_state(lambda s: setattr(s, "email", value))

    def set_password(value: str) -> None:
        app.set_state(lambda s: setattr(s, "password", value))

    def submit() -> None:
        error = validate_email(app.state.email) or ""

        def commit(s: LoginState) -> None:
            s.email_error = error
            s.status = "" if error else f"Welcome, {s.email}!"

        app.set_state(commit)

    return Column(
        children=[
            LoginForm(
                email=app.state.email,
                password=app.state.password,
                on_email_change=set_email,
                on_password_change=set_password,
                on_submit=submit,
                email_error=app.state.email_error,
                title="Sign in",
            ),
            Text(content=app.state.status, key="status"),
        ],
    )
```

That's it. This is the `examples/login_demo` example — it runs the same in both
modes:

```bash
tempestweb dev --mode wasm     # Python in the browser (Pyodide)
tempestweb dev --mode server   # Python on the server (FastAPI + WebSocket)
```

!!! info "Why controlled?"
    State lives in the `App` (one source of truth), so the form keeps no hidden
    state. You always know what's in the fields — and can pre-fill, clear or
    validate them from outside whenever you want.

## Sign up

`SignupForm` follows the same idea with email + password + confirm-password. Show
the confirm error when the passwords differ:

```python
from tempestweb.components import SignupForm

SignupForm(
    email=app.state.email,
    password=app.state.password,
    confirm=app.state.confirm,
    on_email_change=set_email,
    on_password_change=set_password,
    on_confirm_change=set_confirm,
    on_submit=do_signup,
    confirm_error="" if app.state.password == app.state.confirm else "Passwords do not match",
    title="Create account",
)
```

## Transparent catalog

Here's **what's used and where it comes from**. Everything is imported from
`tempestweb.components`; the **Origin** column says whether the name is
**tempestweb-native** or **re-exported** from
[`tempest-core`](https://pypi.org/project/tempest-core/).

### tempestweb-native

Built in this package (`tempestweb/components/{fields,forms,buttons}.py`):

| Name | What it does | Origin |
|---|---|---|
| `EmailField` · `PasswordField` · `TextField` | Controlled fields styled for Material 3 (built-in label + error). | tempestweb |
| `PhoneField` · `CPFField` · `CNPJField` · `AddressField` | BR fields: wrap the core's masked inputs with validation. | tempestweb |
| `validate_email` · `validate_phone` · `validate_cpf` · `validate_cnpj` | Validators; return `None` when OK, else the error message. | tempestweb |
| `LoginForm` · `SignupForm` | Whole forms in one call (fields + button + errors). | tempestweb |
| `filled_button` · `tonal_button` · `elevated_button` · `outlined_button` · `text_button` | Builders for the 5 MD3 button variants. | tempestweb |

### Re-exported from tempest-core

The core's Material 3 catalog, re-exported without reimplementation. Grouped by
function:

| Group | Components | Origin |
|---|---|---|
| **Layout** | `Grid` · `HStack` · `VStack` · `StyledContainer` · `Surface` · `Scaffold` · `Divider` · `Header` · `Footer` · `Sidebar` | tempest-core |
| **Navigation** | `AppBar` · `CollapsingAppBar` · `NavBar` · `Drawer` · `Burger` · `Breadcrumb` · `Tabs` · `SegmentedControl` · `Stepper` · `ProgressStepper` | tempest-core |
| **Data display** | `Card` · `ListTile` · `Table` · `TableRow` · `TableCell` · `DataTable` · `Avatar` · `Chip` · `Tag` · `Badge` · `Stat` · `StatCard` · `MetricCard` · `Rating` · `Clock` · `Calendar` | tempest-core |
| **Feedback** | `Alert` · `Banner` · `EmptyState` | tempest-core |
| **Disclosure** | `Accordion` | tempest-core |
| **Inputs (low-level)** | `EmailInput` · `PasswordInput` · `PhoneInput` · `AddressInput` · `CPFInput` · `CNPJInput` · `RadioGroup` · `SearchBar` | tempest-core |
| **Media** | `ImagePicker` · `ImagePicture` · `DocumentPicker` | tempest-core |
| **Charts** | `BarChart` · `LineChart` · `ChartSeries` | tempest-core |
| **Vision** | `DetectionBox` · `DetectionOverlay` · `ConfidenceBadge` · `ResultView` · `confidence_scheme` | tempest-core |

!!! check "Two instances of the same component coexist — since tempest-core 0.15.0"
    Every component now derives each child's key from its **own**: the base is the
    `key` you passed (or the component's name, when you pass none), and each child
    becomes `<base>-<role>`. Two `SegmentedControl`s on one screen emit
    `filter-item-0` and `order-item-0`, not `seg-0` twice — and since an event is
    routed **by key**, the click lands on the right control.

    ```python
    SegmentedControl(key="filter", options=["All", "Active"], on_select=set_filter)
    SegmentedControl(key="order", options=["A-Z", "Z-A"], on_select=set_order)
    ```

    It holds for `SegmentedControl`, `RadioGroup`, `Rating`, `NavBar`,
    `Breadcrumb`, `Stepper`, `SearchBar`, `Tabs`, `Accordion`, `Card`, `Grid` and
    the fields — in all three modes.

    !!! warning "Two **unkeyed** ones still collide"
        With no `key`, the base is the component's name (`segmented`), so two
        anonymous instances fight over the name again. Give each a `key=` when a
        screen holds more than one — it is one line, and it is what the
        namespacing uses.

!!! tip "Field vs Input"
    The pair exists on purpose: the **`*Input`** (from the core) is the low-level
    primitive; the **`*Field`** (tempestweb-native, for email/password/BR) is the
    ready-made field — label, error and keyboard already wired. Prefer the `*Field`
    day to day; reach for the `*Input` when you want to lay it out yourself.

An example with a core component:

```python
from tempestweb.components import Card, DataTable, BarChart, ChartSeries

BarChart(series=[ChartSeries(points=[3.0, 7.0, 2.0, 9.0, 5.0], label="sales")])
```

!!! info "Charts draw via Canvas — in both modes"
    `BarChart`/`LineChart` (and detection overlays like `DetectionOverlay`) lower to
    a `Canvas` widget with a draw-command list. The web client executes those
    commands onto a real `<canvas>` — axes, gridlines, bars and lines actually draw,
    no charting library, **identical in Mode A and Mode B**. The value models that
    drive the components (`ChartSeries`, `TableRow`/`TableCell`, `DetectionBox`)
    come along.

!!! note "Vision overlays pair with `[vision]`"
    `DetectionOverlay`/`DetectionBox`/`ConfidenceBadge`/`ResultView` draw a model's
    outputs — they pair with client-side inference from
    [Computer vision (ONNX)](../advanced/vision.md).

## Validating when the reader leaves a field

A form that only validates on submit tells the truth late: the reader finds out
the email is wrong after filling in six more fields. `FormField` declares
`on_validate` for this — the client reports the **occasion** (this field, this
value, please check it) when the control loses focus, and the handler runs the
real validators:

```python
from tempest_core import FormField, Input, Validator
from tempest_core import ValidationEvent

rules: dict[str, list[Validator]] = {"email": [_require("Email is required")]}


def validate_field(event: ValidationEvent) -> None:
    """Run one field's rules when the reader leaves it."""
    message = ""
    for rule in rules.get(event.field, []):
        failed = rule(event.value)
        if failed is not None:
            message = failed
            break
    app.set_state(lambda state: state.errors.update({event.field: message}))


FormField(
    key="field-email",
    name="email",
    label="Email",
    validators=rules["email"],
    error=app.state.errors.get("email", ""),
    on_validate=validate_field,
    child=Input(key="email-input", value=app.state.email, on_change=edit_email),
)
```

Three things worth knowing:

* **`key` and `name` are both required** for this to work: the `key` is what the
  client reports against, and the `name` is what arrives as `event.field`.
* **Validators never cross the wire** — they are Python callables. That is why
  the client reports the occasion instead of trying to validate by itself.
* **`error` is a `str`, not `str | None`**: the empty string means "no error",
  and that is what clears the message.

The error is painted by the base sheet under the control, and the field gets
`aria-invalid`, so the message is announced and not merely displayed.

## One-time codes (`PinInput`)

`PinInput` is the code field: `length` digits, `secure` to mask them, and
`on_complete` firing the moment the last digit lands — no button:

```python
from tempest_core import SubmitEvent
from tempest_core import PinInput


def code_completed(event: SubmitEvent) -> None:
    """Accept the code as soon as its last digit lands."""
    app.set_state(lambda state: setattr(state, "code_done", True))


PinInput(
    key="code-input",
    length=4,
    value=app.state.code,
    on_change=edit_code,
    on_complete=code_completed,
)
```

It renders as **one** `<input>` with `autocomplete="one-time-code"` and
`inputmode="numeric"`, not as four little boxes: that way the browser (and
iOS/Android) offers to fill the code in from an SMS, the numeric keypad comes up
on a phone, and pasting the whole code just works — three things separate boxes
throw away. The base sheet spaces the characters so it still reads as a code
field.

!!! note "`on_complete` fires on the transition"
    It tells you when the field *becomes* full, not on every keystroke after
    that. Clearing it and filling it again arms the next one.

## Recap

- Import from `tempestweb.components` — fields, forms **and** the full core library
  in one place.
- The **transparent catalog** above lists every item and its **origin**
  (tempestweb-native vs re-exported from tempest-core).
- Fields are **controlled**: `value` + `on_change` (+ optional `error`).
- `LoginForm` is a whole form in one call; you just wire it to your state.
- Validators (`validate_email`, `validate_phone`, …) return `None` when OK.
- The core components (incl. `BarChart`/`LineChart` via `Canvas`) render the same
  in Mode A (WASM) and Mode B (server).

!!! info "API reference"
    Every component's signature: [`tempestweb.components`](../reference/components.md).
