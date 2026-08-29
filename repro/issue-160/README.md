# Reprodução da issue #160 — `patch path out of range` no primeiro render pós-troca de raiz

Este diretório é **artefato de investigação**, não exemplo do repo: um app Modo A
com as três condições que as tentativas anteriores não tiveram (backend real,
origem fria de verdade, volume de árvore de painel), o serviço que o alimenta, o
harness que dirige o Chrome e as notas do que foi medido.

Nada aqui entra em `examples/` — isso é decisão do dono do repo (exemplo novo
obriga página de docs nas duas línguas).

## O que tem aqui

| Arquivo | O que é |
| --- | --- |
| `app/app.py` | O app Modo A: login → dashboard sob **uma** raiz `Column(key="root")`, `AppBar` cujas ações crescem de 1 para 2, `Row` de 4 `Input`s, `DataTable` 40×8, 4 cards de KPI, barra de uso, poll de 7 s com `set_state` antes e depois de cada `await` |
| `app/tempestweb.toml` | Projeto Modo A com `[pwa] enabled = true` (93 assets no precache) |
| `app/filler/` | 300 arquivos pequenos declarados em `[wasm] assets`, para o precache continuar em voo depois do mount (ver "Por que o precache não competia") |
| `backend.py` | Serviço FastAPI real: autentica, serve `/api/rows` e `/api/metrics` por tick, loga **todo** request numa linha JSON, serve o artefato na **mesma origem**, e aplica latência por request com `--latency-ms` |
| `harness.mjs` | Um run: perfil de Chrome novo, porta nova, cache vazio, service worker novo. Liga `globalThis.__tempestweb_debug` **antes** do primeiro script, mede boot até o Pyodide pronto, o precache, e o número de filhos de cada container que o relato nomeia |
| `run.sh` | Um run ponta a ponta (sobe backend, espera health, dirige o browser, mata o backend) |
| `analyze.py` | Tabela dos runs + o texto integral de cada `patch path out of range` com o outline da árvore do cliente |
| `test_lost_batch_160.py` | Os dois invariantes quebrados, headless, como `xfail(strict=True)`. **Não** é coletado pelo `pytest` do repo (`testpaths = ["tests"]`) |

## Como rodar

```bash
# 1. Buildar o artefato Modo A (93 + 300 assets no precache do worker)
uv run --frozen tempestweb build --mode wasm \
  --path repro/issue-160/app --out repro/issue-160/app/dist/wasm

# 2. Um run: rótulo, porta, arm, quantos ticks de poll observar
#    (porta nova E perfil novo por run — o precache do worker é cache-first e
#     a versão do cache é hash da LISTA, não do conteúdo)
cd repro/issue-160
TW160_OUT=/tmp/tw160 TW160_LATENCY_MS=150 \
  ./run.sh A1 8921 clean 4 --down-mbps 1.5 --rtt-ms 300 --cpu 4

# 3. Tabela + evidência
uv run --frozen python analyze.py /tmp/tw160 A1
```

Dois arms:

- `clean` — todo tick de `/api/metrics` devolve `load_pct` finito. Testa o
  **ambiente** sozinho: CDN do Pyodide frio, worker recém-registrado precacheando
  o shell, lotes do tamanho do painel.
- `drain` — o tick 2 reporta um nó drenando: as ações aparecem **e** `load_pct`
  vem como a string `"NaN"` (o que um encoder JSON emite para float não-finito,
  já que `NaN` cru não é JSON). O tick 3 volta com números finitos, uma nona
  coluna e um novo hint de responsável.

## O mecanismo que o arm `drain` expõe

Duas coisas se somam, e nenhuma delas é o service worker:

1. **`Style.width` (e todo campo numérico sem bound) aceita `float("nan")`.** O
   lote que Python entrega ao cliente então serializa com o token `NaN` cru, que
   `JSON.parse` **recusa** — medido em V8:
   `SyntaxError: Unexpected token 'N', ..." "width": NaN, "heig"... is not valid JSON`.
   A exceção estoura dentro do `onPatches` do `bootstrap.js`, **antes** do
   transporte, antes do renderizador, antes de qualquer diagnóstico: o lote
   inteiro desaparece.
2. **`App._rebuild` (no `tempest-core`) commita a baseline antes de entregar:**

   ```python
   new = self._build()
   patches = diff_scene(self._current, new)
   self._current = new      # <- baseline já andou
   if patches:
       self._apply(patches)  # <- se isto falhar, o lote se perde
   ```

   Então uma entrega que falha deixa Python achando que o cliente tem uma árvore
   que ele nunca recebeu. Todo patch seguinte é relativo a índice **dessa**
   árvore.

Sequência medida (headless, `test_lost_batch_160.py`, e no browser no arm
`drain`):

