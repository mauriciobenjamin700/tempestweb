# CLAUDE.md — tempestweb

Framework para construir apps **web** escrevendo **Python tipado**. Irmão web do
tempestroid: mesma arquitetura "uma árvore, múltiplos renderizadores", com um
renderizador-folha para o **DOM** e **dois modos de execução** — **A (WASM/
Pyodide)**, Python no browser; **B (servidor)**, Python no servidor + cliente fino
por WebSocket.

> Leia primeiro `docs/plan.md` (design completo), `docs/arquitetura.md` e
> `docs/contract.md` (wire format Python↔cliente). O roadmap fase-a-fase está em
> `docs/roadmap.md`. As tarefas paralelas de agentes estão em
> `docs/agents/MANIFEST.md`.

## Regras estruturais

- **Core vendorado.** `tempestweb/_core/` é uma **cópia mecânica** do core
  renderer-agnostic do tempestroid (IR, reconciliador, estado, estilo, widgets,
  componentes, animation/i18n/navigation/theme/validators). **Não edite à mão** —
  será trocado por uma dependência `tempest-core` depois. Importe dele:
  `from tempestweb._core import App, Column, Text, Button, Style, build, diff`.
- **Uma seam só separa os modos:** `tempestweb/transports/`. Tudo acima (o
  `view()` do app) e abaixo (o cliente JS) é compartilhado. `transports/base.py`
  define o `PatchTransport` Protocol — a fronteira A vs B.
- **Cliente em `client/`** — **JavaScript PURO**. Sem TypeScript, sem framework,
  sem etapa de build. ES modules (`<script type="module">`). É o **mesmo** código
  nos dois modos; só a impl de transporte difere (`transport-wasm.js` vs
  `transport-ws.js`).
- Layout do pacote Python: `transports/`, `runtime/`, `server/` (FastAPI, Modo B),
  `native/`, `devserver/`, `cli/`. `main.py`/CLI: `tempestweb` → `cli.main:main`.

## Convenções (herdam do CLAUDE.md global)

### Python
- Aspas duplas em tudo. Tipagem completa e obrigatória (mypy `--strict`).
- Docstrings Google em **inglês**. Imports de nível de módulo via `__init__.py`
  com `__all__`. Async-first sobre asyncio.
- Coleções vazias retornam `[]`, nunca `*NotFoundError` (404 só p/ recurso único).

### JavaScript (cliente)
- **JS puro, sem TS, sem build, sem framework, sem dependências de runtime** além
  do que o browser oferece (e do Pyodide, no Modo A).
- Aspas duplas. ES modules. **JSDoc** nos contratos públicos (substitui os tipos).
- Programe contra `docs/contract.md` e as fixtures em `tests/fixtures/`.
- Testes obrigatórios via **jsdom** em `tests/client/` (ver "Verificação").

## O contrato (wire format)

Python↔cliente trocam **dados JSON-able**, idêntico nos dois modos. Pinado por
golden fixtures **derivadas do core real** em `tests/fixtures/`:

- `node_initial.json` — IR serializada (`{type, key, props, children}`).
- `patches_all_kinds.json` — os 5 patches (update/insert/remove/reorder/replace).
- `style_sample.json` — objeto `Style` (Color = `{r,g,b,a}`, Edge = `{top,right,bottom,left}`).

Detalhe completo em `docs/contract.md`. **Não mude o shape** sem regenerar as
fixtures a partir do core.

## Verificação (obrigatória por fase)

Toda fase fecha no seu "feito quando" com teste automatizado **verde** antes do
commit. Comandos:

```bash
# Python
ruff check . && ruff format --check .
mypy tempestweb
pytest -q

# Cliente JS (jsdom) — runner standalone, sem framework de build
node --test tests/client/      # usa node:test + jsdom; ver tests/client/README
```

Se uma fase depende de browser/device real (ex.: A2 com Pyodide ao vivo), escreva
o código + os testes que **dá** para automatizar e **marque explicitamente** no
commit o que exige verificação manual. Nunca afirme que algo de UI funciona sem
prova — siga a regra de verificação visual do CLAUDE.md global.

## Git (trabalho paralelo de agentes)

- **Uma worktree por agente/fase** (regra do CLAUDE.md global). Crie a worktree a
  partir da base limpa, commite só os seus arquivos, não troque `HEAD` de outra.
- **Branch por fase:** `feat/<id>-<slug>` (ex.: `feat/w1-dom-patcher`). Convencional
  commits (`feat:`, `fix:`, `ref:`, `docs:`, `tests:`, `chore:`).
- Commite incrementalmente — cada passo verde é um commit. O objetivo é acordar com
  um histórico granular e revisável.
- **Não faça merge na main** nem em branch de outro agente. O autor revisa e
  integra de manhã.
- Termine mensagens de commit com a linha de co-autoria padrão.

## Não-objetivos

Sem TypeScript. Sem framework JS. Sem motor de CSS com cascata (estilo é inline
tipado). Modo A não promete bundle pequeno (quem precisa de SEO/first-paint usa B).
