# CLAUDE.md — tempestweb

Framework para construir apps **web** escrevendo **Python tipado**. Irmão web do
tempestroid: mesma arquitetura "uma árvore, múltiplos renderizadores", com um
renderizador-folha para o **DOM** e três modos de execução — **A (WASM/Pyodide)**,
Python no browser; **B (servidor)**, Python no servidor + cliente fino por
WebSocket/SSE; **C (transpile)**, a mesma view compilada para JS.

Herda as regras globais de `~/.claude/CLAUDE.md`. Este arquivo tem o que é
específico deste repo.

## Índice da documentação

Leia o documento antes da tarefa correspondente — não improvise de memória.

| Antes de | Leia |
| --- | --- |
| entender o desenho completo, decisões e trade-offs | `docs/plan.md` |
| mexer em camada, seam ou onde um arquivo mora | `docs/arquitetura.md` · `docs/architecture.md` |
| tocar qualquer coisa que atravesse Python↔cliente | `docs/contract.md` (+ `tests/fixtures/`) |
| saber o que já foi feito e o que vem | `docs/roadmap.md` · `docs/agents/MANIFEST.md` |
| trabalhar no Modo C (transpile) | `docs/advanced/transpile.md` · `docs/modo-c-transpile.md` |
| trabalhar em SSR/HTML estático | `docs/advanced/ssr.md` |
| trabalhar em PWA, offline, WebPush | `docs/advanced/pwa.md` · `docs/advanced/offline-sync.md` |
| trabalhar em capacidade nativa (browser API) | `docs/advanced/capabilities.md` · `.../native-reference.md` · `.../native-events.md` |
| mexer no servidor Modo B (auth, rate limit, sessão) | `docs/advanced/security.md` · `docs/advanced/observability.md` |
| responder "como o usuário faz X?" | `docs/tutorial/` (progressivo: view → state → patches → modos) |
| ver um app inteiro funcionando | `examples/` (56 apps) + `docs/examples/` |
| conferir superfície pública de um módulo | `docs/reference/<módulo>.md` (mkdocstrings) |

Docs são **bilíngues**: `<page>.md` (PT-BR, default) + `<page>.en.md` (EN-US), as
duas no `nav:` e no `nav_translations:` do `mkdocs.yml`. Mudança de superfície
pública, comportamento, install ou versão atualiza README + site no **mesmo
commit**; `mkdocs build --strict` com zero warning.

## Agentes e skill do projeto

| Preciso de | Use |
| --- | --- |
| entender o pedido e planejar até a causa raiz | agente `tw-planner` |
| visual de componente, tema, responsividade | agente `tw-design` |
| revisar a qualidade do que foi escrito (reporta) | agente `tw-code-review` |
| aplicar correções de qualidade mantendo verde | agente `tw-quality` |
| provar que funciona (gate + Chrome real) | agente `tw-validator` · skill `validate-implementation` |
| contestar um "feito" de fase/track | agente `tw-qa` |
| decidir onde o código mora, seams, estrutura | agente `tw-architect` |
| Python (server/transport/runtime/native/cli) | agente `tw-python` |
| cliente JS puro (DOM, style, eventos, SW) | agente `tw-js` |
| site MkDocs bilíngue | agente `tw-docs` |

## Regras estruturais

- **Core = `tempest-core` (centro da verdade).** IR, reconciliador, estado, estilo,
  widgets, componentes, animation/i18n/navigation/theme/validators moram no pacote
  publicado, pinado no `pyproject.toml` — **não neste repo**. Importe direto:
  `from tempest_core import App, Column, Text, Button, Style, build, diff`.
  Precisa mudar o core? Mexa no repo `tempest-core` e suba a versão aqui.
- **Uma seam só separa os modos: `tempestweb/transports/`.** `transports/base.py`
  define o `PatchTransport` Protocol. Tudo acima (o `view()` do app) e abaixo (o
  cliente JS) é compartilhado; detalhe de modo fora de `transports/` é defeito.
- **Cliente em `client/` é JavaScript PURO.** ES modules, sem TypeScript, sem
  framework, sem etapa de build, sem dependência de runtime além do browser (e do
  Pyodide, no Modo A). O mesmo código roda nos três modos; só a impl de transporte
  difere (`transport-wasm.js` · `transport-ws.js` · `transport-sse.js`).
- **Layout Python:** `transports/`, `runtime/`, `server/` (FastAPI, Modo B),
  `html/` (SSR), `transpile/` (Modo C), `native/`, `observability/`, `pwa/`,
  `presets/`, `components/`, `vision/`, `devserver/`, `cli/`. Pacote publicado é
  **flat**: `tempestweb/` na raiz, sem `src/`.
- **Handler nunca atravessa o fio.** O cliente reporta evento por `key`; o Python
  resolve o callable vivo (`EVENT_TYPE_TO_HANDLER_PROPS`, com fallback
  `on_<type>`). Patch path endereça a árvore, então **filho criado pelo
  renderizador só é legal dentro de folha da IR** (fill do ProgressBar, spinner do
  RefreshControl, itens de Menu) — injetar filho em container corrompe os paths.
