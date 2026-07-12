# Componentes prontos

Você **não** precisa montar um formulário de login campo a campo. O tempestweb
traz componentes prontos, validados e bonitos por padrão — você escreve o mínimo,
o componente cuida do resto. 🚀

Tudo vem de um lugar óbvio:

```python
from tempestweb.components import EmailField, PasswordField, LoginForm, validate_email
```

!!! info "De onde vêm os componentes"
    `tempestweb.components` reúne **duas** origens num único import:

    - **Do [`tempest-core`](https://pypi.org/project/tempest-core/)** — o catálogo
      Material 3 (scaffolds, app bars, navegação, cards, tabelas, gráficos, etc.).
      O tempestweb **reexporta** essas classes sem reimplementá-las: cada nome é a
      própria classe do `tempest_core.components`, então comportamento e tipagem
      batem com o core.
    - **Nativos do tempestweb** — os ajudantes de mais alto nível construídos aqui:
      os campos (`EmailField`/`PasswordField`/`TextField` + os campos BR), os
      formulários (`LoginForm`/`SignupForm`) e os construtores de botão MD3
      (`filled_button` e amigos).

    O **catálogo transparente** mais abaixo lista **cada** item e **de onde ele
    vem**. As **primitivas** (`Column`, `Row`, `Text`,
    `Button`, `Container`, `Input`…) você importa direto de `tempest_core`
    (`from tempest_core import Column, Row, Text`).

## Campos prontos

Cada campo é **controlado**: você passa o `value` atual e um `on_change` que guarda
o novo texto; passe `error` para mostrar uma mensagem de validação.

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
                error=app.state.email_error,  # "" quando válido
                key="email",
            ),
        ],
    )
```

Os campos disponíveis:

| Campo | Para quê | Validador |
|---|---|---|
| `EmailField` | E-mail (teclado de e-mail, ícone) | `validate_email` |
| `PasswordField` | Senha (campo seguro) | — |
| `PhoneField` | Telefone BR mascarado `(99) 99999-9999` | `validate_phone` |
| `CPFField` | CPF mascarado | `validate_cpf` |
| `CNPJField` | CNPJ mascarado | `validate_cnpj` |
| `AddressField` | Endereço | — |

!!! tip "Validadores devolvem `None` quando OK"
    `validate_email("você@exemplo.com")` devolve `None`; um valor inválido devolve
    a mensagem de erro (string). Guarde essa string no `error` do campo:

    ```python
    error = validate_email(app.state.email) or ""
    ```

## Formulário de login completo

`LoginForm` compõe e-mail + senha + botão de envio em **uma chamada**. Você só
mantém os valores no estado; o formulário cuida do layout, dos rótulos e dos erros.

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
            s.status = "" if error else f"Bem-vindo, {s.email}!"

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
                title="Entrar",
            ),
            Text(content=app.state.status, key="status"),
        ],
    )
```

É isso. Esse é o exemplo `examples/login_demo` — roda igual nos dois modos:

```bash
tempestweb dev --mode wasm     # Python no browser (Pyodide)
tempestweb dev --mode server   # Python no servidor (FastAPI + WebSocket)
```

!!! info "Por que controlado?"
    O estado vive no `App` (uma fonte de verdade), então o formulário não guarda
    estado escondido. Você sempre sabe o que tem nos campos — e pode pré-preencher,
    limpar ou validar de fora quando quiser.

## Cadastro

