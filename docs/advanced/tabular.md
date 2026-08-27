# Inferência tabular no browser (`tempestweb.tabular`)

!!! tip "O que você vai aprender"
    A rodar um modelo sklearn **dentro do browser**, sobre uma linha de números —
    score de risco, previsão de demanda, classificação de lead — sem chamar
    endpoint e sem quebrar o offline-first. 🧮

O tempestweb já tinha `vision/`: `Classifier`/`Detector`/`Segmenter` sobre ONNX,
com o modelo rodando no browser. Para dado **tabular** — o caso mais comum de ML
em app de negócio — não havia nada, e a app precisava chamar um endpoint.

## O problema que o manifesto resolve

Um modelo ONNX é uma função de um **vetor de floats sem rótulo** para um número.
A **ordem** carrega todo o significado, e nada no runtime confere:

```python
# ❌ Sem manifesto: isso não falha. Responde um número plausível e errado.
await session.run({"X": [[30.0, 3200.0, 18.0]]})   # idade, renda, tempo? ou renda, idade, tempo?
```

Uma app que manda `{"idade": 30}` para um modelo treinado com `age` lê um zero
onde deveria ler a idade — e nada rio abaixo consegue perceber.

```json
{
  "version": "2026-08-27",
  "features": ["age", "income", "tenure_months"],
  "outputs": ["label", "probabilities"],
  "classes": ["low", "high"]
}
```

Com o manifesto ao lado do `.onnx`, o mesmo erro vira mensagem:

```text
MissingFeatureError: row is missing 1 feature(s): age;
it carries instead: idade
```

!!! info "As duas metades juntas, de propósito"
    A mensagem lista o que **faltou** e o que **veio no lugar**, porque as duas
    quase sempre são um typo só. `age` ausente e `idade` presente é um erro, não
    dois.

## Predizendo

```python
from tempestweb.tabular import TabularPredictor

PREDICTOR = TabularPredictor("/models/risk.onnx", manifest="/models/risk.json")


async def score(row: dict[str, float]) -> float:
    """Devolve a probabilidade da classe prevista."""
    prediction = await PREDICTOR.predict(row)
    return prediction.score
```

A linha vai em **qualquer ordem** — o manifesto impõe a que o modelo precisa:

```python
await PREDICTOR.predict({"tenure_months": 18, "age": 30, "income": 3200.0})
```

Várias linhas de uma vez, numa única execução:

```python
predictions = await PREDICTOR.predict_many(rows)
```

!!! note "O modelo só é baixado na primeira predição"
    Construir um `TabularPredictor` no escopo do módulo **não** baixa nada. Uma
    app que define três preditores e usa um paga por um.

## O passo de export: **`zipmap=False` é obrigatório**

!!! danger "Export padrão do skl2onnx **não roda no browser**"
    O default do `skl2onnx` acrescenta um nó **ZipMap**, e a saída
    `probabilities` deixa de ser tensor para virar `seq(map(int64, float))`. O
    `onnxruntime-web` não lê isso:

    ```text
    Can't access output tensor data on index 1.
    ERROR_MESSAGE: Reading data from non-tensor typed value is not supported.
    ```

    Foi medido aqui, com um export real. Passe `zipmap: False`:

    ```python
    onx = to_onnx(model, X[:1], target_opset=15,
                  options={id(model): {"zipmap": False}})
    ```

    Se esquecer, o `native.onnx` levanta `unsupported_output` **dizendo isso** em
    vez de repetir a mensagem do runtime — o modelo de 539 bytes com ZipMap virou
    389 bytes sem ele, e passou a rodar.

O export inteiro, num ambiente **descartável**:

```bash
uvx --with scikit-learn --with skl2onnx --with numpy --from onnx python export_model.py
```

```python
import json
from pathlib import Path

import numpy as np
from skl2onnx import to_onnx
from sklearn.linear_model import LogisticRegression

X = np.column_stack([age, income, tenure]).astype(np.float32)
model = LogisticRegression(max_iter=2000).fit(X, y)

onx = to_onnx(model, X[:1], target_opset=15,
              options={id(model): {"zipmap": False}})
Path("risk.onnx").write_bytes(onx.SerializeToString())
Path("risk.json").write_text(json.dumps({
    "version": "2026-08-27",
    "features": ["age", "income", "tenure_months"],
    "outputs": ["label", "probabilities"],
    "classes": ["low", "high"],
}))
```

