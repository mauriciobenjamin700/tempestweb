# Instalação

Vamos preparar tudo para rodar o tempestweb localmente. O projeto usa
[`uv`](https://docs.astral.sh/uv/) para o ambiente Python e `npm` apenas para o
tooling de teste do cliente JS (jsdom). Nenhum passo de build de frontend — o
cliente é JavaScript puro. ✅

## Pré-requisitos

- **Python 3.11+** (o repositório roda em 3.13).
- **[uv](https://docs.astral.sh/uv/)** — instalador e gerenciador de venv.
- **Node.js 18+** — só para `node --test` (jsdom) do cliente.

!!! tip "Por que `uv`?"
    `uv` cria o venv e instala dependências em segundos, com lockfile
    reprodutível (`uv.lock`). É o gerenciador padrão do projeto.

## Clonar e instalar

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

Os **extras** dizem quais capacidades você instala:

| Extra | Para quê |
|---|---|
| `dev` | ruff, mypy, pytest — o gate de qualidade. |
| `server` | FastAPI, uvicorn, websockets — o **Modo B**. |
| `cli` | watchfiles + tomlkit — o dev-loop (`tempestweb dev`) e o `tempestweb sync`. |
| `docs` | mkdocs-material + i18n — **esta documentação**. |

!!! note "Modo A (WASM) não tem extra Python"
    O Modo A roda Python no browser via Pyodide; o empacotamento estático é
    feito pela CLI. Você não precisa de um extra Python para ele.

## Rodar o gate

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

## Construir esta documentação

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

## Recap

- `make setup` cria o venv e instala tudo (Python + tooling JS).
- Extras controlam quais modos/capacidades você habilita.
- `make check` é o gate; `uv run mkdocs build --strict` é o gate da documentação.

Pronto? Siga para a [Arquitetura](architecture.md) ou pule direto para o
[Tutorial](tutorial/index.md). 🚀
