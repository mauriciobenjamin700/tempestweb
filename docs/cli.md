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
# tempestweb 0.53.2
```

!!! tip "`-V` é atalho de `--version`"
    `tempestweb -V` imprime a mesma coisa. E `tempestweb --help` (ou `-h`) mostra
    todos os subcomandos, com um bloco de exemplos no rodapé.

---

## O modelo mental

Antes dos comandos, três ideias que valem para **todos** eles:

1. **Um modo, escolhido na CLI — nunca no app.** O seu `app.py` nunca nomeia um
   modo. Você escolhe `--mode wasm` (A), `--mode server` (B) ou `--mode transpile`
   (C) na hora de rodar/buildar. O mesmo código roda nos três. **Omitir `--mode`
   usa o `[dev].mode` do `tempestweb.toml`** (e, sem esse campo, `wasm`); um
   `--mode` explícito sobrescreve. Vale para `dev`, `build` e `run`.
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
    mode = "wasm"           # modo usado quando você omite --mode (dev/build/run)
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

!!! tip "Scaffold na pasta atual — `tempestweb new .`"
    Passe `.` como nome para scaffoldar **dentro do diretório atual**, em vez de
    criar um subdiretório:

    ```bash
    mkdir meuapp && cd meuapp
    tempestweb new .
    ```

    O projeto é **nomeado pelo basename do diretório** (aqui, `meuapp`). O `new .`
    **tolera** arquivos pré-existentes não conflitantes (um `.git/`, um `LICENSE`,
    etc.), mas **recusa sobrescrever** os arquivos de scaffold (`app.py`,
    `tempestweb.toml`, `README.md`, `.gitignore`) se algum já existir — passe
    `--force` para sobrescrever mesmo assim.

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
    # sem --mode: usa o [dev].mode do tempestweb.toml (wasm quando não definido)
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

!!! info "`dev` nunca serve cache velho"
    Nos modos estáticos (wasm/transpile) o app é um **PWA com service worker
    cache-first**. Em `dev` isso atrapalharia — você veria o bundle antigo. Por
    isso o `tempestweb dev` **não registra o service worker**: ele injeta um
    *kill-switch* que desregistra qualquer worker existente e limpa os caches, de
    modo que **todo reload serve o build recém-gerado**. O `run`/`build`/`deploy`
    mantêm o service worker cacheador — em produção o cache é o que deixa o app
    rápido no segundo load.

!!! check "Feito quando"
    O terminal mostra `tempestweb dev: serving <app> at http://127.0.0.1:8000
    (mode=wasm); edit a file to reload. Ctrl-C to stop.`, você abre no browser e vê
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

## 6. Qualidade de código

Você escreve **Python tipado** — então a CLI também cuida da qualidade desse
Python. Sete comandos rodam o `ruff`, o `mypy` e o `pytest` **no seu projeto**,
com uma camada de opinião por cima que você pode afrouxar ou apertar. 🚀

!!! warning "Rode do diretório do projeto"
    Como tudo na CLI, esses comandos recebem o **diretório** do projeto via
    `--path` (default: o diretório atual). Rode-os da raiz do seu app — eles
    escopam o ruff/mypy/pytest a esse caminho.

!!! info "Precisa do ruff, mypy e pytest instalados"
    Os comandos **fazem shell-out** para essas ferramentas — não trazem uma cópia
    própria. A CLI prefere o binário no seu `PATH`; se não achar, tenta
    `uv run <tool>`. Instale-os no seu ambiente (`pip install ruff mypy pytest`)
    ou tenha o [uv](https://docs.astral.sh/uv/) no `PATH`.

### Comece pelo gate — `check`

O `check` é o **gate completo**: roda as quatro etapas em sequência e **para no
primeiro erro**, tudo escopado ao `--path` do projeto.

```bash
tempestweb check
```

A ordem é sempre a mesma:

```text
1. ruff check           # lint
2. ruff format --check  # formatação (read-only)
3. mypy                 # tipagem
4. pytest               # testes
```

Antes de cada etapa o `check` ecoa o comando (em stderr) e mostra a saída da
própria ferramenta. Num projeto limpo:

```text
$ ruff check .
All checks passed!
$ ruff format --check .
1 file already formatted
$ mypy .
Success: no issues found in 1 source file
$ pytest .
no tests ran in 0.01s
```

Quando uma etapa falha, o `check` **para ali** (retorna o código de saída dela) —
as seguintes não rodam:

```text
$ ruff check .
All checks passed!
$ ruff format --check .
Would reformat: app.py
1 file would be reformatted
```

!!! note "Sem testes ainda? Tudo bem"
    O `pytest` retorna "nenhum teste coletado" (exit 5) num projeto recém-criado;
    o `check` trata isso como **sucesso**, então o gate passa antes de você
    escrever o primeiro teste.

!!! tip "É o mesmo gate do CI"
    Rode `tempestweb check` antes de cada commit. É a versão de um comando do que a
    esteira de CI faz — se passa localmente, passa lá.

### Os comandos individuais

Quando você quer só uma etapa (ou quer **corrigir**, não só apontar), use os
comandos individuais:

| Comando | Roda | Escreve arquivos? |
|---|---|---|
| `tempestweb lint` | `ruff check` | Não (só reporta) |
| `tempestweb fix` | `ruff check --fix` + `ruff format` | **Sim** |
| `tempestweb format` | `ruff format` | **Sim** |
| `tempestweb fmt-check` | `ruff format --check` | Não (read-only) |
| `tempestweb type` | `mypy` | Não |
| `tempestweb test` | `pytest` | Não |

O fluxo mais comum: aponte com `lint`, corrija com `fix`.

```bash
tempestweb lint            # o que está errado?
tempestweb fix             # conserta o que dá pra consertar automaticamente
```

O `fix` aplica os autofixes **seguros** do ruff e reformata. Para também aplicar
os autofixes marcados como *unsafe* pelo ruff, passe `--unsafe`:

```bash
tempestweb fix --unsafe    # inclui os autofixes unsafe do ruff
```

O `test` filtra os testes pelo `--path`, e trata o **exit code 5** do pytest
("nenhum teste coletado") como **sucesso** — um projeto sem testes ainda não é
um projeto quebrado:

```bash
tempestweb test                    # roda a suíte do projeto
tempestweb test --path ./meuapp    # escopado a um subdiretório
```

!!! note "Exit 5 do pytest = sucesso"
    Se o pytest não encontra nenhum teste (exit 5), o `tempestweb test` (e o
    `tempestweb check`) tratam isso como ✅. Assim o gate não quebra num app que
    ainda não escreveu testes.

### Os três níveis de strictness

`lint`, `fix`, `type` e `check` respeitam um modelo de **strictness** — uma camada
de opinião **por cima** da sua config de ruff/mypy. Ela só **adiciona** regras;
**nunca afrouxa** o que você já configurou.

| Nível | ruff adiciona (`--extend-select`) | mypy adiciona |
|---|---|---|
| `lenient` | nenhuma regra ANN extra | nenhum flag extra |
| `standard` *(default)* | `ANN001`, `ANN201`, `ANN202`, `ANN205`, `ANN206` | `--ignore-missing-imports` |
| `strict` | `ANN001`, `ANN002`, `ANN003`, `ANN201`, `ANN202`, `ANN204`, `ANN205`, `ANN206` | `--strict` |

Em português: o `standard` exige tipos nos parâmetros e nos retornos das funções
públicas; o `strict` cobra também `*args`/`**kwargs` e métodos dunder, e liga o
`mypy --strict`; o `lenient` não adiciona nada — fica só com a sua config.

!!! danger "`Any` é sempre válido — `ANN401` nunca é ligado"
    Nenhum nível liga a regra **`ANN401`** (proibir `typing.Any`). `Any` é uma
    anotação **legítima** — usá-la de propósito é tipar, não deixar de tipar. Você
    escolhe `Any` quando precisa; a CLI nunca vai te punir por isso.

### Configurar o nível — `tempestweb.toml [quality]`

O default é `standard`. Para mudar o nível do projeto inteiro, escreva no
`tempestweb.toml`:

```toml
[quality]
typing_strictness = "standard"   # "lenient" | "standard" | "strict"
```

O `tempestweb new` já escreve esse bloco no `tempestweb.toml` scaffoldado, com
`"standard"`.

Para **uma invocação**, sobrescreva com `--strictness` sem tocar no arquivo:

```bash
tempestweb check --strictness strict     # aperta só nessa rodada
tempestweb lint  --strictness lenient    # afrouxa só nessa rodada
```

!!! check "Feito quando"
    `tempestweb check` sai com código `0` e cada etapa reporta limpo. Esse é o
    mesmo verde que o CI espera — commite com confiança.

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
| `tempestweb lint` | `ruff check` no projeto. | `--path`, `--strictness <lenient\|standard\|strict>` |
| `tempestweb fix` | `ruff check --fix` + `ruff format` (escreve). | `--path`, `--strictness`, `--unsafe` |
| `tempestweb format` | `ruff format` (escreve). | `--path` |
| `tempestweb fmt-check` | `ruff format --check` (read-only). | `--path` |
| `tempestweb type` | `mypy` no projeto. | `--path`, `--strictness` |
| `tempestweb test` | `pytest` (exit 5 = sucesso). | `--path` |
| `tempestweb check` | Gate: `ruff check` → `ruff format --check` → `mypy` → `pytest`. | `--path`, `--strictness` |
| `tempestweb --version` / `-V` | Imprime a versão instalada. | — |

## Recap

- **`new`** cria; **`dev`** desenvolve (os **três** modos, com watch + reload);
  **`run`** serve como buildado (sem watcher, produção-like); **`build`** gera o
  artefato; **`deploy`** empacota o Modo B para produção.
- O modo é escolhido na CLI (`--mode`), nunca no `app.py`.
- `--path` recebe o **diretório**; o entrypoint default é `app.py` (configurável),
  e precisa expor `make_state()` + `view(app)`.
- **`check`** é o gate de qualidade (`ruff check` → `ruff format --check` →
  `mypy` → `pytest`, para no primeiro erro); `lint`/`fix`/`format`/`fmt-check`/
  `type`/`test` são as etapas individuais. O nível `[quality] typing_strictness`
  (lenient/standard/strict, default `standard`) adiciona regras por cima da sua
  config, nunca afrouxa — e **`ANN401` nunca é ligado** (`Any` é válido).

Pronto? Vá para o [Tutorial](tutorial/index.md) e construa o counter. 🚀
