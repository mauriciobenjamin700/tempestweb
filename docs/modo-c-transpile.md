# Modo C — Transpile (Python → JavaScript nativo)

> **Status:** spike / Trilho C0. Terceiro modo de execução, ao lado de
> **A (WASM/Pyodide)** e **B (servidor)**. Escreve-se em Python tipado; um
> compilador transcreve a **camada de app** para JavaScript nativo. Zero runtime
> Python no browser, hospedagem estática, first-paint/SEO ótimos — a história
> "TypeScript do Python".

## Por que existe

| | Modo A (WASM) | Modo B (servidor) | **Modo C (transpile)** |
|---|---|---|---|
| Runtime Python | browser (~6 MB Pyodide) | servidor vivo | **nenhum** |
| First paint / SEO | ruim | bom | **ótimo** |
| Hospedagem | estática | servidor + WS/cliente | **estática** |
| Custo de escala | zero servidor | stateful por cliente | **zero servidor** |

Modo C preenche a dor de quem quer o conforto do Python **e** um bundle nativo
pequeno sem servidor. Cada modo atende uma dor — várias vias, um só código de app.

## O insight que torna isso tratável

O cliente JS **já é nativo e agnóstico de modo**: `client/dom.js` (reconciliador/
patcher), `style.js` (Style→CSS), `events.js`, `router.js`, `theme.js`. Modos A/B
só produzem **IR + patches JSON**; o JS renderiza.

Logo, Modo C **não transpila Python inteiro** (nada de Transcrypt/Brython). Reusa
todo o renderer JS e só transcreve a **camada de app**:

1. **classes de estado** (`@dataclass` → `class extends State`);
2. a função **`view(app)`** (construção da árvore IR);
3. os **event handlers** (closures Python → closures JS);
4. **shims JS dos widgets** (`Column`/`Text`/`Button`/…) que espelham os
   construtores do `tempest_core`, devolvendo nós IR no shape do contrato.

O que o core faz em Python (build/reconcile/diff) é reimplementado em JS **uma
vez** e travado contra as mesmas golden fixtures — mesma garantia de conformidade.

## Arquitetura

```
examples/counter/app.py                (Python tipado — autoria)
        │  tempestweb build --mode transpile
        ▼
client/transpile/counter.gen.js        (JS nativo gerado)
        │  import
        ▼
client/transpile/runtime.js  ──uses──▶ client/transpile/diff.js
        │                              client/transpile/widgets.js
        ▼
client/tempestweb.js  mount()  ──▶  client/dom.js (buildElement/applyPatches)
```

O runtime nativo é, em essência, **"Modo A sem Pyodide"**: segura o estado, roda
`view(app)` → IR, faz `diff(old, new)` em JS, entrega patches ao renderer
compartilhado via a mesma interface `Transport` de `client/transport.js`.

### Ciclo de render

1. `mountApp(root, mod)` cria `App(makeState())` e um **transporte nativo**.
2. Render inicial: `node = view(app)`; monta via `mount(root, transport, node)`.
3. Após cada render, o runtime anda a árvore e monta o mapa `key → handler`.
4. Clique → `events.js` manda `{type:"click", key}` → `transport.sendEvent` acha o
   handler por `key` e chama.
5. Handler chama `app.setState(fn)` → muta estado → **re-render**:
   `next = view(app)`; `patches = diff(node, next)`; `transport.onPatches(patches)`;
   `node = next`. Patches **granulares** (Update/Insert/Remove/Reorder/Replace)
   mantêm a árvore DOM estável — sem root-Replace repetido (que quebraria o ref).

## Contrato do `.gen.js` (o que o compilador emite)

Alvo canônico para `examples/counter/app.py`. **O compilador Python DEVE emitir
exatamente este shape**; o runtime JS é construído para rodá-lo.

```js
// counter.gen.js — GENERATED from examples/counter/app.py (Mode C transpile).
import { App, State } from "../runtime.js";
import { Button, Column, Edge, Row, Style, Text } from "../widgets.js";

// @dataclass CounterState: value: int = 0
export class CounterState extends State {
  constructor() {
    super();
    this.value = 0;
  }
}

export function makeState() {
  return new CounterState();
}

export function view(app) {
  const increment = () => {
    app.setState((s) => {
      s.value = s.value + 1;
    });
  };
  const decrement = () => {
    app.setState((s) => {
      s.value = s.value - 1;
    });
  };
  return Column({
    style: Style({ gap: 8.0, padding: Edge.all(16) }),
    children: [
      Text({ content: `Count: ${app.state.value}`, key: "label" }),
      Row({
        style: Style({ gap: 4.0 }),
        children: [
          Button({ label: "-", onClick: decrement, key: "dec" }),
          Button({ label: "+", onClick: increment, key: "inc" }),
        ],
      }),
    ],
  });
}
```

