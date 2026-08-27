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

- `CompactPredictor` — um formato compacto que roda sem runtime de inferência
  nenhum. A medição acima é o argumento a favor dele, e o follow-up é a
  [issue #191](https://github.com/mauriciobenjamin700/tempestweb/issues/191):
  o que pesa é o `onnxruntime-web`, não o `.onnx`.
- A ordem de execution provider **já é configurável** por `providers=`; o que
  ficou decidido é o default, `["wasm"]`, com o número acima.
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