| Lote | Conteúdo | Destino |
| --- | --- | --- |
| swap login → dashboard | 8 patches, 699.311 chars | aplica |
| tick 2 (`alerts=3`, `load_pct="NaN"`) | `Insert path=[0,1] index=1` (a **segunda ação do AppBar**) + `Update` com `width: NaN` | **perdido** — `JSON.parse` recusa |
| tick 3 | `Update path=[0,1,1]`, depois `Update path=[1,3]` (o **quarto `Input`**) e os `Update` do `DataTable` | `RangeError` no 2º patch; o resto do lote é abortado |

Que é exatamente a lista de dano do relato: a segunda ação do `AppBar`, o quarto
`Input` de uma `Row` e uma coluna do `DataTable`.

## Resultados medidos (2026-08-27, tempestweb 0.124.0 @ 47c3de2)

21 runs, cada um com **porta nova, perfil de Chrome novo, cache vazio e service
worker registrado pela primeira vez naquela origem**. `boot` = do `goto` até o
botão de login existir no DOM (Pyodide pronto e app montado).

| Arm | Runs | Boot | Precache | Estado do worker no mount | Resultado |
| --- | --- | --- | --- | --- | --- |
| **A** — dados limpos, throttle de página 1,5 Mbps / 300 ms / CPU 4× | 6 | 18,7–23,6 s | 93 assets, concluído aos ~6,6 s | `activated` + controlando | **6/6 íntegro** |
| **C** — idem + 393 assets + 150 ms de latência no servidor | 4 | 55,3–59,2 s | 393 assets, concluído aos ~27 s | `activated` + controlando | **4/4 íntegro** |
| **D** — sem throttle de página, 400 ms de latência no servidor, dwell de 8 s no login | 6 | 11,0–15,0 s | 393 assets, **ainda em voo** (0 no cache do início ao fim do run) | `installing` durante o run inteiro | **6/6 íntegro** |
| **M2** — idem D, viewport **390×844** | 1 | 14,8 s | 393, ainda em voo | `installing` | **1/1 íntegro** |
| **B** — arm `drain` (o backend reporta `load_pct: "NaN"` no tick 2) | 5 | 3,3 / 4,7 / 4,8 / 19,6 / 57,9 s | 93 assets | `activated` + controlando | **5/5 REPRODUZIU** |
| **M1 / W1** — arm `drain` em **390×844** e **1440×900** | 2 | 5,0 / 4,9 s | 393 assets | `activated` + controlando | **2/2 REPRODUZIU** |

Um 5º run do arm C bootou (58,9 s, 393 assets) mas foi **abortado** antes do
login — não conta na tabela e não é evidência de nada além do boot.

Nos 17 runs do ambiente (A+C+D+M2): 0 `patch path out of range`, 0 erro de página,
`filters` com 4 filhos, `table` com 41 linhas e 8 colunas, `appbar-actions`
oscilando 1↔2 corretamente, 16–20 lotes de patch aplicados por run, e **0
`console.warn` e 0 `console.error`** somados nos 17 runs.

No arm `drain` são **7/7** (5 no build de 93 assets, 2 no de 393), e os dois
viewports dão o mesmo resultado: a falha é do stream de patches, não do layout.

A assinatura, idêntica em todos os 7:

```text
tempestweb: patch could not be applied
RangeError: tempestweb: patch path out of range at index 1 (path [0, 1, 1], step 2):
  div[data-tw-key="appbar-actions"] has 1 children [button[data-tw-key="act-refresh"]]
{"path":[0,1,1],"set_props":{"label":"Alertas (6)","on_click":null},"unset_props":[]}
```

Outline da árvore do cliente no lote que falhou (`__tempestweb_debug`):

```text
0:div[root] (6)
  1:div[appbar] (2)
    2:span[appbar-title] (0)
    2:div[appbar-actions] (1)      <- Python tem 2 aqui
      3:button[act-refresh] (0)
  1:div[filters] (4)
  1:div[usage] (2)
  1:div[kpis] (4)
  1:div[table] (41)
    2:div[table-header] (8)        <- a nona coluna nunca chegou
```

DOM medido **no instante da falha**, antes do resync da #159 reparar:

```json
{"appbar_actions_children": 1, "appbar_action_labels": ["Atualizar"],
 "filter_placeholders": ["buscar", "região", "estado", "responsável"],
 "table_columns": 8, "usage_label": "uso 41/100", "footer": "tick 1 · polling"}
```

O quarto `Input` ficou com `responsável` (o lote abortado trazia `dono`), a tabela
ficou com 8 colunas (o lote trazia 9) e a segunda ação do `AppBar` não existe —
a lista de dano do relato, item por item. O lote seguinte é um root `Replace` de
624.848 chars: o resync que a #159 introduziu.

## Por que o precache não competia (e como forçar)