## APIs JS (a construir em `client/transpile/`)

### `widgets.js`
Construtores IR puros. Cada um devolve `{ type, key, props, children }` no shape do
contrato (`docs/contract.md`), com `attrs: {}` e `tag: null` (novos props do core
≥ 0.11). `Button` guarda `onClick` em `props.on_click` (fn) para o runtime coletar;
o renderer ignora props que não conhece.

- `Text({ content, key?, style? })`
- `Column({ children, key?, style? })` / `Row({ children, key?, style? })`
- `Button({ label, onClick?, key?, style? })` — spike: `style` default `null`
  (o `installBaseTheme()` estiliza `<button>` nu). Fidelidade MD3 = fase seguinte.
- `Style(partial)` — preenche o objeto Style completo do contrato com `null` nos
  campos não setados. `Edge.all(n)` → `{ top:n, right:n, bottom:n, left:n }`.

### `diff.js`
`diff(before, after) → Patch[]`, espelhando a semântica do `tempest_core.diff`.
**Travado contra golden fixtures** — ver "Verificação".

### `runtime.js`
- `class State {}` — base das dataclasses transpiladas.
- `class App { constructor(state); get state; setState(mutator) }` —
  `setState(fn)` roda `fn(this.state)` e dispara o re-render do runtime.
- `mountApp(root, { makeState, view }) → MountHandle` — orquestra App + transporte
  nativo + `mount()`. Coleta `key → handler` a cada render; `sendEvent` despacha.

## Verificação (obrigatória)

```bash
# Python
ruff check . && ruff format --check .
mypy tempestweb
pytest -q

# Cliente JS (jsdom)
node --test "tests/client/*.test.js"
```

- **diff.js conformidade:** nova fixture `tests/fixtures/transpile_diff_cases.json`
  derivada do core real (`{before, after, patches}` cobrindo os 5 kinds). O teste
  JS roda `diff(before, after)` e exige igualdade com `patches`. **Derivada do
  core** = mesma garantia das outras goldens; não hand-typar.
- **runtime/widgets:** testes jsdom montam o `counter.gen.js`, checam IR inicial,
  disparam clique, checam patch Update no label e o DOM final.
- **compilador:** teste Python que transpila `examples/counter/app.py` e compara
  byte-a-byte com o `counter.gen.js` commitado (golden regenerável, como as
  fixtures de conformância).
- **Playwright (manual/E2E):** `tempestweb build --mode transpile --path examples/counter`
  → servir estático → montar → clicar +/- → `Count` atualiza, zero erro de console.

## Escopo do spike (C0) e o que fica adiante

**No spike:** counter ponta-a-ponta (state + view + 2 handlers), 4 widgets
(Text/Column/Row/Button), diff JS conforme, runtime nativo, `.gen.js` gerado pelo
compilador, prova no Playwright. **Estilo mínimo/ausente** (botões nus estilizados
pelo base theme).

**Adiante (fases C1+):**
- **C1 — fidelidade de estilo. ✅** (via estratégia **(c)**: introspecção em
  build-time do core instalado → tabela `widget-styles.gen.js`). O gerador
  (`tests/conformance/_transpile_widget_styles.py`) constrói **todo widget
  estilizado** (`buildable_widgets()`, filtrado por `spec.styled`) em cada combo
  dos eixos que ele aceita — variant/field_variant × size × color_scheme — com o
  core real, e grava o `style` resolvido; o builder gerado faz o lookup e mescla o
  `style` explícito por cima (os campos setados do usuário vencem). Paridade MD3
  com A/B travada por golden contra o core, não por inspeção visual.
  **`state_styles` (hover/pressed) é N/A:** o IR não carrega estado de interação —
  os Modos A/B também não aplicam hover/pressed via IR, então a paridade já está
  atingida.
