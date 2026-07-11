# Instalação

O tempestweb é publicado no [PyPI](https://pypi.org/project/tempestweb/) —
para **usar** o framework basta um `pip install`. Nenhum passo de build de
frontend: o cliente é JavaScript puro, empacotado pela própria CLI. ✅

!!! tip "Usuário ou contribuidor?"
    - **Só quer usar o tempestweb no seu app?** Fique na seção
      [Instalar do PyPI](#instalar-do-pypi) — é tudo que você precisa.
    - **Quer contribuir com o framework** (rodar o gate, os testes, esta doc)?
      Vá para [Instalação para contribuir](#instalacao-para-contribuir).

## Pré-requisitos

- **Python 3.11+** (o repositório roda em 3.13).

Só isso para usar. O caminho de contribuidor pede também
[uv](https://docs.astral.sh/uv/) e Node.js 18+ — veja
[Instalação para contribuir](#instalacao-para-contribuir).

## Instalar do PyPI

```bash
pip install tempestweb
```

Isso instala o núcleo. As **capacidades extras** são opcionais — instale só o que
seu app usa:

```bash
pip install "tempestweb[server]"          # Modo B (servidor): FastAPI + websockets
pip install "tempestweb[cli]"             # o dev-loop e o empacotador estático
pip install "tempestweb[server,cli]"      # o combo mais comum
pip install "tempestweb[webpush]"         # notificações push (Trilho P)
```

| Extra | Para quê |
|---|---|
| `server` | FastAPI, uvicorn, websockets — o **Modo B** (Python no servidor). |
| `cli` | watchfiles + tomlkit — o dev-loop (`tempestweb dev`) e o `tempestweb sync`. |
| `webpush` | pywebpush + cryptography — Web Push (Trilho P). |

!!! note "Modos A (WASM) e C (transpile) não têm extra Python"
    O **Modo A** roda Python no browser via Pyodide; o **Modo C** transcreve o app
    para JavaScript nativo no build. Nenhum dos dois precisa de um extra Python de
    runtime — o empacotamento estático é feito pela CLI (extra `cli`). Só o
    **Modo B** (servidor) precisa do extra `server`.

!!! tip "Usa `uv`?"
    `uv add tempestweb` (ou `uv add "tempestweb[server,cli]"`) funciona igual e é
    mais rápido, com lockfile reprodutível.

## Criar seu primeiro projeto

Instalou o `cli`? Então **não escreva os arquivos na mão** — a CLI monta um
projeto rodável para você:

```bash
tempestweb new todolist       # cria a pasta todolist/ com um counter funcional
cd todolist
tempestweb dev                # sobe em http://127.0.0.1:8000 com hot-reload
```

O `tempestweb new` escreve quatro arquivos:

```text
todolist/
├── app.py              # a UI: expõe make_state() e view() — o counter inicial
├── tempestweb.toml     # config do projeto (nome, entrypoint, modo/porta padrão)
├── README.md
└── .gitignore
```

!!! question "O arquivo **precisa** se chamar `app.py`?"
    Por padrão, sim — a CLI procura `app.py` na raiz do projeto. Mas o nome é
    **configurável**: o `tempestweb.toml` aponta o entrypoint, então você pode
    renomear.

    ```toml
    [project]
    name = "todolist"
    entrypoint = "app.py"   # troque para "main.py", "src/app.py", etc.
    ```

    O único requisito é que esse módulo exponha **duas** callables: `make_state()`
    (o estado inicial) e `view(app)` (a árvore de widgets). Sem elas o build falha
    com `must define a callable make_state/view`.

!!! tip "Sem `tempestweb.toml`?"
    Funciona mesmo assim — todo campo tem default (`entrypoint = "app.py"`,
    `mode = "wasm"`, porta 8000). O `tempestweb.toml` só é necessário para
    **mudar** um default. Se você criou o projeto na mão com só um `app.py`, o
    `tempestweb build --mode wasm` já roda.

### Comandos da CLI

Todos recebem o **diretório** do projeto via `--path` (padrão: diretório atual) —
nunca um arquivo `.py` posicional.

| Comando | O que faz |
|---|---|
| `tempestweb new <nome>` | Scaffold de um projeto rodável (counter + `tempestweb.toml`). |
| `tempestweb dev --mode <wasm\|server\|transpile>` | Desenvolve localmente com watch + reload — **serve todos os modos**, inclusive o **Modo B (servidor)**. |
| `tempestweb build --mode <wasm\|server\|transpile>` | Gera o artefato em `dist/<modo>/`. |
| `tempestweb run --mode <wasm\|server\|transpile>` | Serve o app **como buildado, sem watcher** (produção-like). |
| `tempestweb sync` | Sincroniza os assets do cliente para dentro do projeto. |
| `tempestweb deploy` | Empacota o artefato para publicação. |
| `tempestweb vapid` | Gera as chaves VAPID para Web Push. |

!!! tip "`dev` para desenvolver, `run` para servir"
    O `tempestweb dev` roda qualquer modo localmente com watch + reload — incluindo
    o **Modo B** (Python no servidor, FastAPI + WebSocket), que faz rebuild e
    reinicia o servidor a cada edição:

    ```bash
    tempestweb dev --mode wasm       # Modo A (default): Python no browser
    tempestweb dev --mode server     # Modo B: FastAPI + uvicorn, restart a cada save
    tempestweb dev --mode transpile  # Modo C: JS nativo, live-reload
    ```

    Já o `tempestweb run` builda uma vez e serve **sem watcher** — o caminho
    produção-like (é o que o Dockerfile do `tempestweb deploy` executa).

Quer o passo a passo completo de cada subcomando? Veja
[Usando a CLI](cli.md). Ou pule direto para o [Tutorial](tutorial/index.md). 🚀

---

## Instalação para contribuir

O resto desta página é para quem vai **desenvolver o próprio tempestweb**: rodar o
gate de qualidade, os testes e construir esta documentação. Para isso o projeto usa
[`uv`](https://docs.astral.sh/uv/) para o ambiente Python e `npm` apenas para o
tooling de teste do cliente JS (jsdom).

### Pré-requisitos de contribuidor

- **Python 3.11+** (o repositório roda em 3.13).
- **[uv](https://docs.astral.sh/uv/)** — instalador e gerenciador de venv.
- **Node.js 18+** — só para `node --test` (jsdom) do cliente.

!!! tip "Por que `uv`?"
    `uv` cria o venv e instala dependências em segundos, com lockfile
    reprodutível (`uv.lock`). É o gerenciador padrão do projeto.

### Clonar e instalar

```bash
git clone https://github.com/mauriciobenjamin700/tempestweb.git
cd tempestweb
make setup
```

O alvo `make setup` faz três coisas:

```bash
uv venv                                  # (1) cria .venv
uv pip install -e ".[dev,server,cli]"    # (2) instala o pacote + extras
npm install                              # (3) tooling de teste JS
```

Aqui a instalação é **editável** (`-e`) e inclui os extras de desenvolvimento
`dev` (ruff, mypy, pytest) e `docs` (mkdocs), além dos extras de runtime
`server` e `cli` já descritos [acima](#instalar-do-pypi).

### Rodar o gate

Antes de qualquer commit, o projeto exige que o gate completo passe:

```bash
make check
```

Isso roda, em sequência:

```bash
ruff check . && ruff format --check .   # lint + formatação (aspas duplas, ANN, D)
mypy tempestweb                         # tipagem estrita
pytest -q                               # testes Python
node --test "tests/client/**/*.test.js" # testes do cliente (jsdom)
```

!!! check "Tudo verde?"
    Se `make check` termina sem erro, seu ambiente está pronto. 🎉

### Construir esta documentação

A documentação é um site MkDocs bilíngue. Para instalar e construir localmente:

```bash
uv pip install -e ".[docs]"
uv run mkdocs build --strict   # falha em QUALQUER warning — esse é o gate
uv run mkdocs serve            # preview local em http://127.0.0.1:8000
```

!!! warning "`mkdocs serve` é só preview local"
    O site publicado vive no **GitHub Pages**, com deploy automático via
    `.github/workflows/docs.yml`. Os links oficiais são
    [a versão PT](https://mauriciobenjamin700.github.io/tempestweb/) e
    [a versão EN](https://mauriciobenjamin700.github.io/tempestweb/en/) — nunca
    `localhost`.

### Recap

- **Usar:** `pip install tempestweb` (mais extras opcionais). Só precisa de Python.
- **Contribuir:** `git clone` + `make setup` cria o venv e instala tudo
  (Python + tooling JS); pede `uv` e Node.
- Extras controlam quais modos/capacidades você habilita.
- `make check` é o gate; `uv run mkdocs build --strict` é o gate da documentação.

Pronto? Siga para a [Arquitetura](architecture.md) ou pule direto para o
[Tutorial](tutorial/index.md). 🚀