!!! info "Por que `uvx`, e não dependência"
    `sklearn`, `skl2onnx` e `numpy` são pesados e trazem bounds que, num pacote
    publicado, **propagam para todo consumidor** do tempestweb — por um passo que
    acontece uma vez, na máquina de quem treina. Em runtime, nada aqui depende
    deles.

## Medido em Chrome real

Mesmo `.onnx`, mesmo `risk.json`, três linhas, comparado contra o que o
**sklearn responde em Python**:

| Linha | sklearn | Chrome → Python | delta |
| --- | --- | --- | --- |
| `income=2000 tenure=6` | `high` p=0,99999702 | `high` p=0,99999708 | 5,96e-08 |
| `income=9000 tenure=90` | `low` p=1,00000000 | `low` p=1,00000000 | 0 |
| `income=2500 tenure=12` | `low` p=0,66673243 | `low` p=0,66673243 | 0 |

Inferência de 3 linhas: **0,3 ms**. Segunda carga do mesmo modelo: **2,7 ms**,
servida do bucket `tw-assets` do cache de assets.

!!! info "O cache é o que já existe"
    O modelo passa pelo `client/offline/asset-cache.js` — o mesmo do offline —,
    então baixa uma vez por versão e não uma por sessão, e cargas concorrentes da
    mesma URL são deduplicadas. Runtime sem Cache Storage degrada para a URL
    crua: cache frio é mais lento, não quebrado.

## O que pesa não é o modelo — é o runtime

!!! danger "Um modelo de 660 bytes, um runtime de 14 MB"
    O `.onnx` de uma `LogisticRegression` de 30 features tem **660 bytes**. O
    `onnxruntime-web` que o executa tem **13,96 MB** (3,58 MB gzip) no bundle
    mais enxuto. O runtime é **21.000×** o modelo — e é ele que decide se
    inferência tabular cabe no seu artefato, não o modelo.

Export medido (`skl2onnx` com `zipmap=False`, `scikit-learn` sobre
`load_breast_cancer` e `make_classification`):

| Modelo | Features | `.onnx` | gzip |
| --- | --- | --- | --- |
| `LogisticRegression` | 30 | 660 B | 539 B |
| `DecisionTreeClassifier(max_depth=8)` | 30 | 2.167 B | 812 B |
| `GradientBoostingClassifier(n=100)` | 30 | 54.217 B | 7.700 B |
| `RandomForestClassifier(n=100, d=8)` | 30 | 154.013 B | 20.192 B |
| `LogisticRegression`, 3 classes | 120 | 2.259 B | 1.915 B |
| `RandomForestClassifier(n=300, d=12)` | 120 | **14.292.489 B** | 1.623.887 B |

Do lado do runtime, `onnxruntime-web` 1.29.0, medido pelo que o Chrome
**realmente baixa**:

| Bundle carregado por `[wasm].scripts` | JS | WebAssembly | total gzip |
| --- | --- | --- | --- |
| `ort.wasm.min.js` (só CPU) | 50.196 B | `ort-wasm-simd-threaded.wasm` — 13.961.845 B | **3,58 MB** |
| `ort.min.js` (default do pacote) | 368.008 B | `…-threaded.jsep.wasm` — 27.797.172 B | **6,48 MB** |
| `ort.all.min.js` | 819.591 B | `…-threaded.jsep.wasm` — 27.797.172 B | **6,64 MB** |

