# Manifesto de agentes — build paralelo overnight

Plano de trabalho para **vários agentes em paralelo**, cada um numa **worktree +
branch própria**, commitando incrementalmente. O autor revisa e faz merge depois.

## Princípios

- **Tracks são independentes a nível de arquivo** (dirs/arquivos disjuntos) → rodam
  em paralelo sem conflito de merge.
- Onde um track precisa do runtime de outro, ele **programa contra o contrato**
  (`docs/contract.md` + as interfaces JSDoc/Protocol já no repo) e **mocka/stuba** a
  dependência. A integração real fica para o merge supervisionado.
- Cada track fecha no seu **"feito quando"** com **teste automatizado verde** antes
  de cada commit. O que exigir browser/device real: escreva o código + os testes
  automatizáveis e **marque no commit** o que falta verificar à mão.
- **Não toque** `tempestweb/_core/**` (cópia mecânica) nem arquivos de outro track.
- Commits convencionais, granulares. Linha de co-autoria no final.

## Base

Branch base limpa: **`main`** (fundação já commitada: core vendorado, contrato +
fixtures, esqueleto do pacote, stubs do cliente, harness de teste, CI, Makefile,
docs). Gate global: `make check` (ruff + mypy + pytest + JS jsdom).

## Tracks

| ID | Branch | Dir/arquivos próprios | Escopo (fases do roadmap) | Feito quando | Verificação |
|----|--------|----------------------|---------------------------|--------------|-------------|
| **T1** | `feat/client-render` | `client/dom.js`, `client/style.js`, `client/events.js`, `client/tempestweb.js`, `tests/client/*` | W1 (patches→DOM), W2 (Style→CSS), W3 (eventos), mount com transporte mock | Aplicar `patches_all_kinds.json` sobre o DOM de `node_initial.json` dá o DOM esperado; `style_sample.json`→CSS esperado; click via transporte mock chama `sendEvent` | `node --test "tests/client/**/*.test.js"` verde |
| **T2** | `feat/mode-server` | `tempestweb/server/*`, `tempestweb/transports/websocket.py`, `tempestweb/runtime/session.py`, `client/transport-ws.js`, `tests/unit/test_server*.py` | B0 (host FastAPI+WS), B1 (transporte WS), B2 (sessão/ciclo de vida) | Cliente de teste conecta no WS, recebe patches iniciais, manda evento, recebe patch de update; sessões isoladas por conexão | `pytest tests/unit/test_server*.py` verde (WS via test client) |
| **T3** | `feat/mode-wasm` | `tempestweb/transports/wasm.py`, `tempestweb/runtime/wasm.py`, `client/transport-wasm.js`, `public/index.html` (bootstrap), `tests/unit/test_wasm*.py` | A0 (de-risk Pyodide — **pesquisar estado atual do pydantic-core no Pyodide**), A1 (transporte WASM), A3 (bootstrap/bundle estático) | Bootstrap carrega Pyodide + core vendorado + `app.py` e produz patches no browser; transporte implementa a interface. **A0/A1 ao vivo exigem browser → marcar verificação manual** | `pytest tests/unit/test_wasm*.py` (lógica puramente Python) verde + doc dos passos manuais |
| **T4** | `feat/native-web` | `tempestweb/native/*`, `client/native.js`, `tests/unit/test_native*.py` | A5 (adaptadores Web API: geolocation, clipboard, notifications, storage como awaitables tipados) + esqueleto do split cliente/servidor (B3) | Cada capacidade tem wrapper Python tipado + glue JS; assinaturas awaitable; split documentado | `pytest tests/unit/test_native*.py` verde (mock das Web APIs) |
| **T5** | `feat/cli-devloop` | `tempestweb/cli/*` (exceto `main.py` topo), `tempestweb/devserver/*`, `tests/unit/test_cli*.py` | C (`new` scaffold rodável, `dev` watcher + reload, `build`/`run` dirigindo os dois modos) | `tempestweb new x` cria projeto rodável; `dev` watcher detecta mudança e dispara reload (stub de transporte); `build --mode` gera artefato | `pytest tests/unit/test_cli*.py` verde |
| **T6** | `feat/docs-site` | `docs/**` (exceto os planos já escritos), `mkdocs.yml`, `.github/workflows/docs.yml` | Site MkDocs **bilíngue PT-BR (default) + EN-US** estilo tiangolo/FastAPI: landing, instalação, arquitetura, tutorial progressivo, contrato, referência | `uv run mkdocs build --strict` zero warnings; seletor de idioma; tutorial cobre counter | `mkdocs build --strict` verde |
| **T7** | `feat/conformance` | `tests/conformance/*`, `tests/fixtures/*` (novas fixtures) | D (harness golden A-vs-B): mesma `view()` → mesmo DOM nos dois modos; trava o wire contract | Suite que gera patches do core e fixa o shape; teste que garante que dois transportes mock produzem DOM idêntico | `pytest tests/conformance` verde |
| **T8** | `feat/examples` | `examples/**` (exceto counter), `tests/unit/test_examples.py` | Mais exemplos: todo-list, formulário, fetch async — exercitando a API de widgets do core | Cada exemplo importa, `build(view())` valida e produz árvore; cobre widgets de input/lista/form | `pytest tests/unit/test_examples.py` verde |

## Dependências (para o merge da manhã, não para a execução)

- T3 (wasm) e T2 (server) consomem o cliente real do **T1** na integração. Durante
  a noite ambos programam contra a interface (`client/transport.js`) e stubam.
- T7 (conformance) referencia T1/T2/T3 na integração; à noite trava só o contrato.
- Ordem de merge sugerida: T1 → T2/T3 → T4 → T5/T7/T8 → T6 (docs por último, refletindo
  o que entrou).

## Regra de parada

Cada agente para quando seu "feito quando" está verde e o escopo coberto. **Não
ficar em loop** inventando trabalho fora do track. Se bloquear por uma decisão de
design, registrar num arquivo `NOTES-<ID>.md` na branch e seguir para o próximo
item do track.
