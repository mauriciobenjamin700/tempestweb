# Overlays e modais

Uma cena é duas coisas: a árvore da tela e uma **camada de overlay** ordenada por
z-index. Diálogos, bottom sheets, action sheets, menus, popovers e toasts moram
nessa camada — o cliente os renderiza num host próprio, acima da árvore, e o
reconciliador diffa os dois juntos.

## Abrir e fechar

A API é imperativa, porque abrir um diálogo é um evento e não um estado derivado
da tela:

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
            title="Apagar item?",
            children=[
                Text(content="Isso não pode ser desfeito.", key="body"),
                Button(label="Cancelar", on_click=close, key="cancel"),
            ],
            on_dismiss=lambda _event: close(),
        )
        overlay_id = app.show_dialog(dialog, barrier=True)
        app.set_state(lambda state: setattr(state, "dialog_id", overlay_id))

    return Button(label="Apagar", on_click=open_dialog, key="delete")
```

* `app.show_dialog` / `app.show_sheet` / `app.show_menu` empilham um overlay e
  devolvem um **id estável**; guarde-o para depois chamar `app.dismiss(id)`.
* `barrier=True` põe um scrim atrás do overlay: ele bloqueia o ponteiro e é o que
  torna o overlay *modal*.
* `on_dismiss` é chamado quando o usuário clica no scrim ou aperta `Escape`. O
  overlay **não** se fecha sozinho — quem decide é a app, chamando `dismiss`.

!!! warning "Sem `on_dismiss`, o scrim é decoração"
    Um overlay modal sem `on_dismiss` e sem botão de fechar prende o usuário: o
    scrim recebe o clique, o cliente reporta o evento e ninguém responde. Se o
    widget não declara `on_dismiss` (o `ActionSheet` é um caso), deixe uma ação
    que feche — a própria seleção de um item, por exemplo.

## O contrato de teclado

Enquanto um overlay modal está aberto, **o teclado pertence a ele**:

* o foco vai para o primeiro controle dentro do overlay ao abrir (ou para o
  próprio overlay, quando ele não tem controles);
* `Tab` e `Shift+Tab` circulam dentro dele e embrulham nas pontas, em vez de
  passear pela página atrás do scrim;
* ao fechar, o foco volta para o elemento que abriu o overlay.

Você não escreve nada disso: o cliente faz nos três modos. Overlay não-modal —
`Menu`, `Popover`, `Toast` — não rouba o foco, porque roubar quebraria o widget
que o abriu.

## Menus com ícone

`MenuItem` declara `label`, `value` e `icon`, e o ícone é resolvido pelos mesmos
dois registros que o widget `Icon` usa: nome puro é Lucide, prefixo `material:`
é Material. Dá para misturar por item.

```python
from tempest_core.widgets.events import MenuSelectEvent
from tempest_core.widgets.overlays import ActionSheet, MenuItem


def open_actions() -> None:
    """Push an action sheet whose items carry icons."""

    def chose(event: MenuSelectEvent) -> None:
        app.set_state(lambda state: setattr(state, "chosen", event.label))
        close_sheet()

    sheet = ActionSheet(
        title="Ações da linha",
        items=[
            MenuItem(label="Editar", value="edit", icon="material:edit"),
            MenuItem(label="Duplicar", value="duplicate", icon="plus"),
            MenuItem(label="Apagar", value="delete", icon="trash"),
        ],
        on_select=chose,
    )
    app.set_state(lambda state: setattr(state, "sheet_id", app.show_sheet(sheet)))
```

O handler recebe um `MenuSelectEvent` com `value` e `label` do item clicado.

!!! tip "Nome de ícone que não existe não quebra a tela"
    Um nome desconhecido limpa o glifo e mantém a caixa, então o layout não
    pula — mas também não avisa. Confira o nome contra os registros
    (`client/icons/`) quando um item aparecer sem ícone.

## Overlay ancorado

`Menu` e `Popover` carregam a `key` do widget que os ancora, e o cliente os
posiciona logo abaixo dele depois do layout, limitando à viewport para que um
menu aberto na borda continue alcançável:

```python
from tempest_core.widgets.overlays import Menu

Menu(
    key="row-menu",
    anchor="row-42-more",
    items=[MenuItem(label="Renomear", value="rename", icon="pencil")],
    on_select=chose,
)
```

## Toast

`Toast` é o overlay que não pede nada ao usuário: carrega uma `message`, anuncia
a si mesmo com `role=status` e `aria-live=polite`, e a app o remove por timer.

## Recapitulando

* Overlay vive numa camada própria; `show_*` devolve um id, `dismiss(id)` fecha.
* `barrier=True` faz o scrim, que é o que torna o overlay modal — e um modal sem
  `on_dismiss` nem botão de fechar prende o usuário.
* O contrato de teclado (foco entra, `Tab` fica preso, foco volta ao fechar) é do
  cliente e vale nos três modos; overlay não-modal não mexe no foco.
* `MenuItem.icon` aceita Lucide (nome puro) e Material (`material:`).

O exemplo completo — diálogo dismissível, action sheet com ícones e o foco
andando por tudo — está em
[`examples/overlay_demo/app.py`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/examples/overlay_demo/app.py):

```bash
tempestweb run --mode server --path examples/overlay_demo
```
