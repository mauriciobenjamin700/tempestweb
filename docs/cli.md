# Usando a CLI

!!! abstract "O que você vai aprender"
    A CLI `tempestweb` é o seu painel de controle: **cria** o projeto, **roda** ele
    localmente nos três modos, **builda** o artefato e o **empacota** para produção.
    Esta página segue o caminho de um app do zero ao deploy, um comando por vez. 🚀

A CLI vem no extra `cli`:

```bash
pip install "tempestweb[cli]"        # ou: uv add "tempestweb[cli]"
pip install "tempestweb[server,cli]" # se você também vai rodar o Modo B
```

Confirme que instalou:

```bash
tempestweb --version
# tempestweb 0.52.0
```

!!! tip "`-V` é atalho de `--version`"
    `tempestweb -V` imprime a mesma coisa. E `tempestweb --help` (ou `-h`) mostra
    todos os subcomandos, com um bloco de exemplos no rodapé.

---

## O modelo mental

Antes dos comandos, três ideias que valem para **todos** eles:

1. **Um modo, escolhido na CLI — nunca no app.** O seu `app.py` nunca nomeia um
   modo. Você escolhe `--mode wasm` (A), `--mode server` (B) ou `--mode transpile`
   (C) na hora de rodar/buildar. O mesmo código roda nos três.
2. **`--path` recebe o *diretório* do projeto, nunca um arquivo `.py`.** O default
   é o diretório atual (`.`). A CLI descobre o entrypoint sozinha.
3. **O entrypoint default é `app.py`.** É um módulo Python que expõe **duas**
   callables — `make_state()` (o estado inicial) e `view(app)` (a árvore de
   widgets). O nome é configurável no `tempestweb.toml`.

!!! info "O `tempestweb.toml`"
    Todo campo tem default, então o arquivo é **opcional**. Ele serve para
    **mudar** um default:

    ```toml
    [project]
    name = "todolist"
    entrypoint = "app.py"   # troque para "main.py", "src/app.py", etc.

    [dev]
    mode = "wasm"           # modo default do `dev`
    port = 8000
    ```

    Sem o módulo expor `make_state()` **e** `view(app)`, o build falha com
    `must define a callable make_state/view`.

---

## 1. Criar o projeto — `new`

Não escreva os arquivos na mão. O `new` monta um projeto rodável:

```bash
tempestweb new todolist
cd todolist
```

Isso escreve quatro arquivos — um counter funcional, a config, um README e um
`.gitignore`:

```text
todolist/
├── app.py              # a UI: make_state() + view() — o counter inicial
├── tempestweb.toml     # config do projeto
├── README.md
└── .gitignore
```

Opções úteis:

| Flag | Para quê |
|---|---|
| `--into <dir>` | Cria o projeto **dentro** de outro diretório (default: cwd). |
| `--template <default\|pwa>` | `default` é o counter de dois modos; `pwa` é um PWA instalável/offline (Modo C). |
| `--force` | Escreve num diretório existente não vazio. |
| `--no-verify` | Pula a renderização de prova (mais rápido, menos garantia). |

!!! tip "Template PWA"
    `tempestweb new meuapp --template pwa` já vem com manifest, service worker e o
    esqueleto de offline/WebPush. O `new` te diz o próximo passo no final —
    para o template PWA ele sugere `tempestweb dev --mode transpile`.

---

## 2. Rodar localmente — `dev`

O **`dev` é o comando único de desenvolvimento** — ele bulda **e** serve o app
localmente com hot-reload. E, desde a v0.52, **serve os três modos**:

=== "Modo A (WASM) — default"

    ```bash
    tempestweb dev
    # equivalente a: tempestweb dev --mode wasm
    ```

    Python roda no browser via Pyodide. Salvou um arquivo? O browser recarrega
    sozinho (livereload). Ótimo para iterar na UI sem servidor.

=== "Modo B (servidor)"

    ```bash
    tempestweb dev --mode server
    ```

    Sobe o host FastAPI real sob uvicorn (Python no servidor + cliente fino por
    WebSocket). A cada edição a CLI **faz rebuild e reinicia o servidor**
    automaticamente. Precisa do extra `server`.

=== "Modo C (transpile)"

    ```bash
    tempestweb dev --mode transpile
    ```

    O app é transcrito para JavaScript nativo (sem runtime Python) e servido
    estático com livereload.

Todos abrem em `http://127.0.0.1:8000` por padrão. Sobrescreva com `--host` e
`--port`:

```bash
tempestweb dev --mode server --host 0.0.0.0 --port 9000 --path ./meuapp
```

!!! tip "`dev` para desenvolver, `run` para servir"
    O **`dev` serve todos os modos** com watch + reload — é o comando do dia a dia
    enquanto você escreve código. O **`run`** builda uma vez e serve o app **como
    está, sem watcher** (produção-like) — é o que o Dockerfile gerado pelo
    `tempestweb deploy` executa. Mesmos modos, mesmas flags; só o watcher muda.