- **Módulo novo em `client/` entra em `_CLIENT_ASSETS`** (`tempestweb/cli/commands/
  build.py`), senão ele simplesmente não existe no app buildado — e nada falha
  alto.

## O contrato (wire format)

Python↔cliente trocam **dados JSON-able**, idêntico nos três modos, pinado por
golden fixtures derivadas do core real em `tests/fixtures/`:

- `node_initial.json` — IR serializada (`{type, key, props, children}`).
- `patches_all_kinds.json` — os 5 patches (update/insert/remove/reorder/replace).
- `style_sample.json` — `Style` (Color `{r,g,b,a}`, Edge `{top,right,bottom,left}`).

Detalhe em `docs/contract.md`. **Não mude o shape** sem regenerar as fixtures a
partir do core — e trate isso como decisão de compatibilidade, não refactor.

## Convenções

### Python
- Aspas duplas. Tipagem completa (mypy `--strict`). Docstring Google em **inglês**
  em toda função, método e classe.
- **Zero comentário inline** — o porquê vive na docstring (exceção: pragma de
  máquina). Import absoluto de nível de módulo, com `__init__.py` re-exportando e
  `__all__` em dia (pacote publicado usa `from x import Y as Y` **e** `__all__`).
- Async-first. Coleção vazia é sucesso (`[]`, nunca `*NotFoundError`).
- `**kwargs` é só passthrough: `kwargs.pop("x")` significa que `x` deve ser
  parâmetro keyword-only nomeado.

### JavaScript (cliente)
- Aspas duplas, ES modules, **JSDoc** nos contratos públicos (substitui os tipos).
- Zero comentário inline explicativo dentro de função — vai para o JSDoc.
- Programe contra `docs/contract.md` e as fixtures. Delegação de evento na raiz.
- Estado visual é atributo (`data-tw-*`) lido pela folha base, não style inline:
  o Style inline da app sempre ganha do stylesheet, e o tema base é piso, não gaiola.

## Verificação (obrigatória por fase)

```bash
uv sync --all-extras                      # use as versões do lock, como a CI
uv run --frozen ruff check . && uv run --frozen ruff format --check .
uv run --frozen mypy tempestweb
uv run --frozen pytest -q
node --test "tests/client/*.test.js"      # jsdom; a forma com diretório quebra no Node 24+
uv run --frozen --extra docs mkdocs build --strict   # quando tocar docs
```

Mudança que afeta **UI renderizada** (CSS, layout, componente, tema, gesto,
responsividade) fecha na skill **`validate-implementation`**: gate + Chrome real
(Chrome DevTools MCP + Playwright MCP), input de verdade, dois viewports, console
limpo, e **evidência medida** no relatório. Type-check e lint verificam código,
não pixel. MCP indisponível: diga isso explicitamente em vez de afirmar que
funciona.

Armadilhas já pagas neste repo:

- `tempestweb run` copia `client/*.js` para `dist/` no boot — editar depois não
  muda a página; reinicie e confira o artefato.
- Todo artefato registra service worker: **limpe SW e caches antes de medir**, ou
  você valida o build anterior (ou outro app, numa porta reusada).
- O CSS base vive dentro de template literal em `client/theme.js`: **backtick em
  comentário quebra o módulo**.
- Um viewport lazy é flex container; pseudo-elemento de spacer precisa de
  `flex:0 0 auto` ou o browser o encolhe.
- Scroll e gesto são **fluxo** de eventos: reportar posição intermediária faz a
  app desfazer o próprio movimento. Reporte quando assentar.
- Widget do core ignora kwarg que não declara (`Container(on_click=...)` é aceito
  e descartado). Confira o campo em `model_fields` antes de culpar o cliente.

## Git

- Uma **worktree por agente/tarefa**, criada de base limpa; commite só os seus
  arquivos; remova a worktree e a branch quando a task for mergeada.
- Branch por fase: `feat/<id>-<slug>`, `fix/`, `ref/`. Conventional commits
  (`feat:`, `fix:`, `ref:`, `docs:`, `tests:`, `chore:`), assunto em PT-BR.
- Commite incrementalmente — cada passo verde é um commit.
- **Não faça merge na `main`** nem em branch de outro agente: o autor revisa e
  integra. Keyword de fechamento de issue só em inglês (`Closes #148`).
- Toda mudança que toca código entregue: bump de versão + entrada no
  `CHANGELOG.md`. Mudança docs-only não bumpa nem ganha tag.
- Termine mensagens de commit com a linha de co-autoria padrão.

## Não-objetivos

Sem TypeScript. Sem framework JS. Sem motor de CSS com cascata (estilo é inline
tipado + folha base por atributo). Modo A não promete bundle pequeno — quem
precisa de SEO/first-paint usa B ou SSR.
