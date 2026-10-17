# O payload de boot do Modo A

No Modo A, o seu Python roda **dentro do navegador**, no Pyodide. Antes da
primeira pintura, o browser baixa o `tempestweb-pkg.zip`, descompacta no
filesystem virtual do Pyodide e faz `import app`. Esta página mostra as duas
decisões que o `tempestweb build --mode wasm` toma sobre esse zip — e como você
ajusta cada uma no `tempestweb.toml`.

!!! info "Resumo em uma linha"
    Por default, o zip leva **bytecode pré-compilado** para o Python exato do
    Pyodide e **só os subpacotes do `tempestweb` que o seu app alcança**. Os dois
    têm saída segura: sem o Python certo na máquina de build, sai fonte (com
    aviso); se o walk de imports não enxergar algo, você força com `keep`.

## O problema: compilar tudo, em toda visita

O Pyodide liga `sys.dont_write_bytecode`. Na prática, isso quer dizer que **todo
módulo é compilado a partir do fonte em todo carregamento de página** — o
`__pycache__` que o CPython normalmente grava nunca existe ali, e nada sobrevive
a um reload.

Medido no painel do `tempest-webtunnel` (Pyodide v314.0.0, em Node, mesmo zip):
com o zip antigo, **159 módulos do app, do `tempestweb` e do `tempest_core`
passavam pelo compilador** a cada boot. Com o bytecode no zip, **zero**.

## 1. Bytecode no zip — `[wasm] bytecode`

```toml
[wasm]
bytecode = "alongside"   # default
```

| Valor | O que vai no zip | Quando usar |
|---|---|---|
| `"alongside"` (default) | `.py` **e** um `__pycache__/<módulo>.cpython-314.pyc` ao lado | Quase sempre. Traceback com a linha de código, e o boot pula a compilação. |
| `"sourceless"` | Só o `.pyc`, no lugar do `.py` | Quando o tamanho do download pesa mais que o traceback com fonte. |
| `"off"` | Só `.py`, como antes | Para desligar o recurso (e o aviso abaixo). |

O `app.py` é especial: o bootstrap o baixa à parte e grava ao lado do zip, então
o bytecode dele vai como `__pycache__/app.cpython-314.pyc` dentro do zip — e o
importlib do Pyodide o encontra ali.

### Por que é seguro

Um `.pyc` só serve para **um** CPython. O de outra versão é recusado — ou, pior,
lido errado. Então o build não confia em "parece 3.14":

1. O alvo está fixado em `tempestweb.core.constants`: `WASM_PYODIDE_PYTHON =
   "3.14"` e `WASM_PYODIDE_PYC_MAGIC` (o *magic number* lido do próprio runtime
   do Pyodide v314.0.0).
2. O build procura um intérprete com **exatamente esse magic**: o que está
   rodando o build, depois `uv python find 3.14`, depois `python3.14` no `PATH`.
   Uma versão *alpha* do 3.14 tem outro magic e é recusada.
3. Compila em modo **checked-hash** (PEP 552): o Pyodide confere o hash do fonte
   antes de usar o `.pyc`. Se um `app.py` novo chegar com um zip velho (cache),
   o módulo é recompilado em vez de rodar código antigo.
4. Confere o cabeçalho de **todo** `.pyc` escrito. Qualquer divergência descarta
   o bytecode inteiro.

Sem intérprete compatível, o build **não falha**: emite um
`WasmBytecodeWarning` e empacota só o fonte — o app boota igual, só que mais
devagar.

!!! tip "Instalando o Python do Pyodide na máquina de build"
    Se o seu ambiente roda outro Python (3.11, 3.12, 3.13), deixe um 3.14
    disponível para o build achar:

    ```bash
    uv python install 3.14
    tempestweb build --mode wasm
    ```

    O `uv python find` só **procura** — o build nunca baixa um Python sozinho.

!!! note "O `tempestweb dev` não compila"
    O loop de desenvolvimento rebuilda a cada save e prefere ser rápido: ele
    empacota só fonte. O bytecode é coisa de `build`, `run` e `deploy`.

## 2. Só o que o app alcança — `[wasm] trim`

O zip carregava **todo** subpacote do `tempestweb` que roda no browser
(`tabular`, `vision`, `query`, `export`, `access`, ...), importado ou não.
Agora o build faz um walk estático de imports e deixa de fora o que ninguém
alcança.

```toml
[wasm]
trim = true          # default
keep = ["tabular"]   # escape: subpacotes que vão mesmo sem import visível
```