!!! check "Feito quando"
    O terminal mostra `Serving at http://127.0.0.1:8000`, você abre no browser e vê
    o counter. Editar `app.py` recarrega a página (A/C) ou reinicia o servidor (B).

---

## 3. Gerar o artefato — `build`

Quando for publicar, o `build` gera o artefato do modo escolhido em
`dist/<modo>/`:

```bash
tempestweb build --mode wasm       # bundle estático Pyodide  → dist/wasm/
tempestweb build --mode transpile  # JS nativo, servível por CDN → dist/transpile/
tempestweb build --mode server     # app FastAPI → dist/server/
```

Opções:

| Flag | Para quê |
|---|---|
| `--path <dir>` | Diretório do projeto (default: cwd). |
| `--out <dir>` | Diretório de saída (default: `<projeto>/dist/<modo>`). |
| `--offline` | (só `wasm`) vendora o runtime Pyodide + wheels para bootar offline. |

!!! note "Modo A offline"
    `tempestweb build --mode wasm --offline` baixa o Pyodide e as wheels no momento
    do build, então o bundle final não depende de CDN em runtime — abre até sem
    rede.

---

## 4. Empacotar para produção — `deploy`

Os modos estáticos (A/C) são só arquivos: publique `dist/` em qualquer CDN. O
**Modo B** precisa de reverse-proxy e TLS — o `deploy` escreve esses arquivos pra
você (nginx + Dockerfile + docker-compose + um `DEPLOY.md`):

```bash
tempestweb deploy --tls --server-name app.exemplo.com
```

Opções:

| Flag | Para quê |
|---|---|
| `--out <dir>` | Onde escrever os arquivos (default: `<projeto>/deploy`). |
| `--server-name <host>` | `server_name` do nginx (seu domínio; default: `_`). |
| `--tls` | Emite bloco TLS (443) + redirect HTTP→HTTPS. |
| `--replicas <n>` | Número de réplicas do app no upstream do nginx (default: 1). |
| `--no-sticky` | Remove `ip_hash` (use com um `RedisSessionRouter` para escalar SSE). |
| `--force` | Sobrescreve arquivos de deploy existentes. |

Depois é só seguir o `DEPLOY.md` gerado. Veja o guia completo em
[Deploy em produção](deploy.md).

---

## 5. Comandos utilitários

### `vapid` — chaves para WebPush

O WebPush (Trilho P) precisa de um par de chaves VAPID. Gere um:

```bash
tempestweb vapid           # imprime public_key / private_key legível
tempestweb vapid --env     # imprime linhas VAPID_PUBLIC_KEY= / VAPID_PRIVATE_KEY=
```

!!! danger "Guarde a chave privada"
    Exporte a privada como `VAPID_PRIVATE_KEY` (secret do servidor) e compartilhe
    só a pública com o cliente. Veja [PWA e offline](pwa.md).

### `sync` — dependências puras no Modo A

O Modo A roda no Pyodide, que não tem seu ambiente completo. O `sync` preenche
`[wasm].modules` no `tempestweb.toml` com as dependências puro-Python instaladas
no projeto, para que sejam empacotadas no bundle:

```bash
tempestweb sync            # escreve tempestweb.toml
tempestweb sync --dry-run  # só mostra o que seria adicionado
```

---

## Referência de subcomandos

Todos os comandos que buldam/servem recebem o **diretório** do projeto via
`--path` (default: diretório atual) — **nunca** um arquivo `.py` posicional.

| Comando | O que faz | Flags principais |
|---|---|---|
| `tempestweb new <nome>` | Scaffold de um projeto rodável. | `--into`, `--template <default\|pwa>`, `--force`, `--no-verify` |
| `tempestweb dev` | **Desenvolve localmente com watch + reload — serve todos os modos.** | `--mode <wasm\|server\|transpile>`, `--path`, `--host`, `--port` |
| `tempestweb build` | Gera o artefato em `dist/<modo>/`. | `--mode`, `--path`, `--out`, `--offline` |
| `tempestweb run` | **Serve o app como buildado, sem watcher (produção-like).** | `--mode`, `--path`, `--host`, `--port`, `--offline` |
| `tempestweb deploy` | Escreve os arquivos de deploy (nginx + Docker + guia). | `--out`, `--server-name`, `--tls`, `--replicas`, `--no-sticky`, `--force` |
| `tempestweb vapid` | Gera um par de chaves VAPID para WebPush. | `--env` |
| `tempestweb sync` | Preenche `[wasm].modules` com as deps puro-Python. | `--path`, `--dry-run` |
| `tempestweb --version` / `-V` | Imprime a versão instalada. | — |

## Recap

- **`new`** cria; **`dev`** desenvolve (os **três** modos, com watch + reload);
  **`run`** serve como buildado (sem watcher, produção-like); **`build`** gera o
  artefato; **`deploy`** empacota o Modo B para produção.
- O modo é escolhido na CLI (`--mode`), nunca no `app.py`.
- `--path` recebe o **diretório**; o entrypoint default é `app.py` (configurável),
  e precisa expor `make_state()` + `view(app)`.

Pronto? Vá para o [Tutorial](tutorial/index.md) e construa o counter. 🚀