`Network.emulateNetworkConditions` por CDP molda o tráfego **da página**, não o
do service worker. Medido no run A1 (log do backend, `req-A1.log`): o worker
terminou os 93 assets em **6,6 s**, enquanto o mount só aconteceu aos **23 s** —
ou seja, com throttling de página o precache termina *antes* do app existir, e a
corrida "precache × boot/mount" que a hipótese pede nunca é exercitada. É por
isso que "boot lento" por throttling de página **reduz** a sobreposição em vez de
aumentá-la, e é provavelmente por isso que as tentativas anteriores com Slow 4G
não a exercitaram.

Duas mudanças forçam a sobreposição, e as duas imitam um deploy real em vez de
localhost:

- `--latency-ms` no backend: atrasa **todo** request, página e worker igualmente;
- `app/filler/` (300 assets em `[wasm] assets`, gerados por `make_filler.py`): o
  `cache.addAll` passa a levar dezenas de segundos.

Medido no arm D (`--latency-ms 400`, sem throttle de página): `caches` da origem
com **0 entradas do começo ao fim** do run e o registro em `installing` o tempo
todo, com 252 dos 393 `/filler/*.json` servidos entre 9,8 s e 46,8 s — enquanto o
mount saiu aos 11,6 s, a troca de raiz aos 24,4 s e três ticks de poll aos 31 s,
38 s e 45 s. Ou seja: **mount, troca de raiz e os três primeiros polls
inteiramente dentro da janela de precache**, e a árvore saiu íntegra 6/6.

### Quão alto o lote perdido reclama

Medido nos 5 runs do arm `drain`, contando linhas de console que mencionam a
falha de JSON:

| Run | Boot | Linhas sobre a falha de JSON | Nível | `patch could not be applied` |
| --- | --- | --- | --- | --- |
| B1 | 4,8 s | 6 | `warn` | 1 |
| B2 | 19,6 s | 6 | `warn` | 1 |
| B3 | 3,3 s | 6 | `warn` | 1 |
| B4 | 4,7 s | 6 | `warn` | 1 |
| B5 | **57,9 s** | **0** | — | 1 |
| M1 (390×844) | 5,0 s | **0** | — | 1 |
| W1 (1440×900) | 4,9 s | **0** | — | 1 |

Quando reclama, é `console.warn` do handler de exceção não-recuperada do Pyodide,
apontando para `WasmTransport.send_patches` — nada que ligue a falha à árvore:

```text
future: <PyodideTask finished name='Task-10'
  coro=<WasmTransport.send_patches() done, defined at
  /home/pyodide/tempestweb/transports/wasm.py:74>
  exception=SyntaxError: Unexpected token 'N', ..." "width": NaN, …
```

E em **3 de 7** não reclamou nada: a única pista foi o `patch path out of range`
do tick seguinte. O aviso do Pyodide depende do GC coletar a task, então a
presença dele não é garantida. Se nenhum patch posterior
endereçasse o nó que faltou, a tela ficaria errada sem uma linha de log — que é
o formato do relato original, feito num artefato anterior à #159/#162.

## O que isto elimina, e o que não

**Elimina** (17 runs, origem fria de verdade, backend real, volume de painel):
que o ambiente sozinho — CDN do Pyodide frio, boot de 11 a 59 s, service worker
recém-registrado com 93 ou 393 assets, precache concluído *ou* ainda em voo
durante o mount, a troca de raiz e os primeiros polls — produza
`patch path out of range`. Não produziu nenhuma vez.

**Não elimina** o gatilho do relato ser outro caminho de perda de lote. O que
este trabalho mostra é que **existe** um caminho de perda, ele é silencioso, e
qualquer perda vira exatamente esta assinatura por causa do
`self._current = new` antes do `self._apply(patches)`. O relato veio de um
artefato **anterior** à #159 (sem resync) e à #162 (sem diagnóstico), então uma
perda por qualquer causa ficaria permanente e sem rastro — que é o sintoma
descrito.

**Não medido**: se o painel do tempest-webtunnel de fato produzia float
não-finito. Isso exige o app dele, não este.

## Armadilhas respeitadas

- Porta nova **e** perfil de Chrome novo por run. A versão do cache do worker é
  hash da **lista** de precache, não do conteúdo: rebuildar sem trocar a lista
  mantém o mesmo nome de cache (`tw-b55fa9e7ad8f-precache` aqui, idêntico entre
  dois builds diferentes deste app).
- `globalThis.__tempestweb_debug` é ligado por `addInitScript`, isto é, antes do
  primeiro script da página — flag ligada depois nunca vê o lote que quebrou.
- `client/dom.js` do artefato **não** é patchado: a mensagem de `resolvePath` já
  carrega path, passo, pai por `data-tw-key` e filhos reais desde a #162.