O walk começa em três lugares — o `app.py`, os seus `[wasm] modules` e o
`tempestweb.runtime` (que o bootstrap importa) — e segue cada subpacote
alcançado. Ele conta, de propósito, **mais** do que o Python executa:

- `import` e `from ... import` em **qualquer** lugar do arquivo — dentro de
  função e sob `TYPE_CHECKING` também;
- import relativo (`from ..tabular import x`);
- `tempestweb.html` como atributo;
- string pontilhada, como em `importlib.import_module("tempestweb.transports.sse")`.

Docstring não conta: mencionar `tempestweb.tabular` na documentação não é
importar.

!!! warning "O que o walk não enxerga"
    Um nome de módulo **montado em runtime** — `import_module(f"tempestweb.{nome}")`
    — não aparece em lugar nenhum do fonte. Se o seu app faz isso, diga ao build:
    `keep = ["tabular"]`, ou desligue de vez com `trim = false`. Um nome errado em
    `keep` falha o build com a lista dos válidos, em vez de ser ignorado.

`tempest_core` vai sempre inteiro: o `__init__` dele importa quase tudo na hora,
então cortar arquivo ali quebraria o boot.

## Quanto muda — medido

Painel do `tempest-webtunnel` (`app.py` + o cliente `api/` gerado pelo
`gen api`), `tempestweb build --mode wasm`:

| Zip | Tamanho | Entradas | `.py` | `.pyc` |
|---|---:|---:|---:|---:|
| Antes (tudo, só fonte) | 487 KB | 198 | 197 | 0 |
| `bytecode = "off"`, `trim = true` | 416 KB | 168 | 167 | 0 |
| **Default** (`alongside` + trim) | 1.16 MB | 336 | 167 | 168 |
| `sourceless` + trim | 739 KB | 169 | 0 | 168 |

O trim tirou `access`, `components`, `export`, `query`, `tabular` e `vision`
deste app. O bytecode custa download — `.pyc` comprime pior que fonte —, e em
troca o boot deixa de compilar.

E o tempo do `import app` (o lado Python do boot, depois do zip baixado), no
mesmo Pyodide v314.0.0 rodando em Node num desktop, **10 rodadas intercaladas
por variante** numa máquina carregada — mediana (mínimo):

| Zip | `import app` |
|---|---:|
| Antes | 1454 ms (1267) |
| `off` + trim | 1436 ms (1168) |
| **Default** (`alongside` + trim) | 1247 ms (1068) |
| `sourceless` + trim | 1176 ms (1016) |

Ou seja, **~15–20% do lado Python**. O resto não é compilação: perfilado, cerca
de dois terços do `import app` é o `pydantic` construindo os ~260 models do
`tempest_core` e do app — trabalho que bytecode nenhum evita.

??? info "E o memory snapshot do Pyodide?"
    O Pyodide tem uma API **privada** de snapshot de memória
    (`loadPyodide({ _makeSnapshot: true })` → `makeMemorySnapshot()` →
    `loadPyodide({ _loadSnapshot })`) que pularia o boot do interpretador e os
    imports de uma vez. Testamos na v314.0.0 e **não dá para usar aqui**:

    - qualquer `loadPackage` — inclusive o do `pydantic`, que o core exige —
      deixa estado no lado JS e o `makeMemorySnapshot()` recusa
      (`Unexpected hiwire entry at index 6`);
    - instalando as wheels à mão para contornar, o snapshot sai (36 MB), mas o
      restore falha (`RangeError: offset is out of bounds`): a extensão nativa
      `pydantic_core` é uma biblioteca dinâmica carregada fora da memória que o
      snapshot captura;
    - só um interpretador **sem** extensão nativa restaura (≈30 MB, em ~80 ms) —
      e é justamente o `pydantic` que custa caro no boot.

    Sem o `pydantic` no snapshot não há ganho que pague 30 MB de download, então
    o recurso ficou de fora.

## Recap

- O Pyodide **não guarda** bytecode: sem `.pyc` no zip, todo módulo compila a
  cada visita.
- `[wasm] bytecode` = `"alongside"` (default) · `"sourceless"` · `"off"`. O
  `.pyc` só sai de um intérprete com o **magic exato** do Pyodide fixado; sem
  ele, fonte + `WasmBytecodeWarning`.
- `[wasm] trim = true` (default) deixa de fora os subpacotes que o walk de
  imports não alcança; `keep = [...]` força, `trim = false` desliga.
- O `tempestweb dev` empacota só fonte, para o loop continuar rápido.