!!! tip "Carregue `ort.wasm.min.js`, não `ort.min.js`"
    O bundle default da 1.29.0 puxa o WebAssembly **jsep** (WebGPU + WebNN)
    mesmo quando a sessão pede só `executionProviders: ["wasm"]` — foi medido
    aqui, olhando a aba de rede. Trocar por `ort.wasm.min.js` economiza
    **13,8 MB crus / 2,9 MB gzip** sem mudar uma linha de Python. É o que o
    [`[wasm].scripts` das capacidades](capabilities.md#extras-de-build-do-modo-a-wasm)
    já recomenda.

Para dar escala, o mesmo `counter` do tutorial buildado nos dois modos, sem ML
nenhum:

| Artefato | cru | gzip |
| --- | --- | --- |
| Modo A `--offline` (Pyodide + stdlib + pydantic vendorados) | 15,6 MB | 8,4 MB |
| Modo C (transpile) | 1,98 MB | 291 KB |

Ou seja: `ort.wasm.min.js` **+43% no gzip** de um artefato Modo A offline, e
**12× o artefato Modo C inteiro**.

### Provedor: o default `["wasm"]`, com o número que o sustenta

Inferência medida em Chrome real (`onnxruntime-web` 1.29.0, 50 execuções,
mediana e p95, sessão já compilada):

| Modelo | Linhas por execução | mediana | p95 |
| --- | --- | --- | --- |
| `LogisticRegression` 30f | 3 | **0,1 ms** | 0,3 ms |
| `LogisticRegression` 30f | 1.000 | 0,1 ms | 0,3 ms |
| `RandomForest` 100×d8 | 3 | 0,1 ms | 0,1 ms |
| `RandomForest` 100×d8 | 1.000 | 3,4 ms | 3,7 ms |

Criar a sessão custa 225 ms na primeira (o runtime WASM subindo junto) e
2,1–8,3 ms nas seguintes.

!!! info "WebGPU não foi medido aqui — e o default não depende disso"
    O ambiente desta medição (WSL2, Chrome headless) expõe `navigator.gpu` mas
    `requestAdapter()` devolve `null`, e o `onnxruntime-web` recusa com
    `no available backend found. ERR: [webgpu] Failed to get GPU adapter` —
    inclusive com `--enable-unsafe-swiftshader`. O que sustenta manter
    `DEFAULT_PROVIDERS = ["wasm"]` é o outro lado da conta: a EP WebGPU **exige o
    runtime jsep**, que custa 2,9 MB gzip a mais, para acelerar uma inferência
    que já leva **0,1 ms**. Um ganho de 100% ali economiza 0,1 ms e paga com
    megabytes.

    `providers=` continua aceitando a ordem que você quiser — quem roda visão e
    tabular na mesma página já baixou o jsep e pode experimentar sem custo novo.

## Sem runtime nenhum: `CompactPredictor`

Se o runtime é o que pesa, a saída é não ter runtime. Um modelo **linear** é um
produto escalar; uma **árvore** é uma cadeia de comparações. Nada disso precisa
de WebAssembly, e é exatamente o que o `CompactPredictor` lê — em Python de
stdlib (`struct`, `array`, `math`), dentro do Pyodide.

```python
from tempestweb.tabular import CompactPredictor

PREDICTOR = CompactPredictor("./models/risk.tmc")


async def score(row: dict[str, float]) -> float:
    """Devolve a probabilidade da classe prevista."""
    prediction = await PREDICTOR.predict(row)
    return prediction.score
```

Mesma API do `TabularPredictor`: `predict(row)` / `predict_many(rows)`, linha em
qualquer ordem, mesma `Prediction` de volta.

Para o `.tmc` entrar no artefato (e no precache do service worker), declare-o
em `[wasm].assets`:

```toml
[wasm]
assets = ["models/*.tmc"]
```

!!! tip "O arquivo já é o manifesto"
    O export grava `feature_names` e `classes` **dentro** do `.tmc`, então não há
    segundo arquivo para manter em sincronia. `manifest=` existe só para
    sobrescrever um export que não recebeu os nomes.

### O export: um passo de build, com o escritor que verifica

O `.tmc` é escrito pelo `tempest-fastapi-sdk`, que **compara os bytes contra as
predições do próprio scikit-learn e se recusa a escrever um arquivo que
discorde**:

```bash
uvx --with scikit-learn --with tempest-fastapi-sdk python export_compact.py
```

```python
from sklearn.ensemble import RandomForestClassifier
from tempest_fastapi_sdk.modelops import export_sklearn_to_compact

model = RandomForestClassifier(n_estimators=12, max_depth=5).fit(X, y)
export = export_sklearn_to_compact(model, X_test, "dist/risk.tmc", feature_names=list(X.columns))
print(export.kind, export.size_bytes, export.verified)   # tree_ensemble 4764 True
```

!!! warning "É uma troca, não um substituto"
    ONNX cobre **todo** estimador; isto cobre **modelo linear e ensemble de
    árvore** — `LogisticRegression`, `Ridge`, `SGD*`, `LinearSVC`, `Perceptron`,
    `DecisionTree*`, `RandomForest*`, `ExtraTrees*` —, mais um `Pipeline` com
    `StandardScaler`/`MinMaxScaler` na frente (o escalador é **dobrado** no
    header, nunca ignorado). Gradient boosting soma contribuições cruas através
    de um estimador inicial: é outro leitor, e o exportador **recusa** em vez de
    escrever algo que este leria errado. Para esses, o caminho é o
    `TabularPredictor`.

### Medido em Chrome real

Artefato Modo A, Pyodide, sem `onnxruntime-web` em lugar nenhum — um
`RandomForest` de 12 árvores (4.764 B) e uma `LogisticRegression` de 6 features
(460 B):

| Medida | Resultado |
| --- | --- |
| Predição do forest | `setosa` p=**1,00000000** (sklearn: `setosa`, 1,0) |
| Predição do linear | `0` p=**0,99111871** (sklearn: 0,9911187022504708) |
| Frio: download + parse + 1 linha | **6,3 ms** |
| Forest, por linha (100 execuções) | mediana ~0,0 ms · p95 **0,2 ms** |
| Linear, por linha (100 execuções) | mediana ~0,0 ms · p95 **0,1 ms** |
| Forest, 1.000 linhas de uma vez | **51,8 ms** |
| Requests dos modelos, com 200 predições | **1 por modelo** |

!!! check "A paridade é medida contra o sklearn, não contra nós mesmos"
    Os `.tmc` da suíte são escritos pelo **publicador do formato** e ao lado deles
    fica o que o **scikit-learn** respondeu para as mesmas linhas
    (`tests/fixtures/compact/`). A armadilha que isso pega: `sklearn.tree`
    converte a entrada para float32 antes de percorrer, então um limiar
    5.099999904632568 e uma entrada 5.1 comparam **iguais** e vão para a
    esquerda. Comparar em float64 manda a linha para a direita — uma árvore, uma
    linha, um rótulo diferente.

!!! warning "Modos A e B"
    O leitor é Python. Modo C serve um conjunto fechado de módulos e recusa o
    import no build, com a mensagem dizendo qual modo tem a capacidade.

## Erros nomeados

| Situação | Erro |
| --- | --- |
| Feature faltando (ou renomeada) | `MissingFeatureError`, com o que faltou **e** o que veio |
| Feature que o modelo não conhece | `UnknownFeatureError` (desligue com `strict=False`) |
| Manifesto sem features, ou com feature repetida | `ManifestError` |
| Valor que não é número | `ValueError` nomeando a feature |
| Modelo respondeu algo ilegível | `PredictionError` |
| Export com ZipMap | `NativeError("unsupported_output")` dizendo como reexportar |

## Fora de escopo nesta versão

- Gradient boosting no `CompactPredictor` — o exportador recusa, e o caminho é o
  `TabularPredictor`.
- Modo C: o leitor compacto é Python, então segue Modos A e B como o
  `TabularPredictor`.
- Treinar no browser. Isto é inferência.

## Recap

- O **manifesto** é o que impede a predição silenciosamente errada: ele declara
  quais features o modelo espera e **em que ordem**.
- `predict(row)` aceita a linha em qualquer ordem; `predict_many(rows)` roda tudo
  numa execução só.
- **`zipmap=False` no export é obrigatório**, e esquecer dá erro que diz isso.
- Treinar e exportar é passo de build em venv descartável, nunca dependência.
- Medido em Chrome real: idêntico ao sklearn até 6e-08, e **0,1 ms** por
  inferência de 3 linhas.
- **O runtime é que pesa**: 13,96 MB de `onnxruntime-web` para um modelo de
  660 bytes. Carregue `ort.wasm.min.js` e economize 13,8 MB crus.
- **`CompactPredictor` dispensa o runtime** para modelo linear e ensemble de
  árvore: 6,3 ms do frio à primeira predição, p95 de 0,2 ms por linha, e o
  `.tmc` carrega o próprio manifesto.