- **Port completo dos widgets. ✅** Todo widget buildável do `tempest_core`
  (`buildable_widgets()` — a lista é derivada, não escrita aqui) tem builder JS
  **gerado por introspecção** (`widgets.gen.js` + `_transpile_widgets.py`), com o
  estilo MD3 resolvido para os que declaram eixos de estilo
  (`widget-styles.gen.js`, eixos variant/field_variant × size × color_scheme,
  normalizados com `"_"`). Handlers stashados num mapa não-wire `__handlers`
  keyed por evento DOM, **derivado da declaração do renderizador**
  (`NATIVE_CONTROL_TYPES`/`CHANGE_REPORTING_TYPES` em `client/dom.js`): um widget
  que o renderizador desenha como controle nativo liga `on_change` a
  `input`/`change`, o resto liga a `click`. A lista era escrita à mão ao lado do
  gerador e driftou — `on_change` de campo mascarado ia para `click`, o campo
  aceitava digitação e nunca avisava a app (#142/#143). Golden tests travam ambos
  os módulos gerados contra o core. **Falta:** eventos exóticos que o cliente
  ainda não emite.
- **Componentes estruturais do core. ✅** Os componentes cuja árvore **não**
  depende dos dados recebidos rodam em Modo C: os aliases `HStack`/`VStack`, as
  superfícies (`Surface`, `StyledContainer`, `Card`, `Scaffold`, `Grid`,
  `Sidebar`, `Drawer`, `Divider`), as barras (`AppBar`, `Header`, `Footer`,
  `NavBar`, `Breadcrumb`, `Burger`, `SegmentedControl`), o conteúdo (`ListTile`,
  `Avatar`, `Chip`, `Tag`, `Rating`, `Stepper`, `SearchBar`, `RadioGroup`), o
  feedback (`Banner`, `Alert`, `Badge`, `EmptyState`, `Stat`, `ProgressStepper`) e
  as composições (`MetricCard`, `StatCard`, `ConfidenceBadge`). Cada composição é
  hand-authored em `components.js` (reescrita do `render()` do core, com as mesmas
  chaves) e o estilo vem de tabela gerada dos resolvedores puros
  (`component-styles.gen.js`), como `widget-styles.gen.js` faz pelos widgets.
  Travados por matriz derivada do core (`transpile_component_samples.json`, um
  caso por eixo que muda o estilo resolvido, comparação order-agnostic via `diff`)
  e exercitados em
  `examples/mode-c-components`. **O que fica fora é o dirigido por dados**
  (`DataTable`/`Table`, `Tabs`, `Accordion`, charts, `DetectionOverlay`,
  `ResultView`, `Calendar`/`Clock`, pickers, `CollapsingAppBar`): a árvore
  depende dos dados, então não há composição fixa para portar sem compilar o
  `render()` do core (projeto separado maior) — acompanhado em
  [#107](https://github.com/mauriciobenjamin700/tempestweb/issues/107).
- **C2 — cobertura do subset. 🚧 em progresso** (o subset cresce; o que fica fora é recusado no build). Expressões: operadores
  aritméticos (`* / %`), comparação (`== != < <= > >=`), booleanos (`and`/`or`),
  unários (`not`/`-`), ternário (`a if c else b`), comprehensions
  (`[e for x in it if c]` → `.filter().map()`), `in`/`not in` → `.includes()`,
  subscript, lambdas de expressão (`lambda s: s.inc()`). Statements: `if`/`elif`/
  `else`, `for … in` → `for…of`, `Assign` (`const`), `AugAssign` (`+=`…).
  **Métodos de state** (classe → métodos JS; `self` → `this`). Novo widget:
  `Container` (layout + escape-hatch `tag`/`attrs`). **f-string com format-spec**
  também entrou (`codegen.py`): `.Nf`, `,`, `,.Nf`, `.N%`, `d` e `,d`.

  **O que falta é o que o compilador recusa** — e ele recusa alto, com
  `arquivo:linha`, em vez de emitir JS que quebra no browser. A lista viva é o
  corpus de exemplos rodado por `tests/transpile/`, categorizado nas issues
  [#110](https://github.com/mauriciobenjamin700/tempestweb/issues/110)–[#117](https://github.com/mauriciobenjamin700/tempestweb/issues/117);
  o zero-padding e os specs de alinhamento/sinal de f-string ficaram em
  [#116](https://github.com/mauriciobenjamin700/tempestweb/issues/116). Não
  repetir a lista aqui é deliberado: ela envelhece a cada release, e o gate é
  quem sabe a verdade.
- **C3 — CLI. ✅ feito.** `tempestweb build --mode transpile <path>` (e
  `run --mode transpile`, que serve o bundle estático como o wasm) transpila o
  `app.py` do projeto para `client/transpile/app.gen.js` e emite um bundle
  estático: `index.html` que monta via `mountApp` + o cliente compartilhado + o
  runtime nativo (diff/widgets/runtime). Zero Python, servível por qualquer CDN.
  Fora do subset → `BuildError` claro. **`dev --mode transpile`** (watch →
  recompila + livereload) também disponível — reusa o devserver estático do
  Modo A; verificado editando `app.py` e vendo o bundle recompilar ao vivo.
- **C4 — erros de subset.** Fora do subset = erro de compilação claro
  (arquivo:linha), no espírito do `mypy --strict`.
- **C5 — diff otimizado + keys**, paridade total com o reconciliador do core.

## Não-objetivos (herdam do CLAUDE.md)

Sem TypeScript. Sem framework JS. Sem transpilador Python genérico (Transcrypt/
Brython) — subset tipado próprio. Sem dependência de runtime além do browser. O
`.gen.js` é ES module puro, sem etapa de bundling obrigatória.