`SignupForm` segue a mesma ideia, com e-mail + senha + confirmação de senha. Mostre
o erro de confirmação quando as senhas diferem:

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
    confirm_error="" if app.state.password == app.state.confirm else "As senhas não conferem",
    title="Criar conta",
)
```

## Catálogo transparente

Aqui está **o que é usado e de onde vem**. Tudo é importado de
`tempestweb.components`; a coluna **Origem** diz se o nome é **nativo** do
tempestweb ou **reexportado** do [`tempest-core`](https://pypi.org/project/tempest-core/).

### Nativos do tempestweb

Construídos neste pacote (`tempestweb/components/{fields,forms,buttons}.py`):

| Nome | O que faz | Origem |
|---|---|---|
| `EmailField` · `PasswordField` · `TextField` | Campos controlados estilizados para o Material 3 (label + erro embutidos). | tempestweb |
| `PhoneField` · `CPFField` · `CNPJField` · `AddressField` | Campos BR: envolvem os inputs mascarados do core com validação. | tempestweb |
| `validate_email` · `validate_phone` · `validate_cpf` · `validate_cnpj` | Validadores; devolvem `None` quando OK, senão a mensagem de erro. | tempestweb |
| `LoginForm` · `SignupForm` | Formulários completos numa chamada (campos + botão + erros). | tempestweb |
| `filled_button` · `tonal_button` · `elevated_button` · `outlined_button` · `text_button` | Construtores das 5 variantes de botão MD3. | tempestweb |

### Reexportados do tempest-core

O catálogo Material 3 do core, reexportado sem reimplementação. Agrupado por
função:

| Grupo | Componentes | Origem |
|---|---|---|
| **Layout** | `Grid` · `HStack` · `VStack` · `StyledContainer` · `Surface` · `Scaffold` · `Divider` · `Header` · `Footer` · `Sidebar` | tempest-core |
| **Navegação** | `AppBar` · `CollapsingAppBar` · `NavBar` · `Drawer` · `Burger` · `Breadcrumb` · `Tabs` · `SegmentedControl` · `Stepper` · `ProgressStepper` | tempest-core |
| **Exibição de dados** | `Card` · `ListTile` · `Table` · `TableRow` · `TableCell` · `DataTable` · `Avatar` · `Chip` · `Tag` · `Badge` · `Stat` · `StatCard` · `MetricCard` · `Rating` · `Clock` · `Calendar` | tempest-core |
| **Feedback** | `Alert` · `Banner` · `EmptyState` | tempest-core |
| **Divulgação** | `Accordion` | tempest-core |
| **Inputs (baixo nível)** | `EmailInput` · `PasswordInput` · `PhoneInput` · `AddressInput` · `CPFInput` · `CNPJInput` · `RadioGroup` · `SearchBar` | tempest-core |
| **Mídia** | `ImagePicker` · `ImagePicture` · `DocumentPicker` | tempest-core |
| **Gráficos** | `BarChart` · `LineChart` · `ChartSeries` | tempest-core |
| **Visão** | `DetectionBox` · `DetectionOverlay` · `ConfidenceBadge` · `ResultView` · `confidence_scheme` | tempest-core |

!!! tip "Campo vs Input"
    O par existe de propósito: o **`*Input`** (do core) é a primitiva de baixo nível;
    o **`*Field`** (nativo do tempestweb, para e-mail/senha/BR) é o campo pronto —
    label, erro e teclado já ligados. Prefira o `*Field` no dia a dia; use o
    `*Input` quando quiser montar o layout você mesmo.

Exemplo com um componente do core:

```python
from tempestweb.components import Card, DataTable, BarChart, ChartSeries

BarChart(series=[ChartSeries(points=[3.0, 7.0, 2.0, 9.0, 5.0], label="vendas")])
```

!!! info "Gráficos desenham via Canvas — nos dois modos"
    `BarChart`/`LineChart` (e overlays de detecção como `DetectionOverlay`) baixam
    para um widget `Canvas` com uma lista de comandos de desenho. O cliente web
    executa esses comandos num `<canvas>` real — eixos, gridlines, barras e linhas
    desenham de verdade, sem biblioteca de gráficos, **igual no Modo A e no Modo
    B**. Os modelos de dados que alimentam os componentes (`ChartSeries`,
    `TableRow`/`TableCell`, `DetectionBox`) vêm junto.

!!! note "Overlays de visão pareiam com o `[vision]`"
    `DetectionOverlay`/`DetectionBox`/`ConfidenceBadge`/`ResultView` desenham as
    saídas de um modelo — combinam com a inferência no cliente da
    [Visão computacional (ONNX)](vision.md).

## Recapitulando

- Importe de `tempestweb.components` — campos, formulários **e** a biblioteca
  completa do core num lugar só.
- O **catálogo transparente** acima lista cada item e sua **origem** (nativo do
  tempestweb vs reexportado do tempest-core).
- Campos são **controlados**: `value` + `on_change` (+ `error` opcional).
- `LoginForm` é um formulário inteiro numa chamada; você só liga ao seu estado.
- Validadores (`validate_email`, `validate_phone`, …) devolvem `None` quando OK.
- Os componentes do core (incl. `BarChart`/`LineChart` via `Canvas`) renderizam
  igual no Modo A (WASM) e no Modo B (servidor).
