# Galeria de Componentes em Modo C — Zero Python no Browser ⚡

Um app transpilado que exercita **todos os componentes portados** do
`tempest_core`: superfícies, barras, linhas de conteúdo, blocos de feedback e os
interativos. Nenhum Python roda no browser — e a árvore é a mesma que os Modos A e
B constroem.

---

## O que você vai construir

Uma galeria em seções, cada uma com uma família de componentes:

| Seção | Componentes |
|---|---|
| **Superfícies** | `Surface`, `Card`, `Sidebar`, `Drawer`, `Grid`, `StyledContainer` |
| **Barras** | `Header`, `AppBar`, `NavBar`, `Breadcrumb`, `Footer`, `Burger` |
| **Conteúdo** | `ListTile`, `Avatar`, `Tag`, `Chip`, `Badge`, `Divider` |
| **Feedback** | `Alert`, `Banner`, `EmptyState`, `Stat`, `ProgressStepper`, `ConfidenceBadge` |
| **Interativos** | `Rating`, `Stepper`, `SearchBar`, `SegmentedControl`, `RadioGroup` |

!!! tip "Por que este exemplo existe"
    Ele é o artefato que prova o port do Modo C. A composição de cada componente é
    **reescrita à mão** em `client/transpile/components.js` (o `render()` do core
    não pode rodar sem Python) e o estilo vem de tabela gerada a partir do core.
    Uma galeria que renderiza igual nos três modos é a evidência de que a
    reescrita ficou fiel.

---

## Pré-requisitos

```bash
pip install tempestweb
```

Leitura recomendada: [Componentes prontos](../tutorial/components.md) e
[Modo C — transpile](../advanced/transpile.md).

---

## Rodando

```bash
# bundle estático: index.html + o cliente + o app transpilado. Zero Python.
tempestweb build --mode transpile --path examples/mode-c-components

# desenvolvimento com livereload (recompila a cada save)
tempestweb dev --mode transpile --path examples/mode-c-components --port 8000
```

O mesmo `app.py` roda nos outros dois modos sem mudar uma linha:

```bash
tempestweb run --mode server --path examples/mode-c-components --port 8000
tempestweb run --mode wasm   --path examples/mode-c-components --port 8000
```

---

## A regra que este exemplo ensina: dê `key` a cada componente

```python
from tempest_core import Card, Column, Text, Widget


def two_cards() -> Widget:
    """Duas superfícies irmãs, cada uma com a própria chave."""
    return Column(
        key="cards",
        children=[
            Card(key="card-left", children=[Text(content="esquerda", key="left-label")]),
            Card(key="card-right", children=[Text(content="direita", key="right-label")]),
        ],
    )
```

!!! warning "Sem `key`, dois componentes iguais disputam o mesmo nome"
    A chave default de um componente é o **próprio nome**: dois `Card` sob o mesmo
    pai responderiam ambos por `card`. O reconciliador endereça filho por chave, e
    o roteador de evento casa por chave — então duas instâncias sem `key` trocam
    patches e eventos entre si. Cada instância deste exemplo carrega `key`
    explícita por esse motivo.

!!! note "Chave de filho é derivada da chave do pai"
    Desde o `tempest-core` 0.15.0 cada componente deriva a chave dos filhos que
    cria a partir da própria (`faq-3` → `faq-3-item-0`), então duas instâncias na
    mesma tela não colidem mais nos filhos. A `key` do pai continua sendo sua
    responsabilidade.

---

## O que fica fora do Modo C

Componente cuja **árvore depende dos dados** não tem composição fixa para portar
sem compilar o `render()` do core: `DataTable`/`Table`, `Tabs`, `Accordion`, os
gráficos, `DetectionOverlay`, `ResultView`, `Calendar`/`Clock`, os pickers e o
`CollapsingAppBar`. Acompanhado em
[#107](https://github.com/mauriciobenjamin700/tempestweb/issues/107) — nos Modos A
e B todos funcionam.

---

## Recap

* O Modo C entrega os componentes portados com a **mesma árvore** dos Modos A e B,
  travada por matriz de paridade derivada do core.
* A composição é reescrita à mão; o estilo vem de tabela gerada. É por isso que a
  galeria existe: ela é a prova visual do port.
* Dê `key` explícita a cada componente — a default é o nome da classe.
* Componente dirigido por dados fica para depois (#107), e apenas no Modo C.
