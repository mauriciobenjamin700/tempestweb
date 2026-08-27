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

- `CompactPredictor` e a ordem configurável de execution provider — follow-up.
- Treinar no browser. Isto é inferência.

## Recap

- O **manifesto** é o que impede a predição silenciosamente errada: ele declara
  quais features o modelo espera e **em que ordem**.
- `predict(row)` aceita a linha em qualquer ordem; `predict_many(rows)` roda tudo
  numa execução só.
- **`zipmap=False` no export é obrigatório**, e esquecer dá erro que diz isso.
- Treinar e exportar é passo de build em venv descartável, nunca dependência.
- Medido em Chrome real: idêntico ao sklearn até 6e-08.
