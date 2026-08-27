# Changelog

All notable changes to **tempestweb** are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); this project adheres to semantic
versioning.

## [0.124.0] — 2026-08-27

### Fixed

- **A limpeza de `410 Gone` do WebPush nunca rodou em produção (#118).** A
  verificação em device da linha P3 pedia o round-trip por um push service real,
  e ele foi medido contra o **FCM**, com a aba fechada: subscribe devolve
  `https://fcm.googleapis.com/fcm/send/…`, `pywebpush` responde **201** em ~1,0 s
  e o worker mostra a notificação com **zero páginas abertas**. Chave VAPID
  trocada responde **403**; subscription cancelada responde **410 Gone**.

  E o `410` não chegava a lugar nenhum. `WebPushService.send` captura o
  `WebPushError` **deste módulo**, e o sender real — `pywebpush.webpush` —
  levanta o `WebPushException` **dele**. Toda falha real caía no ramo genérico
  com `status_code=None` e `gone=False`, então a poda de endpoint morto que o
  docstring promete só acontecia contra os senders fake que os testes injetam:
  eles levantavam a exceção certa, e por isso o ramo estava "coberto". Sintoma
  medido: depois de um `unsubscribe()` no browser, todo envio respondia
  `{"sent":0,"total":1}` — para sempre, com o endpoint morto no store.

  `_default_sender` passa a traduzir: o `WebPushException` do `pywebpush` vira
  `WebPushError` com o status da resposta do push service. Medido depois da
  correção, mesmo endpoint morto: primeiro envio `{"sent":0,"total":1}`, segundo
  `{"sent":0,"total":0}` — podado.
- **E a poda, alcançável em produção pela primeira vez, rodava desprotegida.**
  `remove()` é implementado pelo host (SQLAlchemy, Redis) e pode levantar numa
  conexão caída; a chamada estava direto no ramo do 410, sem isolamento. Medido
  com um store que levanta `OperationalError` no `remove()`, duas assinaturas e a
  morta primeiro: a exceção subia por `send` → `send_to_owner`, `POST
  /webpush/send` respondia **500** e o endpoint **vivo do mesmo lote nunca era
  tentado**. Ou seja: fazer o 410 chegar trocaria "linha morta no store" por
  "entrega perdida para quem está vivo". A poda virou
  `WebPushService._prune_dead_endpoint`, isolada: o `SendOutcome` volta com
  `gone=True` de todo jeito e o vivo recebe. É o único lugar do módulo onde
  engolir exceção é correto — o endpoint está morto de fato, e o dado que importa
  já está no outcome — e a docstring registra o porquê.
- **`POST /webpush/send` travava o event loop do Modo B.** `pywebpush.webpush`
  posta com `requests` (bloqueante) e declara `timeout: float | None = None`,
  repassando esse `None` ao `requests.post` — o fallback
  `kwargs.pop("timeout", 10000)` do `WebPusher.send` nunca se aplica, porque a
  chave está sempre presente. Logo não havia timeout **nenhum**: um endpoint que
  aceita o TCP e não responde pendurava o envio. E a rota `async` chamava o
  fan-out inline, no mesmo loop que serve o stream de patches por WebSocket.
  Medido com um sender de 1 s e três assinaturas: a requisição levava 3,00 s e um
  heartbeat de 10 ms no mesmo loop recebia **zero** ticks — toda app conectada
  congelada pelo envio inteiro. Duas metades corrigidas: `WebPushService` ganha
  `timeout` (keyword-only, default **10 s** — o FCM respondeu em ~1,0 s na
  medição, 10x de folga) repassado ao sender, e a rota chama o envio por
  `run_in_threadpool`. Medido depois: mesma requisição em 3,01 s, heartbeat com
  **296 ticks** e atraso máximo de **0,01 s**.
- **`SendOutcome.status_code` fabricava `201` num envio que ninguém confirmou.**
  O campo promete "o status HTTP do push service (quando conhecido)", mas o
  fallback `or 201` inventava um: um sender que devolve `None` (o `fake_sender`
  dos próprios testes) e `pywebpush.webpush(curl=True)`, que devolve `str`,
  produziam `ok=True, status_code=201`. Agora o status é lido da resposta e fica
  `None` quando não há resposta para ler — `200`/`201`/`202` num envio aceito.
  De quebra, **o teste que cobria isso não podia falhar**: alimentava o fake com
  `201` e afirmava `201`, exatamente a constante do código pré-fix. Ele passa a
  usar `202` (status real — o `pywebpush` só levanta acima de 202) e reprova
  contra o estado anterior, junto dos outros.
- **`POST /webpush/unsubscribe` removia por endpoint sem escopo de owner.** Dois
  roteadores sobre o mesmo serviço é a forma que a própria assinatura oferece
  (`webpush_router(svc, owner="alice", prefix="/webpush/alice")` e o mesmo para
  `"bob"`), e o store é indexado só por endpoint: `POST
  /webpush/alice/unsubscribe` carregando o endpoint do bob respondia
  `{"removed": true}` e apagava a assinatura **do bob**. A rota passa a conferir
  `store.list_for(owner)` antes de remover — endpoint que este owner não tem
  responde `{"removed": false}`, a mesma resposta de um já removido, então a rota
  também não revela que outro owner o guarda. O `SubscriptionStore` Protocol
  segue intocado (`remove(endpoint)`): mudar a interface quebraria host que já a
  implementa. A poda por 410/404 continua **sem** escopo, e isso é correto — ali
  o push service disse que o endpoint está morto, logo está morto para todo
  owner.
- **Corpo sem `endpoint` no `/unsubscribe` respondia `{"removed": false}` calado**
  — a mesma resposta de "essa assinatura já não existia", enquanto `/subscribe`
  já respondia 400 ao mesmo corpo malformado. Agora as duas respondem **400**
  nomeando o campo.
- **`POST /webpush/subscribe` respondia 500 a um corpo sem `endpoint`.** O
  `ValueError` do store escapava sem tratamento; agora é **400** nomeando o campo
  que falta — erro do chamador responde como erro do chamador.

### Changed

- **Superfície pública do WebPush:** `WebPushService.__init__` ganha
  `timeout: float = 10.0` (keyword-only), `SendOutcome.status_code` passa a poder
  ser `None`, `POST {prefix}/unsubscribe` responde **400** a corpo sem `endpoint`
  e só remove o que o `owner` do roteador tem. `docs/examples/webpush-server.md`
  e `.en.md` acompanham nas duas línguas: a tabela de endpoints com as respostas
  de erro, o `timeout` na explicação peça-por-peça, o envio fora do event loop, a
  poda cobrindo `410` **e** `404` (com o risco conhecido de agrupar: um proxy
  respondendo o próprio 404 por caminho errado apaga um inscrito vivo), o `403`
  que não poda, e o `status_code` real em vez da constante.
- O docstring do módulo passa a registrar o racional de tratar `404` como
  endpoint morto, e um teste (`test_a_404_prunes_like_a_410`) fixa a decisão — a
  medição em device só exercitou `201`/`403`/`410`, então o `404` estava
  agrupado por acidente.
- `docs/roadmap.md` (P3) e `docs/agents/device-verification.md` registram a
  medição: os três status do FCM, o defeito que ela achou, e o
  `pushsubscriptionchange` exercitado **no worker real** (evento sintético,
  `pushManager.subscribe()` e re-POST reais) — re-subscreve com a chave da
  `oldSubscription`, ganha endpoint novo e re-POSTa `/webpush/subscribe` com
  **200**, aba fechada.

## [0.123.0] — 2026-08-27

### Fixed

- **`native.storage` prometia IndexedDB e gravava no `localStorage` (#118).** A
  verificação em device da linha N3 pedia medir persistência num browser real,
  já que o `indexedDB` do jsdom é um shim. Medido num artefato Modo A buildado,
  e o defeito não era persistência — era **o backend**:

  ```text
  indexedDB.databases() → []
  localStorage          → note (18 chars), bulk (142.890 chars, crus)
  storage.configure(codec="deflate") → active=deflate supported=True
  ```

  `client/native/storage.js` prefere `deps.store` e cai para `localStorage`
  quando não recebe um. Nada injetava esse store: o `browserDeps()` de
  `client/native/index.js` não o listava, então **só o Modo C** — que monta o
  seu em `client/transpile/native.js` — usava IndexedDB. Modos A e B ficavam com
  o `localStorage`: teto de ~5 MB, escrita **síncrona** na main thread,
  invisível para o service worker. E o codec `deflate` da #180, que configura o
  store de IndexedDB, virava no-op enquanto `configure` respondia
  `supported=True` — o pior tipo de resposta, a que parece certa.

  Persistência sozinha não pega isso: o `localStorage` também sobrevive ao
  reload. Foi preciso olhar **onde** o valor caiu.

  `browserDeps()` passa a construir o store uma vez, preguiçosamente, e a
  entregá-lo em todo dispatch; onde não há IndexedDB (jsdom, perfil bloqueado) o
  fallback de `localStorage` continua exatamente como estava. Medido depois da
  correção, mesmo app: `indexedDB.databases()` → `["tempestweb@1"]`,
  `localStorage` **vazio**, `bulk` de 142.890 caracteres em **10.276 bytes**
  deflated, `note` e `bulk` de volta intactos após reload, `keys=[]` e object
  store vazio depois do `remove()`, e quota reportada de **10.738.498.004
  bytes** contra os ~5 MB do `localStorage`.

  `tests/client/native-storage-backend.test.js` fixa a fiação: que
  `browserDeps()` carrega um store, que ele é construído uma vez, que uma
  escrita pelos deps default aterrissa no IndexedDB, que o `deflate` chega ao
  store onde as escritas vão (envelope `$twcodec` e bytes comprimidos), e que um
  runtime sem IndexedDB continua gravando pelo `localStorage`.

## [0.122.0] — 2026-08-27

### Added

- **`CompactPredictor` — inferência tabular sem runtime de inferência nenhum
  (#191).** A #178 entregou `TabularPredictor` sobre ONNX, e a #191 pediu medir
  antes de portar o resto. Medido: o `.onnx` de uma `LogisticRegression` de 30
  features tem **660 bytes**, e o `onnxruntime-web` que o executa tem **13,96 MB**
  (3,58 MB gzip) no bundle mais enxuto — **+43% no gzip** de um artefato Modo A
  offline e **12× o artefato Modo C inteiro**. Para um app cujo único modelo é
  tabular, o runtime **é** o download.

  Então este leitor dispensa o runtime em vez do modelo: um modelo linear é um
  produto escalar, uma árvore é uma cadeia de comparações, e ambos cabem em
  Python de stdlib (`struct`, `array`, `math`). `CompactPredictor` tem a mesma
  API do `TabularPredictor` — `predict(row)` / `predict_many(rows)`, linha em
  qualquer ordem, mesma `Prediction` — e lê o formato `.tmc`/`TMC1` escrito pelo
  `tempest_fastapi_sdk.modelops.export_sklearn_to_compact`, **que verifica os
  bytes contra as predições do próprio scikit-learn e recusa escrever um arquivo
  que discorde**.

  **O arquivo é o manifesto.** O export grava `feature_names` e `classes` dentro
  do `.tmc`, então não há segundo arquivo para manter em sincronia; `manifest=`
  fica só para sobrescrever um export sem nomes. Cobre modelo linear, árvore e
  floresta, mais `Pipeline` com `StandardScaler`/`MinMaxScaler` (o escalador é
  dobrado no header, nunca ignorado). Gradient boosting o exportador recusa — é
  outro leitor — e o caminho continua sendo o `TabularPredictor`.

  **A paridade é medida contra o sklearn, não contra nós mesmos:** os seis `.tmc`
  da suíte são escritos pelo publicador do formato, e ao lado deles fica o que o
  scikit-learn respondeu para as mesmas linhas
  (`tests/conformance/_compact_models.py` regenera os dois). Isso pega a
  armadilha real: `sklearn.tree` converte a entrada para float32 antes de
  percorrer, então um limiar 5.099999904632568 e uma entrada 5.1 comparam
  **iguais** e vão para a esquerda — comparar em float64 muda o rótulo de uma
  linha numa árvore.

  Medido em Chrome real (artefato Modo A, sem `onnxruntime-web` em lugar nenhum):
  forest de 12 árvores respondeu `setosa` p=1,00000000 e o linear `0`
  p=0,99111871, contra 0,9911187022504708 do sklearn; **6,3 ms** do frio à
  primeira predição; p95 de **0,2 ms** por linha; 1.000 linhas de uma vez em
  **51,8 ms**; e **um request por modelo** ao longo de 200 predições.
- **Capacidade nativa `compact.load`**, que traz os bytes do `.tmc` pelo mesmo
  cache de assets que o `onnx.load` usa — o modelo baixa uma vez por versão, não
  uma por sessão, e um runtime sem Cache Storage cai para o fetch cru.

### Fixed

- **O artefato Modo A não levava oito subpacotes que uma app importa pelo
  nome.** `tempestweb.tabular`, `.vision`, `.query`, `.access`, `.export`,
  `.presets`, `.pwa` e `.observability` estavam fora do
  `_WASM_PACKAGE_PARTS`, então qualquer app Modo A que importasse um deles
  morria no boot com `No module named` — enquanto a suíte inteira ficava verde,
  porque o processo de teste tem o pacote instalado e o browser só tem o zip. Foi
  achado rodando um artefato de verdade numa aba, não pelo gate.

  O guard existente provava que o subconjunto era **fechado** sob os próprios
  imports; o novo
  (`test_every_app_facing_subpackage_is_bundled`) inverte a pergunta: todo
  subpacote que não é server-side (`server`, `cli`, `devserver`) nem
  build-time (`transpile`) tem que estar no bundle, ou ser excluído de propósito
  com o motivo escrito. Custo medido: o `tempestweb-pkg.zip` do artefato foi de
  360.758 para 468.407 bytes — 107 KB contra um Pyodide de 15,6 MB.

## [0.121.0] — 2026-08-27

### Fixed

- **Em Modo C, a prop da base que a app punha num componente não chegava a nó
  nenhum.** Nos Modos A e B quem resolve isso é o `build` do core, que passou a
  carregar `semantics`, `focusable`, `focus_order`, `tag` e `attrs` para a raiz
  que o componente renderizou (`tempest-core` 0.17.0, aberta a partir daqui). Em
  Modo C **um componente é uma função**, não um nó que alguém expande: o builder
  destrutura o que conhece e o resto some. Ou seja, a mesma tela ficava acessível
  no browser e **muda na build transpilada de si mesma** — a divergência mais cara
  de achar, porque os dois lados "funcionam".

  Os 47 builders de `components.js` passam a carregar, por um decorator
  (`carrying`) em vez de uma linha repetida 47 vezes, com a regra do core: **o
  render é dono do que ele tocou.** Prop que a árvore construída já define em
  qualquer nó fica intacta — é o que mantém um campo correto, porque ele põe o
  nome no `Input` em que o leitor de tela para, e a cópia no wrapper sem role
  anunciaria o mesmo controle duas vezes (`aria-prohibited-attr`).

  Guards, os dois medidos mordendo:

  | Onde | O quê |
  | --- | --- |
  | `tests/fixtures/transpile_component_samples.json` | seis **pares `__named`**, construídos do core real, com os dois ramos da regra (350 → **356 casos**) |
  | `tests/client/component-carry.test.js` | sweep sobre **todos** os builders, mais o guard de drift contra o `CARRIED_PROPS` gerado do core |

  Com o `carrying` neutralizado: `alert_title_only__named diverged from core` na
  matriz, e `Accordion dropped attrs` no sweep.

### Changed

- **Piso `tempest-core>=0.17.1`.** É onde o carry existe (0.17.0) e onde
  `focusable=False` e `focus_order=0` deixam de ser tratados como ausência
  (0.17.1) — o Modo C espelha o comportamento corrigido, então rodar contra a
  0.17.0 faria a matriz divergir nos dois falsy.
- `client/transpile/values.gen.js` e `tempestweb/transpile/_served.py`
  regenerados: o core exporta `CARRIED_PROPS`, e ele vira a lista canônica que o
  cliente espelha em vez de redigitar.
- O guard `test_ported_components_are_reachable_from_the_app_import` passa a
  contar as duas formas de declaração (`export function` e `export const`), como
  o gerador do manifesto sempre contou. Sem isso, um builder embrulhado é
  reportado como inalcançável — e a régua estaria medindo a sintaxe, não o
  alcance.

## [0.120.0] — 2026-08-27

### Added

- **`tempestweb.tabular` — inferência sklearn→ONNX no browser (#178).** O
  framework tinha `vision/` para pixels e nada para dado **tabular** — o caso
  mais comum de ML em app de negócio (score de risco, previsão de demanda,
  classificação de lead), que por isso precisava chamar endpoint e quebrava o
  offline-first.

  **O manifesto é o que a issue chamou de valor real, e é.** Um modelo ONNX é uma
  função de um vetor de floats **sem rótulo** para um número: a ordem carrega
  todo o significado e nada no runtime confere. Uma app que manda `{"idade": 30}`
  para um modelo treinado com `age` não falha — lê um zero e responde um número
  plausível e errado. Com o manifesto:

  ```text
  MissingFeatureError: row is missing 1 feature(s): age; it carries instead: idade
  ```

  As duas metades juntas de propósito: `age` ausente e `idade` presente é **um**
  typo, não dois. Manifesto sem feature ou com feature repetida é recusado —
  duplicata torna a ordem ambígua, que é justamente o que ele existe para fixar.

  **v1 estreita**, como combinado: `TabularPredictor` + manifesto + erros
  nomeados. `CompactPredictor` e ordem configurável de provider ficam para
  follow-up.

  **Medido em Chrome 150 real**, com um `.onnx` de sklearn de verdade exportado
  no venv descartável, comparado contra o que o mesmo modelo responde em Python:

  | Linha | sklearn | Chrome → Python | delta |
  |---|---|---|---|
  | `income=2000 tenure=6` | `high` p=0,99999702 | `high` p=0,99999708 | 5,96e-08 |
  | `income=9000 tenure=90` | `low` p=1,00000000 | `low` p=1,00000000 | 0 |
  | `income=2500 tenure=12` | `low` p=0,66673243 | `low` p=0,66673243 | 0 |

  Sem numpy: o tensor é montado com `struct` da stdlib. numpy é extra do
  `vision`, e um pacote que empacota algumas dezenas de floats não deve arrastar
  ele — nem os bounds dele — para a resolução de todo consumidor.

### Fixed

- **`onnx.load` agora passa pelo cache de assets que já existia.** Um modelo ONNX
  é a maior coisa que uma app embarca e não muda entre cargas, e mesmo assim era
  rebaixado toda sessão — para o `vision` também. Passa a usar
  `client/offline/asset-cache.js`, que ainda deduplica cargas concorrentes da
  mesma URL. Medido: segunda carga em **2,7 ms**, do bucket `tw-assets`. Runtime
  sem Cache Storage degrada para a URL crua — cache frio é mais lento, não
  quebrado.

- **Export padrão do skl2onnx não rodava, e o erro não dizia o porquê.** O default
  acrescenta um nó **ZipMap** e `probabilities` deixa de ser tensor, virando
  `seq(map(int64,float))`. O `onnxruntime-web` respondia
  `Reading data from non-tensor typed value is not supported`, que não diz o que
  fazer. Achado medindo com um export real; agora `onnx.run` levanta
  `unsupported_output` **nomeando a correção**
  (`to_onnx(..., options={id(model): {"zipmap": False}})`), e a receita abre com
  um `!!! danger` sobre isso. O modelo com ZipMap tinha 539 bytes; sem ele, 389 —
  e passou a rodar.

### Changed

- `docs/roadmap.md`: Trilho R, fase R7 (tabular) ✅ — o trilho inteiro fecha.

## [0.119.0] — 2026-08-27

### Added

- **`imaging` — comprimir, miniaturar e transformar antes do upload (#174).**
  Entre `camera.capture()` e `http.upload()` não havia nada: a app capturava uma
  foto de 4 MB e subia 4 MB, ou reescrevia compressão com canvas na mão, num
  framework cuja proposta é não escrever JS.

  **Os pixels ficam no browser.** Toda função recebe e devolve um **handle**
  opaco para bytes que o cliente segura, e a issue deixava essa decisão em
  aberto. A alternativa — mandar os bytes — é absurda no Modo B: comprimir uma
  foto de 4 MB subiria 5,3 MB de base64 ao servidor e baixaria outros 5,3 MB, só
  para encolher. Com handle são ~40 bytes. `camera.capture(include_bytes=False)`
  estende isso à primeira travessia e `as_upload(nome)` à última — o servidor
  recebe os bytes, o Python nunca.

  De quebra, isso **implementa o `blob_id`** que o `http.upload` já documentava e
  não resolvia: um descritor com handle agora sobe os bytes de verdade, como
  multipart, em vez do JSON que apenas os mencionava.

  **A busca de qualidade é binária e limitada.** Tamanho codificado não é linear
  em qualidade, então uma escada fixa ou estoura o orçamento ou joga fora
  qualidade que cabia. `CompressedImage` reporta onde parou: qual qualidade,
  quantos encodes gastou e se cumpriu o orçamento.

  **Medido em Chrome 150**, foto de 4000×3000 com estrutura: 871,5 KB → **124,8 KB**
  (−85,7%) em **5 encodes**, qualidade **0,91**, `within_budget=True`, 545 ms.
  Miniaturas de 96 e 256 px saíram com 4,9 KB e 29,7 KB. E o caminho que a issue
  exigia: com 9,4 MB de ruído puro contra 200 KB, parou em **5 encodes** com
  `within_budget=False` e o menor que conseguiu — respondeu em vez de travar.

  **Opção com nome errado levanta.** `CompressOptions` e `TransformOptions` são
  `extra="forbid"`: `compress(photo, maxWidth=1600)` levanta em vez de ignorar em
  silêncio, porque o silêncio subiria a foto em tamanho original e ninguém
  saberia. Os modelos de payload (`CompressedImage`, `Thumbnail`, …) fazem o
  oposto e ignoram campo desconhecido, senão cliente novo quebraria Python
  antigo.

  Handle é limitado e o mais antigo é descartado, para uma tela de captura
  rodando uma hora não acumular todo frame; endereçar um vencido levanta
  `NativeError("not_found")`.

  `blobs.js` e `imaging.js` entraram em `_NATIVE_ASSETS`, e `_native.py` foi
  regenerado.

### Changed

- **`camera.capture` ganha `include_bytes`** e `Photo` ganha `ref`. Aditivo: o
  default mantém o comportamento de hoje byte a byte.
- `docs/roadmap.md`: Trilho R, fase R6 (imaging) ✅.

## [0.118.0] — 2026-08-27

### Added

- **`device.profile` — memória, núcleos e heap da máquina do usuário (#179).** O
  framework sabia medir o servidor (`observability/`) e a si mesmo no CI
  (`benchmarks/perf_gate.py`), e não sabia nada sobre a máquina em que a app
  roda — que é quem decide se comprimir a foto mais, cachear menos, ou desistir
  de rodar o modelo ONNX localmente.

  **Escopo reduzido em relação à issue, de propósito.** A issue propunha
  `DeviceProfile` com `connection`, `save_data` e `cache_bytes` — e os três já
  existiam: conexão e `save_data` em `native.network.state()`
  (`NetworkState.effective_type`/`save_data`) e bytes em
  `native.quota.estimate()`. Pior: o nome proposto (`connection`) divergia do que
  o `NetworkState` já usa, o que daria **dois nomes ao mesmo fato no contrato**.
  Ficou só o que era genuinamente novo — `memory_gb`, `cores`, `heap_used_mb`,
  `heap_limit_mb` — e a doc mostra a composição com as outras duas famílias.

  **Todo campo é opcional, e o teste fixa o caminho em que tudo volta `None`.**
  `navigator.deviceMemory` e `performance.memory` são só-Chromium; no Safari e no
  Firefox a chamada funciona e responde `None` na maior parte. Uma app que lê
  `None` como "aparelho fraco" degrada **todo iPhone** para o pior nível, que é o
  oposto de adaptar. A doc abre com um `!!! danger` dizendo isso.

  **Medido em Chrome 150:** `memory_gb=32`, `cores=12`, `heap_used_mb=2.5`,
  `heap_limit_mb=4192`, com o caminho "nenhuma API disponível" devolvendo quatro
  `None` e console limpo. A medição **corrigiu a doc**: eu havia escrito que o
  Chromium capa `deviceMemory` em 8, e este Chrome respondeu 32 — o valor é
  quantizado em potência de dois e o cap é escolha do browser, então a doc passa
  a mandar comparar com `<=` contra um limite baixo em vez de testar um valor
  exato.

  Fingerprinting fica **fora** por escrito: os campos são grosseiros de propósito
  e existem para escolher um nível de compressão, não para identificar ninguém.

  `device.js` entrou em `_NATIVE_ASSETS` e `_native.py` foi regenerado — os dois
  guards pegaram a falta antes de eu perceber.

### Changed

- `docs/roadmap.md`: Trilho R, fase R5 (device.profile) ✅.

## [0.117.0] — 2026-08-27

### Added

- **Codec opcional no store, medido antes de existir (#180).** A issue pedia a
  medição **antes** do código, e a medição mudou a resposta: **o IndexedDB já
  comprime o que guarda.** Um catálogo de 977 KB chega ao disco como **222 KB**
  sem codec nenhum — o LevelDB por baixo espremeu 4,4× sozinho. Então o codec não
  compete com texto cru; compete com o storage. A economia real é o que sobra:

  | Payload | Sem codec | Com codec | Economia real |
  |---|---|---|---|
  | catálogo, 5.000 itens | 222,1 KB | 122,1 KB | **−45,0%** |
  | histórico repetitivo | 64,1 KB | 22,6 KB | **−64,8%** |
  | ruído base64 | 126,5 KB | 95,0 KB | −24,9% |

  Com a CPU throttlada 6×, o custo é **+12,4 ms por leitura** e **+75,8 ms por
  escrita** em 1 MB, subindo para **+33,8 ms / +295,1 ms** em 4 MB. O medo escrito
  na issue era "40 ms por leitura para economizar 3%"; a leitura não é o problema,
  a escrita é.

  Conclusão: paga para quem guarda dezenas de MB de coleção repetitiva, não paga
  para quem guarda rascunho e fila. Logo **default `"json"`, opt-in explícito**:

  ```python
  await native.storage.configure(codec="deflate")
  ```

  **Divergência da issue, deliberada.** Ela propunha a API em
  `native.offline.configure(...)` e, no mesmo texto, colocava a fila de mutações
  **fora de escopo** — ou seja, a API proposta comprimiria justamente o que ela
  excluiu, e deixaria a coleção grande de fora. O codec entrou onde a coleção
  grande de fato mora: o `native.storage`, sobre o KV do IndexedDB — que é também
  onde o `tempestweb.query` persiste.

  **Ligar e desligar não apaga nada, e isso é o que torna a opção segura:**
  decodificar está sempre ligado, só codificar é opt-in. Um valor guardado carrega
  o nome do codec que o escreveu, então o leitor nunca consulta a configuração
  atual. Medido em Chrome real com um catálogo de 565 KB: registro escrito antes
  do codec continua legível com ele ligado, e registro comprimido continua legível
  com ele desligado.

  **`configure` nunca levanta por falta de suporte.** `CompressionStream` só
  chegou no Safari 16.4; abaixo disso a chamada responde
  `active="json", supported=False` e o store segue funcionando. Store que não
  comprime ainda é store; exceção ali seria tela morta num device real. Envelope
  de codec desconhecido e bytes corrompidos viram **cache miss**, não exceção.

  `codec.js` entrou em `_OFFLINE_ASSETS` — módulo de `client/` fora da lista
  simplesmente não existe no app buildado, e nada falha alto.

  Receita com a tabela inteira em `docs/advanced/storage-codec.md` (PT + EN),
  aberta por um `!!! danger` mandando medir a própria carga.

### Changed

- `docs/roadmap.md`: Trilho R, fase R4 (offline codec) ✅.

## [0.116.0] — 2026-08-27

### Added

- **`tempestweb.query` — o lado da leitura do dado remoto (#175).** O framework
  tinha as duas pontas difíceis — `native.http` (retry + idempotência),
  `native.offline` (fila durável) e `native.sync` (delta-sync por watermark) — e
  nada no meio. Não havia onde guardar a resposta de um `GET` com chave,
  invalidar quando uma mutação entra, paginar, ou aplicar uma mudança antes de o
  servidor concordar. Cada app escrevia isso como `dict` dentro do próprio
  `State`, e a parte que sempre saía errada era a invalidação.

  **A chave é tupla, então prefixo é comparação e não convenção.** `keys("users")`
  faz `("users",)`, `("users", "list", "page=1")`, `("users", "detail", "7")`, e
  `invalidate(USERS.all())` alcança as três. Parâmetro é ordenado antes de entrar
  na chave, senão a mesma query escrita de dois jeitos cacheia duas vezes e a
  segunda escrita nunca invalida a primeira. E o prefixo é **por segmento**:
  `("users",)` não é prefixo de `("users-archive",)`, que é justamente o que um
  `startswith` sobre strings juntadas erra — em silêncio.

  **`invalidate` mantém o valor; `drop` remove.** Stale não é vazio: a tela segue
  mostrando a última resposta boa enquanto o refetch está no ar.

  **Leituras concorrentes da mesma chave viram uma requisição** (single-flight).
  Uma tela com três widgets lendo a mesma query disparava três requisições
  idênticas.

  **O rollback que faltava no desenho da issue.** O `done-when` pedia "otimista
  aplicado **e revertido**", mas a superfície proposta só oferecia `patch` +
  `invalidate` — e invalidar é ida à rede, não desfazer: deixa a mudança errada
  na tela até o refetch chegar, e offline não faz nada. Aqui `patch` devolve um
  rollback que restaura **exatamente** as entradas que substituiu, e
  `optimistic(...)` é o bloco que não deixa esquecer dele. O patch alcança um
  **prefixo**, porque um rename tem que chegar em toda página cacheada onde a
  linha aparece; e é atômico, porque duas entradas mostrando duas verdades
  diferentes é pior que nenhuma mudança.

  **As duas formas de paginar**, tipadas, com `is_offset_page`/`is_cursor_page`
  para distinguir e `empty_offset_page()` para o estado antes da primeira
  resposta. Payload malformado renderiza vazio em vez de levantar — listagem
  vazia é recuperável, exceção no caminho de renderizar é tela branca.

  **Persistência sobre o store que já existe.** `persist`/`restore` falam com um
  `QueryStorage` — Protocol que o `native.storage` satisfaz como está, verificado
  sob `mypy --strict` — então `client/offline/store.js` não foi duplicado e o
  módulo continua rodando sem browser. Valor não-JSON-able é **pulado e contado**,
  não fatal. Entrada volta **fresca**: revivê-la velha mandaria a tela de boot
  direto para a rede, que é o que persistir queria evitar.

  Relógio é injetado (`QueryCache(clock=...)`), em milissegundos e monotônico —
  um relógio de parede que anda para trás faria toda entrada parecer fresca para
  sempre.

  **Modos A e B**, fixado por teste. Tutorial em `docs/tutorial/query.md`
  (PT + EN) com programa completo por passo.

### Changed

- `docs/roadmap.md`: Trilho R, fase R3 (query) ✅.

## [0.115.0] — 2026-08-27

### Added

- **`tempestweb.access` — `can()` e claims do token, para a `view` decidir o que
  desenhar (#177).** O servidor já decidia o que uma requisição pode fazer; do
  lado da tela não existia nada, então `if state.role == "admin"` se espalhava
  pela `view` e a lista de permissões do JWT era lida com `json.loads` em algum
  canto.

  `AccessControl(roles={...})` guarda o mapa papel → permissão **uma vez**;
  `for_roles`/`for_permissions`/`for_token` resolvem, e a `view` pergunta
  `access.can("users:delete")`. O curinga é deliberadamente pequeno — um
  separador e um curinga no fim, não um glob:

  | Concedido | Pedido | |
  |---|---|---|
  | `users:*` | `users:delete` | ✅ |
  | `users:*` | `audit:read` | ❌ outro prefixo |
  | `users:*` | `users` | ❌ é outra permissão, não uma mais rasa |
  | `users:read` | `users:*` | ❌ ler não é poder tudo |

  **`unverified_access_from_token` não verifica assinatura, e o nome carrega
  isso.** A issue pedia que fosse impossível confundir; o nome proposto
  (`permissions_from_token`) soava autoritativo no autocomplete de quem não lê a
  doc, então o `unverified_` entrou no identificador, para aparecer em toda
  chamada e em todo code review. Um token com assinatura forjada **decodifica
  normalmente** — recusar alguns sugeriria que os aceitos foram conferidos, e no
  Modo A a chave estaria no browser junto com a app. Isso está fixado por teste,
  para que "consertar" adicionando verificação reprove e explique.

  Construído sobre o `decode_jwt` que já existia em `observability/auth.py`, em
  vez de reimplementar base64url + parse — metade da superfície proposta pela
  issue já estava no repo.

  Falha de forma **fecha, não quebra**: papel desconhecido concede nada em vez de
  levantar (o servidor pode ganhar um papel antes de a app modelá-lo), claim com
  forma inesperada contribui nada, token expirado **reporta** via
  `is_expired(now=...)`, e `NO_ACCESS` é um default de deslogado que responde
  `False` a tudo em vez de `AttributeError`. `is_expired` recebe `now` em vez de
  ler o relógio, para quem chama ser dono da fonte de tempo.

  **Modos A e B**, fixado por teste: o Modo C serve um conjunto fechado de
  módulos e recusa este import no build. Numa app Modo C o servidor manda junto o
  que a tela pode desenhar — arranjo mais honesto, aliás, porque a decisão vem de
  quem tem a chave.

  Receita em `docs/advanced/access.md` (PT + EN) abrindo com o `!!! danger` de
  que esconder botão não é autorização, com o par servidor/cliente escrito.

### Changed

- `docs/roadmap.md`: Trilho R, fase R2 (access) ✅.

## [0.114.0] — 2026-08-27

### Added

- **`tempestweb.export` — CSV e XLSX gerados em Python, para o `native.file.save`
  entregar (#176).** `native.file.save` já entregava bytes ao usuário; nada
  produzia esses bytes, então toda app com uma `DataTable` e um botão "Exportar"
  escrevia o encoder à mão — e encoder à mão erra nos mesmos quatro lugares:

  | O dado | O que quebrava |
  |---|---|
  | `Recife, PE` | a vírgula virava separador: a linha ganhava uma coluna |
  | `Ana "A" Silva` | as aspas quebravam quem fosse ler |
  | `João` | sem BOM, o Excel abria como `JoÃ£o` |
  | `date(2026, 8, 27)` num XLSX | virava o número `46265` |

  `Column(campo, cabeçalho, format=...)` lê o valor de um `dict` **ou** de um
  objeto — a mesma lista de colunas serve para o payload da API e para a
  `@dataclass` do estado. `to_csv` delega a citação ao `csv` da stdlib e liga o
  BOM por default; `to_xlsx` monta a pasta de trabalho com `zipfile` +
  `xml.etree`, **sem dependência nova**.

  O quarto erro é o que exigiu trabalho de verdade: o Excel **não tem tipo
  data**. Uma célula de data é um número — dias desde 1899-12-30 — que só parece
  data por causa de um *number format* guardado no `styles.xml`. Encoder à mão
  acerta o número e esquece o formato, e o defeito só aparece quando alguém abre
  o arquivo. O módulo carrega os dois `numFmt`, e o teste **abre a planilha de
  volta** (descompacta, resolve os relacionamentos, confere o tipo da célula)
  para que "gerou bytes" nunca passe por "gerou uma planilha".

  Erro de desenvolvedor levanta em vez de exportar algo silenciosamente errado:
  `Column("nmae", …)` levanta `ColumnFieldError` nomeando o campo que faltou e
  os que existem, e um nome de aba que o Excel recusa (>31 caracteres,
  `[ ] : * ? / \`, apóstrofo nas pontas, `History`) levanta `SheetNameError`
  antes de a pasta virar "conteúdo ilegível".

  **Modos A e B.** Gerar bytes não toca o browser, mas o Modo C serve um conjunto
  fechado de módulos (`tempest_core`, `tempestweb.components`,
  `tempestweb.native`) e **recusa este import no build**, com erro nomeado — app
  Modo C que precisa exportar pede o arquivo ao servidor. Receita em
  `docs/advanced/export.md` (PT + EN), com o aviso de que Excel em pt-BR espera
  `;` como separador e empilha um arquivo separado por vírgula numa coluna só.

### Changed

- **`docs/roadmap.md` ganha o Trilho R**, rastreando a adoção do
  `tempest-react-sdk` fase a fase (R1 export ✅, R2–R7 pendentes), com o que fica
  deliberadamente de fora registrado: provider, contexto e hook não atravessam,
  porque aqui o estado é Python.

## [0.113.0] — 2026-08-25

### Fixed

- **Os campos deste repo entregavam um controle anônimo, e o `LoginForm` levava a
  violação para todo app que o usava.** Um campo desce para uma `Column` — uma
  `<div>` **sem role** — em volta de um `Input`, e a legenda é um `Text` irmão, não
  um `<label for=…>`. Nada associava os dois, então o nome acessível do controle era
  o que o `placeholder` por acaso dizia. Medido com axe sobre a IR dos próprios
  componentes:

  | Caso | Antes | Por quê |
  |---|---|---|
  | `password_field_default` | `label` (**crítico**) | legenda "Senha", sem placeholder |
  | `email_field_default` | limpo | o placeholder default nomeou por acidente |
  | `login_form_default` | `label` (**crítico**) | o campo de senha dentro dele |
  | `signup_form_default` | `label` (**crítico**) | os dois campos de senha |

  Agora o campo **sempre** nomeia o controle: pelo `semantics` que a app passou, e
  pela legenda visível quando ela não passou. Depois, os quatro casos ficam limpos.

- **`semantics` era prop declarada que nenhum `render` lia.** Todo `Component`
  declara `semantics` (vem da base), então nomear um campo compilava, passava no
  `mypy` e não fazia nada — nem erro, nem aviso, nem nome. Auditado sobre
  `tempestweb.components.__all__` antes da correção: **59 de 63 componentes
  descartavam o nome**, e os 4 que o preservavam o preservavam porque o *core*
  repassa. Os cinco que este repo é dono passam a lê-lo; os 54 restantes são
  re-export do `tempest-core` e ficam registrados no guard, com o motivo — um
  componente repassa o próprio `semantics` dentro do próprio `render`, o que é
  release de lá.

  Isso é o que libera **grade com uma linha de cabeçalho**: uma célula sem legenda
  visível é o layout denso que vinte itens em oito colunas pedem, e até aqui ela era
  um controle sem nome nenhum — quem usa leitor de tela ouvia "caixa de edição"
  vinte vezes.

  O nome vai para o `Input`, não para o wrapper: `aria-label` em elemento sem role é
  atributo **proibido** (`aria-prohibited-attr`, `serious`) *e* deixa o controle
  anônimo (`label`, `critical`) — os dois medidos, e o teste do wrapper nomeado fixa
  esse par para o caminho errado não voltar.

- **O ponto cego que deixou isso passar: nenhuma cena do gate de a11y usava os
  campos deste repo.** Nove cenas, e a que se chama `login-form` monta
  `EmailInput`/`PasswordInput` do **core** dentro de um `FormField`, que o
  renderizador nomeia — então `TextField`, `EmailField`, `PasswordField`,
  `LoginForm` e `SignupForm` nunca foram auditados. `login_demo` entra em
  `tests/conformance/_a11y_scenes.py`, e verificado que morde: com a cena nova e o
  componente antigo o gate reprova com `[critical] login_demo: label — Form
  elements must have labels`; com a correção, passa.

- **Um `ScrollView` não rolava: chegava ao DOM como `div`, sem overflow e sem
  eixo.** `Scaffold(scroll=True)` lowera para um, então a árvore dizia que o
  corpo rolava dentro do frame e o browser rolava o **documento**. Medido em
  Chrome num app real que prende o frame a `media.height`: 900px de frame sobre
  3.249px de conteúdo, com a app bar e a barra de ações indo embora para cima.
  Mesma família da `ProgressBar` emitida sem pintura (0.65.0) — o widget
  atravessa a IR corretamente e o renderizador não tinha nada a dizer sobre ele.

  O overflow vem da folha base, que é onde default visual mora (o `Style` inline
  da app continua ganhando). O eixo é prop, não cabe na folha, então é espelhado
  em `data-tw-horizontal` como o `open` do `RouteDrawer`. **`min-height: 0` é a
  metade que parece redundante e não é:** o mínimo automático de um flex item é o
  conteúdo dele, então sem isso o scroller cresce em vez de rolar. O SSR recebe
  as mesmas declarações inline, pela mesma razão que a trilha de um indicador é
  inline lá — página estática não tem folha nenhuma.

  Depois, no mesmo app: `overflow-y: auto`, `clientHeight` 752 sobre
  `scrollHeight` 3.249, e as duas barras nas **mesmas** coordenadas antes e
  depois de rolar 1.500px dentro do frame.

- **Os três shells do build não zeravam a margem de 8px do `body`** — só o
  `render_document` do SSR zerava. Era 8px de espaço morto em todo app buildado
  e, com um frame na altura exata do viewport, 16px de rolagem no documento que
  levava as barras junto. Medido: `scrollHeight - clientHeight` de exatamente
  **16** antes, **0** depois. Um teste por modo, porque os três templates são
  três strings — "o que foi corrigido e os dois que não foram" é uma forma que
  este repo já entregou (o renderizador SSR ficou cinco widgets atrás do cliente
  na 0.98.0).

### Changed

- `docs/tutorial/components.md` (PT + EN) ganha **Quem dá o nome ao campo**, com a
  ordem (`semantics` → legenda), o HTML resultante e a nota de WCAG 2.5.3: um
  `semantics` que não contém o texto da legenda deixa quem usa comando de voz sem
  como chamar o campo.
- `docs/stability.md` (PT + EN): a cobertura do gate passa a ser descrita por **tipo
  de widget e por componente**, com o buraco do segundo eixo registrado.
- `docs/advanced/transpile.md` (PT + EN): a matriz de paridade vai de 336 para
  **350 casos** — seis pares novos (`*_named_*`), cada um com o twin `__dark`.
- O port do Modo C acompanha (`client/transpile/components.js`): `controlSemantics`
  é a mesma regra em JS, e a matriz prova que os dois modos produzem a mesma
  árvore — inclusive o campo nomeado pela legenda.

Verificado em Chrome real (Modo B, `tempestweb run`): as três células reportam
`textbox "Quantidade do item 3"`, `textbox "Preço unitário do item 3"` e a nomeada
pela app na árvore de acessibilidade, o wrapper não carrega nome nenhum, digitar
tecla por tecla numa célula sem legenda mantém o valor (`85,40`) através do
rebuild, e o console fica limpo.

## [0.112.0] — 2026-08-25

### Added

- **Web Audio além de um tom: uma frase por chamada, e um medidor (T24)**
  ([#118](https://github.com/mauriciobenjamin700/tempestweb/issues/118)). O
  `webaudio` tinha só `tone` — uma frequência, uma duração, um contexto novo por
  beep. Agora tem três formatos:

  ```python
  result = await native.webaudio.sequence([
      native.webaudio.Step(frequency=261.63, duration_ms=700, gain=0.3),
      native.webaudio.Step(frequency=329.63, duration_ms=700, gain=0.3),
      native.webaudio.Step(frequency=392.00, duration_ms=700, gain=0.3),
  ])                                  # 3 notas juntas = acorde
  await native.webaudio.stop()        # corta sem fechar o contexto

  async for level in native.webaudio.watch_levels():
      app.set_state(lambda s: setattr(s, "vu", level.rms))
  ```

  **`sequence`** agenda a frase inteira numa chamada: cada `Step` ganha oscilador e
  ganho próprios sobre um barramento compartilhado, com envelope de
  `attack_ms`/`release_ms` — sem ele a onda começa e termina no meio do ciclo, e o
  que se ouve é um estalo. Passos com o mesmo `start_ms` soam juntos. **`stop`**
  para os osciladores e deixa o contexto aberto (um `AudioContext` fechado não
  reabre). **`watch_levels`** streama `rms`/`peak`/`bands` de um `AnalyserNode`
  sobre o barramento de síntese (`source="output"`, o default: **sem microfone e
  sem prompt de permissão**) ou sobre o microfone.

  **Grafo de nós arbitrário fica de fora, de propósito:** no Modo B cada chamada de
  capacidade é um round-trip, então uma API na forma do grafo do Web Audio poria a
  rede entre um oscilador e seu ganho. O que uma app precisa de "além de um tom" é
  agendamento e forma, e os dois são por frase.

  Um contexto compartilhado para a app toda, não um por frase: o browser limita
  quantos contextos uma página abre, e uma app que dá beep por contexto bate nesse
  teto.

  **Medido em Chrome real** (`examples/webaudio_demo`, Modo B, análise medindo a
  própria síntese): acorde de 700 ms tocando → `rms 0.365 → 0.376 → 0.353`,
  `peak 0.852 → 0.719`; em **t=720 ms**, quando o release acaba, `0.000`. Arpejo de
  4 notas escalonadas sobe `rms 0.184 → 0.286 → 0.342` conforme elas se sobrepõem.
  Console limpo.

  **Verificado nos Modos A e B.** Em Modo A, origem virgem: acorde reporta
  `3 notas juntas, 700 ms`, o medidor lê `rms 0.374 · peak 0.766` enquanto ele soa,
  e `stop` devolve `parado: 2 osciladores`. O Modo C não compila `async for` para
  stream nenhuma (`statement AsyncFor is not supported`) — pré-existente, vale igual
  para `geolocation.watch` —, então lá o medidor fica fora e `sequence`/`stop`
  compilam.

  `tone` fica **intocado** — uma app que só precisa de um clique continua não
  pagando por mais nada. `Step` é `extra="forbid"` (modelo de opção do
  desenvolvedor: nome errado tem que doer); `SequenceResult` e `Level` ignoram
  extras, para chave nova de cliente novo não quebrar Python antigo.

### Changed

- `docs/advanced/native-reference.md` (PT + EN) documenta os três formatos com o
  porquê da frase-como-unidade; `docs/roadmap.md`: **T24 fecha**;
  `docs/examples/index.md` (PT + EN) lista o demo novo.
- `tempestweb/transpile/_native.py` regenerado — o Modo C expõe
  `sequence`/`stop`/`watch_levels` pela fachada, com os mesmos defaults do `Step`.

## [0.111.0] — 2026-08-25

### Fixed

- **O perf gate reprovou a `main` verde outra vez, agora pela razão de escala.** A
  0.105.0 dizia que a precisão do gate mora nas razões, porque elas são medidas
  entre si na mesma máquina — verdade, mas incompleta: cada medida era a **mediana**
  de cinco rodadas, e num runner compartilhado a interferência segura a maioria das
  rodadas. O `diff` reportou `scale 2.85x` (limite 2,6) sobre a mesma árvore que
  escala **2,01–2,04×** aqui, em três execuções seguidas; a janela de 400 linhas foi
  preemptada e a mediana carregou isso.

  A medida passa a ser a **rodada mais rápida** de cinco. Interferência só consegue
  *somar* tempo, nunca subtrair, então o mínimo é a estimativa menos enviesada do
  que o código custa de fato — e é o que mantém a razão entre dois tamanhos
  significativa. Nenhum limite foi relaxado: `MAX_SCALE_RATIO` fica em 2,6.

  `benchmarks/baseline.json` foi regenerado com o estimador novo (build 680,82,
  diff 21,35 unidades), porque trocar de estimador **é** mudança deliberada de
  medida — os valores medidos caem, então o baseline antigo tornaria o teto de 2,5×
  ainda mais frouxo em vez de mais honesto.

### Changed

- `docs/advanced/observability.md` (PT + EN): a linha da razão de escala explica o
  estimador e cita os números que motivaram a troca.

## [0.110.0] — 2026-08-25

### Fixed

- **O replay da fila offline com a aba fechada nunca funcionou: o worker usava um
  `import()` dinâmico, que a spec proíbe**
  ([#118](https://github.com/mauriciobenjamin700/tempestweb/issues/118)).
  `replayFromSync` (`client/sw/sw.js`) alcançava `client/offline/{store,sync}.js`
  com `await import(...)`. Nenhum service worker pode fazer isso — a spec proíbe
  `import()` no `ServiceWorkerGlobalScope`
  ([w3c/ServiceWorker#1356](https://github.com/w3c/ServiceWorker/issues/1356)) —
  então **todo** `sync`/`periodicsync` estourava e caía no fallback de pingar
  clientes abertos. Com a aba fechada não existe cliente para pingar: a fila ficava
  parada, sem erro visível, e o Background Sync — a única coisa que drena a fila
  sem aba — era decorativo.

  O worker já é registrado como `{ type: "module" }`, então import **estático** é
  legal; só o dinâmico não é. Os dois módulos passam a ser importados no topo, e o
  build reescreve o especificador (`../offline/store.js` no repo →
  `./client/offline/store.js` no artefato, onde o `sw.js` mora na raiz), recusando
  o build se o import mudar de nome.

  **Medido em Chrome real, A/B na mesma máquina, mesmo procedimento, duas origens
  virgens:** duas mutações enfileiradas offline, aba fechada, rede de volta.

  | Worker | Requests no servidor | Fila no IndexedDB |
  |---|---|---|
  | antigo (`import()` dinâmico) | **0** | **2 presas** |
  | novo (import estático) | **2**, 1,01 s após fechar a aba e 3 ms após o reconnect | **vazia** |

  Zero páginas da origem abertas nas duas medições. O `sync` real do Chrome
  disparou sozinho no reconnect — a tag (`tw-offline-replay`) já era registrada
  pelo `enqueue`.

- **Dois guards, porque o teste em Node não podia pegar isto**
  (`tests/unit/test_sw_static_imports.py`): `import()` **funciona** em Node, então
  a suíte jsdom passava verde sobre um worker que o browser recusa. Um guard lê a
  fonte do worker e reprova qualquer `import()`; o outro builda o artefato nos dois
  modos estáticos e confere que o especificador foi reescrito **e** que o arquivo
  apontado foi copiado. Verificado que morde: os quatro reprovam no `sw.js` antigo.

### Changed

- `docs/advanced/offline-sync.md` (PT + EN) e `docs/roadmap.md`: o item P2 de
  "Background Sync com aba fechada" deixa de ser "verificação manual pendente" e
  passa a registrar a medição.

## [0.109.0] — 2026-08-25

### Fixed

- **O sexto componente claro por construção fecha: `Stepper`**
  ([#158](https://github.com/mauriciobenjamin700/tempestweb/issues/158)). Cinco dos
  seis saíram na 0.101.0; o `Stepper` mora no **tempest-core**, então precisava de
  release lá. `tempest-core` 0.16.0 dá a ele `theme`, `variant`, `color_scheme`,
  `size` e `media`, com os botões vindo de `resolve_variant` e o valor lendo o papel
  `ON_SURFACE`. O pin sobe para `tempest-core>=0.16.0`.

  No **Modo C** o componente é composição à mão, então o port em
  `client/transpile/components.js` acompanha: as constantes fixas `MUTED` /
  `ON_SURFACE` saem, o estilo dos botões vem de `resolveWidgetStyle("Button", ...)`,
  o valor de `colorRoles(theme).on_surface` e o `gap` de `SPACING_STEPS.sm`. A
  matriz de paridade foi regenerada do core real — 5 casos mudaram
  (`stepper_default`, `stepper_bounded` e seus twins `__dark` / `__keyed`).

- **`LIGHT_ONLY_COMPONENTS` fica vazia**, e é justamente por isso que a assertion
  continua: o guard de `_dark_sample` reprova o **próximo** componente que nascer
  sem tema, em vez de deixá-lo posar como cobertura de dark. Antes o `Stepper` era
  a única entrada, e ela mascarava 13 pares `__dark` byte a byte iguais ao claro.

### Changed

- `examples/dark-mode` ganha um `Stepper` — o exemplo que existe para provar que a
  cor vem do tema agora inclui o componente que não obedecia.
- `docs/tutorial/theming.md` (PT + EN): o `!!! warning "Stepper continua sem theme"`
  vira `!!! check`, com o que mudou e por que o guard fica.

## [0.108.0] — 2026-08-25

### Fixed

- **`tempestweb.contract` não funcionava instalado do PyPI.** `wire_shape()` e
  `wire_shape_digest()` — exportados no `__all__` do módulo — leem as golden
  fixtures, e elas moram em `tests/fixtures/`, **fora** do diretório do pacote:
  nenhuma delas entrava no wheel. O módulo importava sem erro (as duas constantes
  são literais) e só então levantava `FileNotFoundError`, apontando para um
  `site-packages/tests/fixtures/node_initial.json` que nunca existiu. Quem clonasse
  o repo nunca via; quem instalasse do PyPI via na primeira chamada.

  As três goldens passam a ser force-included no wheel sob `tempestweb/_fixtures/`,
  e a resolução segue o padrão que o cliente JS já usava: pacote primeiro, checkout
  de fonte como fallback. O sdist também passa a incluir `tests/fixtures`. Medido
  no wheel instalado em venv limpo: `wire_shape_digest()` devolve o digest e ele
  bate com `WIRE_SHAPE_DIGEST`.

  `tests/unit/test_wire_contract_freeze.py` ganhou o guard: uma golden nova sem
  entrada no `force-include` reprova ali, em vez de reprovar na máquina de quem
  instalou.

## [0.107.0] — 2026-08-25

### Fixed

- **O gate de performance reprovava a `main` verde por 0,4%.** A checagem de custo
  calibrado tinha tolerância de 1,8× sobre um baseline medido em máquina de
  desenvolvimento, e o merge de #153 caiu em `build costs 1206.9 calibration units,
  baseline 667.7 (limit 1201.9)` — 1,81×. Não era regressão: o **mesmo** código
  mediu 975,8, 1130,9 e 1206,9 unidades em três runners da CI, e o run que reprovou
  foi justamente o de **unidade de calibração mais rápida** (64 µs contra 104 µs).
  Dividir por uma unidade menor infla o custo: a calibração remove clock de CPU, não
  a diferença de memória/GC entre máquinas, então as duas medidas não escalam juntas.

  `MAX_RELATIVE_REGRESSION` vai a **2,5×** e passa a ser o que sempre foi de fato —
  tripwire grosso, que pega uma duplicação de custo. A precisão do gate fica nas
  razões de escala (`MAX_SCALE_RATIO`, 2,6×) e na contagem de patches, que são
  medidas **entre si** na mesma máquina e por isso imunes ao runner. O teste de
  ruído passa a fixar 1,81× — o número real que a CI produziu —, logo apertar a
  tolerância de novo reprova em `tests/unit/test_perf_gate.py` em vez de deixar a
  `main` vermelha no merge seguinte. `docs/advanced/observability.md` (PT + EN)
  registra o spread medido.

## [0.106.0] — 2026-08-25

### Added

- **Gate de acessibilidade que trava de verdade**
  ([#121](https://github.com/mauriciobenjamin700/tempestweb/issues/121)).
  `docs/stability.md` declarava baseline de a11y e nada media: o job Lighthouse
  roda com `|| echo soft-fail`, ou seja, não bloqueia nada — e um `IconButton`
  chegou a produção como `div` sem foco e sem nome acessível sem nenhum job
  reclamar (#109).

  O job `a11y` do CI roda **axe-core** sobre o DOM que o renderizador de verdade
  constrói e falha em violação `serious`/`critical`. As cenas são **geradas dos
  apps que o repo entrega** (`tests/conformance/_a11y_scenes.py`): galeria de
  componentes do Modo C, painel de controles, lista com campo, formulário, casca
  de navegação e tela de imagens — auditar markup escrito à mão provaria que o
  snippet do teste é acessível, não que o renderizador é.

  Verificado que morde: imagem sem `alt` reprova como `critical` (`image-alt`),
  botão sem nome reprova (`button-name`, a forma exata da #109) e `role` inválido
  vindo de `semantics` reprova (`aria-roles`).

- **O wire-contract é congelado** — `tempestweb.contract` expõe
  `WIRE_CONTRACT_VERSION` (versão própria, independente da versão do pacote) e
  `WIRE_SHAPE_DIGEST`, o hash da **forma** do fio (cada chave e seu tipo, nunca o
  valor). As golden fixtures travavam drift acidental mas são regeneráveis do
  core, então não distinguiam "regenerei" de "mudei o contrato".

  `tests/unit/test_wire_contract_freeze.py` reprova mudança de forma e diz qual
  escolha o autor deve: aditiva (chave opcional nova, `kind` novo, `type` novo →
  digest novo, versão igual, entrada no CHANGELOG) ou quebra (renomear, remover,
  retipar, mudar semântica de patch → bump da versão + nota de migração).
  Regenerar fixture com valores novos do **mesmo tipo** não mexe no digest.

  Uma borda fica registrada em teste em vez de virar susto: campo `null` na
  fixture é gravado com o tipo `null`, então regenerar com um valor **move** o
  digest — resposta certa (o cliente que só via nada agora tem tipo para parsear),
  mas produzida por um valor. O outro lado é o limite real: enquanto um campo
  nullable continuar `null` em toda fixture, o tipo declarado dele **não** está
  pinado por este digest.

### Fixed

- **O gate novo pegou duas violações críticas na primeira execução** — as duas
  entraram na 0.98.0 e são exatamente a classe de coisa que ele existe para achar:

  - **`aria-expanded` num `div` sem role é ARIA inválido** (`aria-allowed-attr`).
    O `RouteDrawer` o escrevia; "expandido" descreve o **controle** que abre a
    gaveta (o botão da app), não o painel. Fechado, o painel agora diz o que
    é verdade sobre ele: `aria-hidden="true"`.
  - **Controle embrulhado ficava sem nome acessível** (`label`). Um `<label>`
    nomeia o input pelo **texto**; quando a app nomeia por `semantics`, o
    `aria-label` cai no wrapper e não nomeia o controle dentro dele. O nome passa
    a ser copiado para dentro — e só quando não há legenda visível, porque dois
    nomes num controle é pior que um. `examples/settings-panel` ganhou o nome nos
    seis controles que tinham só um `Text` ao lado.

- **Os dois thumbs do `RangeSlider` não tinham nome acessível** (`label`,
  `critical`) — nos **dois** renderizadores, DOM e SSR. O wrapper é um `<div>` sem
  role, então o `aria-label` dele não nomeia nada que o leitor alcance: o leitor
  para nos dois `<input type="range">` que o renderizador cria. Medido em
  `examples/booking-form`: o widget carregava `semantics.label` e os dois thumbs
  continuavam anônimos, porque o nome parava no wrapper.

  Cada thumb passa a ser nomeado pelo widget **mais a ponta que ele move**
  (`Fare window (minimum)` / `(maximum)`; sem `semantics`, `Minimum` / `Maximum`),
  porque dois controles anunciados igual são o mesmo defeito de terno.

- **O `Dropdown` do `examples/booking-form` não tinha nome** (`select-name`,
  `critical`): um `<select>` solto, nomeado só por um `Text` ao lado. Ganhou
  `semantics`, como os do `settings-panel`.

### Changed

- **As cenas do gate cobriam 17 tipos de widget e deixavam sete controles de fora**
  — justamente os que a #143 acabara de fazer falar (range slider, dropdown,
  autocomplete, os dois pickers, file picker, tab bar). Diversidade se mede por
  **tipo de widget**, não por número de telas: `booking-form`,
  `search-autocomplete` e `tabs-profile` entraram, e as duas violações críticas
  acima apareceram na hora. Nove cenas.

- **`KNOWN_EXCEPTIONS` agora não pode apodrecer em silêncio.** O docstring
  prometia que o gate reportaria exceção que parou de disparar, e ele não podia:
  a passada bloqueante desliga essas regras, e regra desligada não produz
  resultado nenhum. Uma segunda passada reabilita só o que é julgável em jsdom e
  reporta o que ficou obsoleto.

  Ela achou algo na estreia: `landmark-one-main`, `page-has-heading-one` e
  `region` são regras de documento e **nunca** disparam quando o contexto é o
  elemento de mount — as três saíram da lista. Sobra `color-contrast`, marcada
  como não-julgável aqui (precisa de layout, amostra cor por canvas), então a
  passada de obsolescência não a acusa nem finge medi-la.

- `docs/stability.md` (PT + EN) descreve o que o gate pega e o que fica para a
  camada Lighthouse (contraste e instalabilidade precisam de layout real), e a
  tabela de compatibilidade do wire. `docs/roadmap.md`: S10 fecha.
- `axe-core` entra como `devDependency` e `npm run a11y` roda o gate local.
- **`WIRE_SHAPE_DIGEST` reflete o envelope `theme`.** O congelamento do wire e a
  chegada do envelope de tema nasceram em frentes paralelas: cada uma passava
  sozinha e o digest reprovava na integração — o guard fazendo o trabalho dele.
  A mudança é **aditiva** (uma `EnvelopeKind` nova, nenhuma chave renomeada ou
  retipada), então `WIRE_CONTRACT_VERSION` fica em `1` e só o digest muda.
## [0.105.0] — 2026-08-25

### Added

- **Gate de performance no CI**
  ([#120](https://github.com/mauriciobenjamin700/tempestweb/issues/120)).
  `benchmarks/bench_reconcile.py` existia e ninguém rodava: uma mudança que
  dobrasse o custo de `diff` passava por todo o gate atual, porque ruff, mypy,
  pytest e jsdom são de correção — nenhum de tempo.

  `benchmarks/perf_gate.py` roda no CI e falha o job. O difícil num gate de perf
  não é medir, é **não ser flake**: runner compartilhado varia mais do que as
  regressões que valem pegar. Então ele afirma só o que sobrevive a máquina lenta:
  **escala** (dobrar as linhas custa no máximo ~2,6× — `O(n²)` aparece perto de
  4×, e a razão é imune à velocidade da máquina), **patch mínimo** (1 mudança → 2
  patches; o jeito mais barato de fazer um diff parecer rápido é parar de estar
  certo), **custo calibrado** (dividido por um laço medido no mesmo processo, com
  tolerância de 1,8×) e **escala de sessões**.

- **Throughput do Modo B** (`benchmarks/bench_ws_throughput.py`): mede o loop em
  que o app vive — evento, handler, diff, lote no transporte — com uma sessão e
  com N concorrentes. Medido: **o total fica praticamente constante** (~1.000
  eventos/s nesta máquina) e a fatia por sessão divide. Ou seja, Modo B satura em
  CPU no rebuild, dentro de um único event loop: escalar é mais processo, não mais
  thread. O gate fixa essa forma — queda no total é contenção, não carga.

- **Cold-start do Modo A** (`benchmarks/bench_cold_start.mjs` + workflow
  `perf-cold-start.yml`): mede **cold** (sem SW/cache: Pyodide e core pela rede) e
  **warm** (precache do SW) até a primeira árvore na tela. Roda em **schedule**, e
  não em PR, porque um download desse tamanho no caminho crítico de cada PR compra
  um número que ninguém lê naquele momento.

  Primeira medição, em Chrome real com o artefato buildado do `examples/counter`:
  **cold 2.394 ms / 14.593 KB**, **warm 2.354 ms / 8.751 KB**. O service worker
  poupou 5,8 MB de rede e **40 ms** — 40% dos bytes, 1,7% do relógio. A leitura é
  o que importa: no Modo A o custo dominante é o **boot do Pyodide (CPU)**, não o
  download, então otimizar rede ali não move a agulha.

### Changed

- `docs/advanced/observability.md` (PT + EN) documenta as três medidas e o porquê
  de cada limite. `docs/roadmap.md`: S9 fecha.
- `benchmarks/baseline.json` guarda o baseline calibrado, versionado; mudança
  deliberada de custo usa `--update-baseline` e se justifica no PR.

Gate verificado que morde, com teste por regra
(`tests/unit/test_perf_gate.py`): `diff` escalando 4,1× reprova citando `O(n^2)`;
1 patch em vez de 2 reprova; custo calibrado 2× reprova; ruído de 30% **passa**
(era o requisito para o gate não ser desligado na primeira semana); e throughput
total caindo a 0,30× reprova falando de contenção.
## [0.104.0] — 2026-08-25

### Added

- **Observabilidade de servidor (S8)**
  ([#119](https://github.com/mauriciobenjamin700/tempestweb/issues/119)).
  `metrics=True` respondia **quantas** sessões existem; não respondia se estão
  lentas, onde o tempo é gasto, nem o que o servidor fez para o cliente que
  reclamou.

  `create_app(..., observability=ServerObservability(...))` liga três coisas
  independentes:

  - **Latência e throughput** — histograma `tempestweb_patch_seconds` +
    `tempestweb_patches_total` no mesmo `GET /metrics`. Mede a espera que o
    **cliente** sente: do evento chegar até os patches irem para o transporte,
    **rebuild incluído**. Isso importa porque o rebuild é coalescido e roda depois
    do handler retornar — cronometrar o handler dava rodadas com **zero patches**,
    que foi como o defeito apareceu na medição.
  - **Log estruturado** — uma linha JSON por evento de sessão (`session.open` /
    `session.close`), com `session_id` como **campo** e `reason` sendo o nome da
    exceção quando a sessão morre de erro. `json_log_sink` é o sink novo.
  - **Tracing** — span por sessão, por dispatch e por lote, atrás de adapter.
    `otel_tracer()` importa `opentelemetry` **dentro da função**, e o extra novo
    `tempestweb[otel]` traz só a API: exporter e sampler ficam com o
    OpenTelemetry, onde já são configuráveis.

  Nada disso é dependência forçada: o default é inerte — nenhum import, nenhum
  relógio, nenhum span. Medido: com métricas **e** log ligados, 200 cliques
  passaram de 0,665 ms para 0,689 ms de média (**+3,6%**).

### Changed

- `AppSession` aceita `observability` e `session_id`. O import do tipo é
  `TYPE_CHECKING`-only porque o bundle do Modo A carrega esse módulo e não deve
  carregar a observabilidade de servidor com ele (o teste de fechamento do bundle
  pega isso).
- `docs/advanced/observability.md` (PT + EN) documenta as três partes, incluindo o
  custo medido e por que o histograma não fica em volta do handler.
  `docs/roadmap.md`: S8 fecha.

Verificado ao vivo num app Modo B com cliente WebSocket real: 40 cliques → 40 no
histograma, 40 patches contados; cliente mediu 0,62 ms de ida e volta e o servidor
0,30 ms de tempo de patch (49% da espera), ou seja o número do servidor bate e é o
menor, como tem de ser. O log da sessão saiu parseável, com o mesmo `session_id`
nos dois eventos.
## [0.103.0] — 2026-08-24

### Added

- **`[pwa]` ganhou switch: dá para desligar o service worker no build**
  ([#161](https://github.com/mauriciobenjamin700/tempestweb/issues/161)). Todo
  build emitia `sw.js` + `register.js` e registrava o worker no `index.html`;
  `PwaConfig` só permitia customizar o manifest, e o emissor não olhava nada
  parecido. Sem switch, a saída era strippar o artefato depois do build com
  regex sobre HTML gerado.

  ```toml
  [pwa]
  enabled = false          # o default das duas metades
  manifest = true          # nomear uma metade sobrepõe o enabled
  service_worker = false
  ```

  Os dois eixos ficam separados porque as metades são úteis apart: o manifest
  sozinho torna a app instalável e a nomeia na home screen; o worker é o que
  precacheia a shell. Vale nos dois modos estáticos (A e C). Campo que não for
  booleano é recusado — `service_worker = "false"` é truthy em Python, e um
  switch cujo trabalho é desligar algo não pode fazer o oposto do que se lê.

- **`client/sw/sw-teardown.js`**, o worker que um build emite quando o service
  worker está desligado. Desligar não é o mesmo que nunca ter ligado: quem já
  visitou a app tem o worker registrado, e worker registrado continua servindo a
  shell do precache até ser substituído. Emitir nada deixaria essas pessoas
  presas ao build antigo, sem nada no deploy capaz de alcançá-las — worker
  registrado revalida o próprio script, então a única via é um worker na mesma
  URL. O de teardown limpa todo cache do origin, se desregistra e recarrega as
  páginas que controlava.

### Fixed

- **O app shell do worker passa a seguir os switches.** A lista de precache
  nomeava `manifest.webmanifest` e `register.js` incondicionalmente, então
  `[pwa] manifest = false` com o worker ligado emitia um `sw.js` cujo shell
  apontava para um arquivo que o build não escreveu. O worker instala com
  `cache.addAll`, que **rejeita o lote inteiro** quando qualquer request falha —
  então isso não degradava o precache, matava a instalação: registro descartado,
  cache vazio, e nada no console. Medido em Chrome: **0 registros, 0 entradas em
  cache**, com a página montando normalmente. Corrigido, e medido de novo: 1
  worker ativo, 102 entradas.

  O guard novo (`test_every_precached_url_exists_in_the_artifact`) confere que
  **toda** URL do app shell existe no artefato, nos dois modos e nas quatro
  combinações de switch — a classe inteira do defeito, não só este caso.

### Changed

- O banner de conectividade continua montando num artefato sem service worker:
  ele reporta a rede, não o precache.
- `docs/advanced/pwa.md` (+ EN) ganhou a seção **Desligando o PWA**, com o custo
  do worker para quem não precisa dele e a tabela do que muda no artefato.
  `docs/advanced/transpile.md` (+ EN) lista os três campos novos.
## [0.102.0] — 2026-08-24

### Fixed

- **O Modo A não pedia resync, então um patch que falhava truncava a tela para
  sempre** ([#159](https://github.com/mauriciobenjamin700/tempestweb/issues/159)).
  O `onPatchFailure` do `mount` só pede reparo quando o transporte sabe pedir, e
  `client/transport-wasm.js` não implementava `requestResync` — no Modo A o
  handler degenerava em `console.error` e retornava. Dali em diante a árvore do
  cliente não tinha conserto: todo patch seguinte é index-relativo a uma árvore
  que não existe mais, então cada tick falhava igual e a tela ficava faltando
  pedaço. No tempest-webtunnel isso significou um painel sem o botão Sair, sem um
  campo do formulário e sem uma coluna da tabela, por semanas, com o console
  reclamando a cada 7 segundos.

  `WasmRuntime.dispatch_event` ganhou o branch `resync` que faltava (só o
  `AppSession.dispatch` do Modo B tratava o tipo) e um `WasmRuntime.resync()` que
  reenvia a scene atual como `Replace` de raiz, com os overlays abertos seguindo
  como inserts sob `overlay` — o mount inicial do Modo A entrega só o nó raiz,
  então um diálogo aberto sumiria de um resync que reenviasse só a raiz.

  O pedido viaja como evento de fio comum, igual ao Modo B, e o runtime o serve
  em vez de rotear para handler de app: o `key` vazio nunca precisa resolver para
  um widget.

- **O bootstrap do Modo A descartava, em silêncio, lote entregue antes do
  transporte existir.** `start()` constrói o app e já inicia o loop de rebuild,
  mas o transporte JS só nasce algumas instruções depois; o `onPatches` gerado
  entregava o lote quando `deliverToTransport` estava setado e o **jogava fora**
  caso contrário. Agora é bufferizado e drenado em ordem no `onDeliver` —
  seguro, porque o nó inicial é um snapshot tirado dentro de `start()`, do qual
  os lotes bufferizados diffam.

### Added

- **A falha de patch passa a dizer o que o cliente tem**
  ([#160](https://github.com/mauriciobenjamin700/tempestweb/issues/160)). A
  mensagem era `patch path out of range at index N`: não nomeava o path inteiro,
  nem o passo que falhou, nem o nó que o cliente tem ali, nem quantos filhos ele
  tem contra o índice pedido — diagnosticar uma ocorrência exigia patchar
  `client/dom.js` dentro do artefato buildado. Agora carrega os quatro, com o pai
  identificado por `data-tw-key`.

- **`globalThis.__tempestweb_debug` liga o log do stream de patches:** uma linha
  numerada por lote, mais um outline da árvore que o cliente tem no lote que
  falha. A flag é lida a cada lote, não capturada no mount, porque ela existe
  para ser ligada pelo console de uma página que já está com problema.

  A lista de filhos na mensagem é truncada em 12, com a contagem real ao lado:
  uma lista virtualizada tem centenas de filhos, e imprimir todos transformaria a
  única linha útil do console num muro ilegível.

- Transporte sem `requestResync` passa a reclamar alto em vez de sair calado.

- **O resync passa a substituir a camada de overlay, em vez de empilhar sobre
  ela.** Um resync carrega todo overlay aberto como `Insert`, e insert
  **adiciona**: um diálogo aberto na hora da falha voltava uma segunda vez, em
  cima do primeiro, e cada resync seguinte somava mais um. Agora o cliente esvazia
  a camada antes de aplicar os inserts — **só** num resync, porque um `Replace` de
  raiz comum vindo do diff não reenvia overlay que não mudou, e limpar ali apagaria
  um diálogo que ninguém repõe. Vale nos três modos: o Modo B chega no mesmo
  código de cliente com o mesmo lote.

- **`WasmRuntime.resync()` deixa de derrubar o loop de eventos num transporte
  fechado.** É o único branch de `dispatch_event` que aguarda o transporte
  diretamente — os outros passam trabalho para o `set_state` e deixam o loop de
  rebuild agendar o envio — então era o único que podia levantar
  `TransportClosedError` na hora do dispatch. O `run()` só captura esse erro em
  volta do `recv_event`, então um resync chegando enquanto a aba fecha matava o
  loop inteiro na saída. O `AppSession` do Modo B guarda o mesmo caso com o
  `_closed`.

### Changed

- `docs/troubleshooting.md` (+ EN) ganhou a seção **Render e patches**, com a
  entrada de `patch path out of range` e o procedimento de investigação.
## [0.101.0] — 2026-08-24

### Fixed

- **Cinco componentes eram claros por construção: `TextField`, `EmailField`,
  `PasswordField`, `LoginForm` e `SignupForm` não aceitavam tema**
  ([#158](https://github.com/mauriciobenjamin700/tempestweb/issues/158)). Nenhum
  declarava `theme`, e nenhum repassava tema nenhum para os widgets do core que
  constrói, então ficavam **claros num app escuro** — nos três modos. Não era
  regressão: era como sempre foram, e os docstrings diziam
  ("styled for the Material 3 **light** surface").

  O idioma que a doc ensina é `theme=app.theme` em cada widget. Um usuário que
  seguia isso e usava `TextField` num app escuro recebia um campo claro sem
  nenhum aviso — e o pior caso é fundo escuro (folha base) com texto escuro
  (inline), ou seja, ilegível.

  Os cinco passam a declarar `theme` (com `default_factory=current_theme`, como
  todo widget colorido do core) e a repassá-lo para tudo que constroem: o
  `Input` de cada campo, os campos e o botão de submit de cada form. As cores do
  label e da linha de erro deixam de ser hex fixo (`#49454f` / `#b3261e`) e
  passam a sair dos papéis `on_surface_variant` / `error` do esquema do tema —
  `Text` não aceita tema próprio, então elas são resolvidas pelo componente e
  passam como style inline.

  O builder do Modo C acompanha (`client/transpile/components.js`): o `Input` de
  cada campo e o botão de cada form recebem o tema, e as duas constantes de cor
  viram `colorRoles(theme)`.

- **A matriz de paridade do Modo C deixa de ter treze pares vazios.** Com os
  cinco tematizáveis, `LIGHT_ONLY_COMPONENTS` cai de seis nomes para um, e o
  guard passa a **exigir** que o par `__dark` deles difira do claro — sem
  nenhuma mudança no teste, que já pinava a divisão nas duas direções.

### Known issues

- **`Stepper` continua sem `theme`.** Ele mora no `tempest-core`, que é outro
  repositório: dar tema a ele é um release do core, não uma mudança aqui. É o
  único nome que sobra em `LIGHT_ONLY_COMPONENTS`, com o motivo escrito ao lado.

### Changed

- `docs/tutorial/theming.md` (+ EN) ganhou **Os componentes do tempestweb seguem
  o mesmo idioma**, e a nota que dizia que `TextField` mantinha a paleta default
  deixou de valer para ele (segue valendo para o `SearchBar` do core).
- `examples/login_demo` passa `theme=app.theme` — é a documentação executável do
  `LoginForm`, e estava ensinando a forma que ignora o tema.
- `docs/advanced/transpile.md` (+ EN) dizia que a matriz de paridade tem **185**
  casos; ela tem **336** (151 componentes × claro/escuro, mais 34 pares
  `__keyed`). O número parou em 185 quando a #106 introduziu o eixo de modo, e a
  página passou a subestimar a própria cobertura em quase metade. Agora um guard
  (`tests/unit/test_docs_matrix_count.py`) compara a prosa das duas línguas com o
  tamanho real da fixture, porque a contagem muda exatamente quando ninguém
  lembra de procurar na doc.

## [0.100.0] — 2026-08-23

### Fixed

- **`theme_css` ainda escurecia a página pelo SO, contra a política que este
  próprio release estabelece.** A folha base recusa `prefers-color-scheme` de
  propósito — o core resolve um tema `SYSTEM` como **claro** para todo widget,
  porque widget não vê o SO — mas `theme_css` continuava emitindo
  `@media (prefers-color-scheme: dark)`. No Modo A, que injeta esse CSS sozinho,
  um app com `Theme(mode=SYSTEM)` num SO escuro ficava exatamente com a árvore
  clara sobre página escura que a política existe para evitar.

  Agora o bloco escuro sai sob `:root[data-tw-theme="dark"]`, o mesmo
  interruptor da folha: as duas metades viram juntas, no modo que a app resolveu.

- **Tema fixado em `DARK` perdia a paleta da app para a folha base.** O bloco
  escuro da folha é `:root[data-tw-theme="dark"]` (0,1,1) e o da app saía em
  `:root` (0,1,0) — então, no instante em que a página escurecia, o rebrand
  revertia para o roxo do baseline. A folha base é piso, não gaiola: um tema
  fixado passa a emitir seu esquema nos dois seletores, empatando a
  especificidade, e a app ganha por vir depois no `<head>`.

- **Metade do dark mode continuava clara: a folha base não tinha eixo de modo**
  ([#148](https://github.com/mauriciobenjamin700/tempestweb/issues/148)). O
  `Style` que o core resolve viaja inline e ganha do stylesheet, então `Card` e
  `Button` já seguiam o tema. O que só a folha pinta — fundo da página,
  superfície de campo, `::placeholder`, `:hover`/`:focus`, superfície de overlay —
  não tinha modo nenhum: um app escuro mostrava campo branco dentro de cartão
  escuro.

  A folha ganha um bloco de tokens dark sob `[data-tw-theme="dark"]`, e o
  renderizador marca o documento com o modo resolvido. O canal segue o padrão que
  o `navigate` já usava: envelope `{"kind": "theme", "mode": "dark"}` nos Modos B
  e SSE, callback `on_theme` no Modo A (o Python divide a aba), e marcação
  em-processo no `set_theme` do Modo C.

  Três decisões que valem a leitura, porque cada uma tem um jeito errado óbvio:

  - **O modo é resolvido como um widget resolve** (`Theme.is_dark()`, sem a flag
    de plataforma). Um tema `SYSTEM` resolve claro no core, então escurecer por
    `prefers-color-scheme` colocaria árvore clara em página escura — motivo pelo
    qual a media query **não** entrou. Quem quer seguir o SO lê
    `app.media.platform_dark_mode` no `view` e chama `set_theme`.
  - **O primeiro `light` não é enviado:** os tokens da folha são a paleta clara,
    então seria um frame dizendo o que o CSS já diz. Toda mudança posterior vai,
    inclusive a volta ao claro.
  - **O modo é checado depois de cada handler**, não só quando há patch: uma troca
    de tema numa app cujo `view` não repassa o tema reconstrói para a IR idêntica,
    o core não emite patch, e a folha ficaria clara sob uma app que foi ao escuro.

### Added

- **Gate de contraste da paleta** (`tests/client/theme-contrast.test.js`). A regra
  `color-contrast` do axe precisa de layout, então o gate de a11y a desliga, e o
  job Lighthouse que a pegaria num browser real roda com `|| echo soft-fail` —
  ou seja, uma paleta escura inteira entrou sem nada no CI capaz de distinguir
  legível de ilegível.

  A metade que **não** precisa de layout é o par de papéis: `--tw-on-surface` é,
  por definição, o que vai sobre `--tw-surface`. O teste calcula os 12 pares que a
  folha promete, nos dois modos (o bloco escuro sobreposto ao claro, que é o que o
  leitor recebe), e reprova abaixo de AA — 4,5:1 para texto, 3:1 para `outline`,
  que é fronteira. Um terceiro caso prova que ele morde: escurecer um primeiro
  plano sem o fundo reprova.

  Medido: no claro o par mais apertado é `warning` sobre `surface`, **6,02:1**; no
  escuro, `on-secondary-container` sobre `secondary-container`, **7,19:1**. O que
  continua precisando de browser — se um widget de fato usou o par que devia — fica
  com o Lighthouse.

- `applyThemeMode` / `THEME_MODE_ATTR` em `client/theme.js`, `encode_theme` +
  `PatchTransport.send_theme` nos transportes, `on_theme` no `WasmRuntime` e no
  `bootstrap` do Modo A.
- Seção **"A folha base segue o modo que você declara"** no tutorial de tema
  (PT + EN), com o aviso medido: declarou escuro, repasse `app.theme` aos widgets
  — senão a folha escurece e o inline continua claro (campo ilegível).
- `docs/contract.md` documenta o envelope ao lado do `navigate`.
- `tests/unit/test_theme_envelope.py` fixa as três decisões acima;
  `tests/client/theme.test.js` fixa o bloco de tokens e a marcação;
  `tests/client/transport-ws.test.js` fixa o roteamento do envelope.

Medido em Chrome real (Modo B): clicar "Dark" no `examples/theme-switcher` leva o
documento a `data-tw-theme="dark"`, os tokens de `#fef7ff`/`#1d1b20`/`#6750a4`
para `#141218`/`#e6e0e9`/`#d0bcff` e o `body` para `rgb(20,18,24)`; voltar desfaz.
Num app que repassa o tema, o campo vai de `rgb(254,247,255)/rgb(25,25,26)` para
`rgb(20,18,24)/rgb(229,229,230)` — fundo escuro **com** texto claro — o
`::placeholder` acompanha, e digitar continua funcionando. Console limpo.
## [0.99.0] — 2026-08-23

### Fixed

- **Dark mode não alcançava widget nem componente em Modo C**
  ([#106](https://github.com/mauriciobenjamin700/tempestweb/issues/106)). As
  tabelas de estilo geradas (`widget-styles.gen.js`, `component-styles.gen.js`)
  eram geradas com o tema default, então todo widget e todo componente
  transpilado renderizava a paleta clara — e como o estilo inline resolvido ganha
  do stylesheet, era a metade com precedência que falhava.

  As tabelas ganham eixo de modo (o mais interno em `WIDGET_STYLES`, para
  duplicar folha e não árvore de chaves; no topo nas sete tabelas de componente
  que carregam cor), e os builders gerados passam a aceitar `theme` — o campo que
  o core declara e que não cruza o fio — escolhendo a folha por
  `theme.is_dark()`, com `light` como queda quando não há tema, exatamente como o
  core resolve um widget sem tema.

  **Custo medido, não estimado:** a tabela de widgets tinha 725K com um modo
  (pretty printed); emitida compacta com os **dois** modos, 605K — menor do que
  antes. Comprimida, a diferença entre um e dois modos é da ordem de 6K.

  Os 47 componentes portados propagam o tema como o core propaga, componente por
  componente: um `*Input` **é** o campo e repassa; um `SearchBar`/`*Field` compõe
  um e sobrepõe o estilo resolvido, então o campo interno mantém a paleta
  default. A matriz de paridade ganhou um par `__dark` por caso (185 → 336
  amostras), que é o que fixa cada uma dessas decisões.

  **Seis componentes ficam de fora, e agora isso está escrito:** `TextField`,
  `EmailField`, `PasswordField`, `LoginForm`, `SignupForm` e `Stepper` não
  declaram campo `theme` — são claros por construção, como os docstrings deles já
  diziam ("styled for the Material 3 light surface"). O par `__dark` deles é
  byte a byte igual ao claro. O par continua valendo (fixa que o port JS ignora o
  tema **exatamente** como o core ignora), mas não prova nada sobre escuro, e a
  matriz lia como mais cobertura do que tem.

  `LIGHT_ONLY_COMPONENTS` nomeia os seis com o motivo, e
  `tests/transpile/test_component_dark_axis.py` fixa a divisão nas duas direções:
  componente que **pode** ser tematizado e mostra cor tem que diferir no escuro
  (é a asserção da #106 no nível de componente), e a lista não pode apodrecer —
  quem ganhar tematização sai dela, quem perder entra, e o gerador reprova até
  isso ser feito. As três direções foram provadas por mutação.

  Isso importa porque `model_copy(update={"theme": ...})` **pula a validação**:
  `TextField` recusa o kwarg (`extra_forbidden`), e o gerador injetava de qualquer
  forma um atributo que o core ignora. O caso "escuro" saía sendo o caso claro com
  outro nome — que é exatamente a forma do defeito que a #106 existe para pegar.

### Added

- **`examples/dark-mode`** — o idioma `theme=app.theme` numa tela com `Card`,
  `Badge`, `Input`, `Button` e `Alert`, com dois botões que trocam o tema em
  runtime.
- Seção **"Modo escuro: passe o tema ao widget"** no tutorial de tema (PT + EN),
  entrada no troubleshooting nas duas línguas, e página do exemplo novo.
- `test_mode_free_component_tables_really_are_mode_free` — `SHAPE_STEPS` e
  `TYPOGRAPHY` são emitidas planas porque não carregam cor; o teste prova isso
  contra o core, para o dia em que deixar de valer.

Medido em Chrome real, Modo B e Modo C, com **os mesmos** valores computados nos
dois — e eles são os que o core resolve: `Button` `rgb(88,71,133)` →
`rgb(199,193,215)`, `Card` `rgb(252,252,252)` → `rgb(25,25,26)`, `Alert`
`rgb(219,226,240)` → `rgb(29,59,124)`; voltar para Light desfaz; console limpo.

!!! warning "A folha base continua clara"
    O que só a folha base pinta (fundo do `Input`, fundo da página, hover/foco)
    segue sem eixo de modo — rastreado em
    [#148](https://github.com/mauriciobenjamin700/tempestweb/issues/148).

## [0.98.0] — 2026-08-23

### Fixed

- **Onze widgets de IR interativos desenhavam um `<div>` anônimo**
  ([#143](https://github.com/mauriciobenjamin700/tempestweb/issues/143)) — a
  auditoria que a [#130](https://github.com/mauriciobenjamin700/tempestweb/issues/130)
  pediu, feita e medida. `Switch`, `Slider`, `RangeSlider`, `Dropdown`,
  `Autocomplete`, `DatePicker`, `TimePicker`, `FilePicker` e `TabBar` passam a
  renderizar o controle nativo equivalente; `TabView` e `RouteDrawer` continuam
  `div` por decisão documentada (os dois têm filho de IR, então strip criado pelo
  renderizador cairia no índice que os patch paths endereçam) e passam a dizer o
  estado — `role=tabpanel` + nome da aba ativa, `data-tw-open` + `aria-expanded`.

  Vale nos três modos, porque `client/dom.js` é o renderizador compartilhado.

- **O payload do evento tinha a forma do DOM, não a do widget.**
  `ToggleEvent(checked)` nunca validava contra `{"value": "on"}`, então o handler
  de **todo `Checkbox`** recebia o dict cru — `event.checked` era um
  `AttributeError` esperando o primeiro clique. Agora `Checkbox`/`Switch` mandam
  `checked`, `Slider` manda número, `RangeSlider` manda o par `low`/`high`
  normalizado, `Dropdown`/`FilePicker` reportam `select` com índice/nome.

- **Modo C mapeava `on_change` para `click`** em seis widgets (`Switch`,
  `Slider`, `RangeSlider`, `Autocomplete`, `DatePicker`, `TimePicker`): cada um
  renderizava, aceitava input e nunca avisava a app. A derivação lia a tabela de
  tags e somava `Checkbox` à mão — qualquer widget que embrulha o controle num
  `<label>` lia como `div`. O gerador passa a ler `NATIVE_CONTROL_TYPES` /
  `CHANGE_REPORTING_TYPES` declarados no próprio renderizador.

- **O Style resolvido descreve peças desenhadas à mão.** Medido em Chrome: o
  `Switch` era um quadrado de 20x20 com um checkbox de 52x32 pendurado para fora,
  os `Slider` tinham 4px de altura (alvo de toque de 4px) e o `Checkbox` escondia
  a própria legenda. `styleToCss` e o port `style_to_css` passam a descartar a
  geometria/pintura de peça desses quatro tipos e a reemitir a cor resolvida como
  `accent-color` — e também como `--tw-control-accent`, porque a folha base
  pinta o track do `Switch` e não consegue ler `accent-color`: um app azul
  mostrava um switch roxo.

- **Pickers estouravam a tela em 390px** (um `<input type=file>` não encolhe:
  empurrava a página 101px) e o **`aria-label` do `TabView` ficava preso na
  primeira aba** (era escrito só quando ausente, e o Update que troca de aba
  carrega `active` sozinho).

- **O renderizador SSR estava cinco widgets atrás do cliente**: os campos da
  #142 (`TextArea`, `MaskedInput`, `PinInput`) nunca foram portados, então a
  mesma árvore era campo digitável no browser e caixa morta na página estática.
  Portados, com um teste que trava as duas tabelas de tags.

### Added

- **`examples/booking-form`** — `DatePicker`, `TimePicker`, `RangeSlider`,
  `Dropdown` e `FilePicker` ligados a um dataclass, com resumo ao vivo. Os quatro
  primeiros não tinham exemplo nenhum, então não havia onde exercitá-los.
- **`docs/tutorial/controls.md`** (PT + EN) — o mapa widget → elemento → evento
  dos catorze controles, e por que `TabBar` desenha a faixa que o `TabView` não
  pode desenhar.
- **`tests/unit/test_renderer_control_coverage.py`** — a auditoria manual virou
  gate: todo widget interativo do core é controle desenhado ou exceção listada, e
  o motivo de cada exceção é conferido contra o core.

Medido em Chrome real (Modo B e Modo C, 390px e 1280px, console limpo): clique
real no `Switch` alterna o estado, arrasto move o `Slider` de 70% para 25%,
`ArrowRight` move a fonte de 16pt para 18pt, arrastar o polegar baixo do
`RangeSlider` reporta o par normalizado, seleção no `Dropdown` reporta índice 2,
upload real chega como `passaporte.txt`, digitar filtra o `Autocomplete` de 20
para 3 opções, clique na 3ª aba troca o painel, e a gaveta sai de
`translateX(-260px)` para `0`.
## [0.97.0] — 2026-08-23

### Fixed

- **Lista virtualizada travava vazia depois de encurtar**
  ([#133](https://github.com/mauriciobenjamin700/tempestweb/issues/133)). Uma
  janela deslizada fundo contra uma lista que encurta resolve para vazio — o
  `_resolve_window` do core prende o `start` na contagem, e `[45, 75)` contra 25
  itens vira `[25, 25)`. Sem linha não há scroll, e sem scroll não há evento que
  a recupere.

  O controlador de virtualização passa a se recuperar depois de cada lote de
  patches: uma lista **com** itens que não materializou nenhum, ou cuja janela
  começa além da última página, pede a última página. Os dois sinais são
  necessários porque só um sobrevive em cada modo — quando a app declara
  `window`, o `start` está no elemento; quando ele é deslizado em runtime, o
  elemento ainda lê 0, e o que entrega o estado travado é a lista com itens sem
  nenhuma linha.

  É rede de segurança, não a correção da regra: onde a janela **resolve**
  continua sendo resposta do core.

Medido no `examples/list_demo`, nos dois modos: deslizar fundo, pull-to-refresh,
e a lista volta com itens e volta a rolar.

## [0.96.0] — 2026-08-23

### Fixed

- **Handler com parâmetro default-bound recebia o evento no lugar do valor
  capturado** ([#134](https://github.com/mauriciobenjamin700/tempestweb/issues/134)),
  nos três modos. `def toggle(i: int = index)` é o idioma que a documentação do
  Python ensina para capturar variável de laço, e a convenção de chamada era
  decidida pela **espécie** do parâmetro — nunca por ele ter default, que é
  precisamente o que diz "o chamador não precisa fornecer isto". Medido no
  `examples/faq-accordion`: `open_index` virava um `ClickEvent` e o acordeão
  parava de responder de vez.

  Agora o handler só recebe o evento quando declara um parâmetro **sem** default
  (ou `*args`, que pode recebê-lo). A regra vive em
  `tempestweb.runtime.events.handler_wants_event` e serve os Modos A e B — que
  antes tinham **duas** cópias do predicado, ambas com o defeito. Em Modo C a
  pergunta é a mesma e sai de graça: `fn.length` conta os parâmetros antes do
  primeiro default.
- **O Modo C descartava o default de parâmetro.** `def toggle(i: int = index)`
  saía `(i) => …` — a captura sumia — então o closure respondia `undefined` mesmo
  depois de ser chamado nu. O default é emitido agora, o que também dá ao runtime
  a aridade que ele lê.

Os três modos passam a concordar: no `faq-accordion`, clicar num header abre
aquele item, clicar de novo fecha, e outro header troca — idêntico em Modo B e em
Modo C.

!!! note
    `tempest_core.handler_accepts_event` continua respondendo a pergunta mais
    frouxa (qualquer parâmetro posicional). Os dois deveriam convergir no core;
    até lá o tempestweb usa o seu.

## [0.95.0] — 2026-08-23

### Fixed

- **O Modo C tratava `dict` como lista**
  ([#137](https://github.com/mauriciobenjamin700/tempestweb/issues/137)), nas três
  operações que a issue mediu:
  - **truthiness** — `""`, `0`, `None` e `False` as duas linguagens concordam;
    container vazio **não**: `[]` e `{}` são falsy em Python e truthy em JS. Então
    `if s.errors:` entrava no ramo com estado recém-criado. Posição booleana
    (`if`, `elif`, `while`, `not`, o ternário) passa por `truthy$`; comparação,
    `not`, literal booleano e nome que o módulo só liga a booleano ficam sem
    embrulho, para o teste continuar legível;
  - **`len(d)`** emitia `d.length` e respondia `undefined` — o banner do
    `br-cadastro` dizia literalmente `undefined campo(s) com erro`. Agora conta
    chaves (e `size`, num `Set`/`Map`);
  - **`"k" in d`** emitia `d.includes("k")`, método de `Array` que um objeto não
    tem. Agora lê chave em mapeamento, membro em lista/string e `has` em
    `Set`/`Map`.

  `and`/`or` em posição de **valor** ficam como estão de propósito: devolvem um
  operando nas duas linguagens, então `||` já é o comportamento certo. A
  diferença só aparece com container vazio à esquerda, que nenhum exemplo do
  corpus escreve — está registrado nas docs em vez de embrulhado em silêncio.

Com isso o `examples/br-cadastro` funciona inteiro em Modo C: máscara, endereço,
validação e contagem de erros.

## [0.94.0] — 2026-08-23

Três widgets declarados que o renderizador desenhava como `div` anônimo. Vale nos
**três modos** — `client/dom.js` é o renderizador compartilhado —, e é a mesma
classe do `IconButton` (#109): o nó existe com a chave certa, então nenhum teste
via, e a caixa parecia certa numa captura.

### Fixed

- **`TextArea` renderiza um `<textarea>`**
  ([#130](https://github.com/mauriciobenjamin700/tempestweb/issues/130)), com
  `value`, `placeholder`, `rows` e `maxlength`. Era um `div` com cara de campo e
  nada para focar: `FORM_CONTROL_TAGS` e `payloadFor` já estavam prontos para o
  `<textarea>` que nunca era criado.
- **`MaskedInput` renderiza um `<input>` e aplica a máscara**
  ([#136](https://github.com/mauriciobenjamin700/tempestweb/issues/136)). A
  notação é a do core (`9` dígito, `A` letra, o resto literal); a formatação roda
  antes de o valor ser lido, para estado e tela concordarem, e o cursor é
  recolocado contando os caracteres **preenchíveis** que o precedem — senão
  digitar o sexto dígito de um CPF jogaria o cursor três casas atrás. Re-mascarar
  um valor já mascarado é no-op, senão cada ida e volta pelo estado comeria os
  literais.
- **`LazyGrid.columns` é aplicado**
  ([#132](https://github.com/mauriciobenjamin700/tempestweb/issues/132)):
  `display: grid` + `grid-template-columns: repeat(N, minmax(0, 1fr))`. A reserva
  de espaço da virtualização passou a contar **linhas** (`ceil(itens/colunas)`) e
  os spacers, que são pseudo-elementos, ganharam `grid-column: 1 / -1` — sem isso
  ocupariam uma célula e a barra de rolagem descreveria uma lista N vezes maior.
- **O `on_change` de um controle de formulário ia para `click` no Modo C.** A
  lista de "controle de verdade" era escrita à mão ao lado do gerador, então
  driftou assim que o renderizador aprendeu um controle novo — e o drift é mudo:
  o campo renderiza, aceita digitação e nunca avisa a app. Agora é derivada da
  tabela de tags do renderizador. Conserta `MaskedInput`, `TextArea` e também
  `PinInput`, que já estava assim.
- **`setattr(obj, nome, valor)` com nome computado** só era portado na forma
  `lambda s: setattr(s, "campo", v)` com nome constante; fora dela emitia uma
  chamada a um `setattr` inexistente. Medido no `examples/br-cadastro`, cujo
  bloco de endereço inteiro era inerte. `getattr` ganhou o mesmo tratamento.

### Auditoria

O `TAG_BY_TYPE` foi auditado contra os widgets de IR interativos do core, como a
#130 pedia. **Treze** têm o mesmo defeito latente; três saem aqui, e os dez
restantes ficam registrados: `Autocomplete`, `DatePicker`, `Dropdown`,
`FilePicker`, `RangeSlider`, `RouteDrawer`, `Slider`, `Switch`, `TabBar`,
`TabView`. Nenhum tem regra na folha base nem ramo em `events.js`.

## [0.93.0] — 2026-08-23

### Added

- **`Form.validate(values)` roda em Modo C** — o primeiro (e, por ora, único)
  **método** de widget portado. O cliente carrega o *builder* de cada widget e
  nenhum dos métodos Python da classe; `validate` cabe porque o insumo sobrevive:
  `validators` nunca atravessa fio em Modo C, então as funções vivas estão no nó
  quando a validação roda. Fixado por
  `tests/fixtures/transpile_form_samples.json` (9 cenários do `Form` real —
  válido, uma falha, todas as falhas, segundo validador falhando, valor ausente,
  campo sem validador, form vazio, validadores BR).

  O padrão geral que a [#128](https://github.com/mauriciobenjamin700/tempestweb/issues/128)
  pedia para decidir: **tabela de exceção** (`_WIDGET_METHODS`). Método fora dela
  continua recusado no build — a porta é uma entrada, não uma abertura.
- **Predicados de caixa `isupper`/`islower`**, com a semântica do Python: exigem
  ao menos um caractere com caixa, então `"1".isupper()` é `False`.

### Fixed

- **`form.validate` escapava da recusa quando o compilador não via a ligação.**
  A recusa dependia de um local que o módulo tivesse ligado a `Form(...)`, então
  um form montado em outro escopo passava batido e compilava para
  `form1.validate is not a function` — medido no `examples/signup-wizard`, que
  passava no build e lançava três vezes por clique. A rota nova não depende da
  ligação.
- **`dict(outro)` explodia num mapeamento.** Compilava para
  `Object.fromEntries`, que exige iterável de pares. `dict(pares)` também é
  legítimo e o compilador não sabe qual é qual, então a decisão passou a ser em
  runtime.
- **`d.pop(chave, default)`** caía no `pop` de array, que num objeto não existe.
- **Atribuição anotada não registrava ligação.** Só `x = re.compile(...)` era
  rastreado, nunca `x: re.Pattern[str] = re.compile(...)` — a forma que as regras
  de estilo deste repo pedem. O `.match` saía cru num `RegExp`, que não tem esse
  método, e morria dentro de um validador. Vale igual para `form: Form = Form(…)`.

Corpus do Modo C: **44 dos 57 exemplos** (era 42). Desbloqueados: `form` e
`login-form`; o `signup-wizard` já compilava e agora **funciona**.

## [0.92.0] — 2026-08-23

### Added

- **`f"{x:+.1f}"`** — o `+` que força o sinal no positivo, que é como um delta se
  lê. O valor é formatado **primeiro** e o prefixo decidido do resultado, senão
  um negativo sairia `+-3.0`; zero negativo mantém o sinal, que o `toFixed`
  sozinho perde. Compõe com `,`, `%` e `d`. Com `0Nd` é recusado, porque o Python
  conta o sinal dentro da largura e sobrepor daria um caractere a mais.
- **`{**old, k: v}`** — o idioma de "novo dict sem mutar", irmão do `[a, *rest]`
  que já passava. Vira spread de objeto, com a posição preservada porque nas duas
  linguagens a última chave ganha.
- **`if __name__ == "__main__":` é pulado**, não recusado. É guarda de script e
  nunca roda quando o arquivo é importado como módulo — que é exatamente como o
  Modo C o compila, então pular é a leitura fiel. Um `else` nele continua recusado,
  porque esse *roda* na importação.
- **Construtor de evento do core no Modo C.** Os 33 eventos (`ThemeChangeEvent`,
  `TextChangeEvent`, …) eram excluídos de `values.gen.js` sob a premissa de que
  evento só vem *do* cliente. Uma app constrói um quando simula evento do host —
  é o que o `examples/theme-switcher` faz — e a exclusão barrava a view inteira
  pelo tamanho de um literal de objeto cada.

### Fixed

- **`xs[:] = [...]` compilava para uma atribuição inválida.** Fatia *lê* como
  `.slice(...)`, então a atribuição saía `xs.slice(0) = [...]`, que **parseia** —
  e por isso o `node --check` do build passava — e lançava
  `Invalid left-hand side in assignment` no primeiro clique. Medido no
  `examples/router-drawer`: a navegação pelo drawer não fazia nada. Agora emite
  `splice`, a substituição no lugar que o Python faz; fatia parcial
  (`xs[1:3] = …`) é recusada, porque pode crescer ou encolher a lista.
- **Membro não portado de valor do core agora falha no build.** `_served.py`
  responde "o cliente exporta esse nome?" e não "esse nome tem esse método?" — o
  mesmo defeito com outra forma. `Theme.from_seed(...)` compilava, carregava e
  morria na montagem (`examples/theme-switcher`, página em branco). O manifesto
  novo `tempestweb/transpile/_members.py` é gerado introspectando o cliente no
  Node, e o compilador recusa com `arquivo:linha`. `Color.from_hex`, `Edge.all` e
  `Edge.symmetric` seguem passando: esses o cliente carrega.

Corpus do Modo C: **42 dos 57 exemplos** (era 40). Desbloqueados: `quiz-app` e
`router-drawer`. O `theme-switcher` continua fora, mas agora com erro de
compilação em vez de página em branco.

## [0.91.0] — 2026-08-23

### Changed

- **`tempest-core` 0.14.0 → 0.15.0**, que passa a *namespacear* a chave de todo
  filho de componente: a base é o `key` do componente (ou o `default_key` dele,
  quando não vem chave) e cada filho vira `<base>-<papel>`. Era exatamente o
  defeito reportado em
  [#135](https://github.com/mauriciobenjamin700/tempestweb/issues/135) — dois
  `SegmentedControl` na mesma tela disputavam `seg-0`, e como o evento roteia por
  chave o clique ia para o controle errado.
- **Os 42 componentes portados para o Modo C carregam a derivação.** Um port com
  chave literal é o mesmo defeito de volta, só que no cliente: medido em
  `examples/faq-accordion`, os sete headers agora saem `faq-0-header` …
  `faq-6-header`, e `resolve_handler("faq-3-header")` devolve o closure que
  captura `3` (antes devolvia sempre o do primeiro).
- **`StatCard` deixou de herdar a chave default do `MetricCard`.** Ele delega, e
  delegava sem chave própria, então um `StatCard` sem `key` respondia por
  `metric-card`.

### Fixed

- **A matriz de paridade não comparava chave nenhuma.** O comparador reduzia cada
  nó a `{type, props, children}`, então um builder com chave literal passava
  intacto — foi assim que o port entrou. Agora compara a chave de todo
  **descendente** (a do nó raiz continua fora, porque a fixture a anula de
  propósito).
- **A matriz não exercia `key=` em componente nenhum.** Sem chave, a derivação é
  invisível: `Accordion()` emite `accordion-header` derivando ou não. Cada um dos
  34 componentes que emitem chave de filho ganhou um par `__keyed`, construído do
  core com `key="k9"` — 151 → **185 casos**.

Corpus do Modo C: **40 dos 57 exemplos**, sem mudança.

## [0.90.0] — 2026-08-23

Três defeitos do tipo "compila e morre" (ou pior: compila e mente), todos
encontrados dirigindo em Chrome real os exemplos que os commits anteriores
destravaram. Nenhum aparecia na suíte: o guard de build roda `node --check`,
que faz *parse* sem executar.

### Fixed

- **Props de componente do facade saíam em `snake_case`, e o handler sumia.**
  A renomeação para `camelCase` era decidida resolvendo o nome no
  `tempest_core`; um componente que só existe em `tempestweb.components`
  (`LoginForm`, `SignupForm`, `TextField`, `EmailField`, `PasswordField`) não
  resolvia lá, então `on_submit` chegava como `on_submit` no builder, que
  desestrutura `onSubmit`, e **todo handler era descartado em silêncio**.
  Medido no `login_demo`: o formulário montava, digitar funcionava, e o submit
  não fazia absolutamente nada. Agora o nome é procurado no core e depois no
  facade — e, de brinde, a checagem de kwarg do core volta a valer para esses
  componentes (`LoginForm(subtitle="x")` falha com `arquivo:linha`).
- **`Color.from_hex` não existia no Modo C.** No core `Color` é modelo com o
  classmethod — o jeito de escrever cor literal, 65 chamadas nos exemplos —
  e o cliente exportava só a fábrica. `Color.from_hex("#ef4444")` compilava,
  carregava e matava a página na montagem. Portado com o parse do core
  (`#RGB`/`#RRGGBB`/`#RRGGBBAA`, `#` opcional, alfa sobre 255) e fixado por
  `tests/fixtures/transpile_color_samples.json`.
- **`field(default_factory=OutraDataclass)` chamava a classe sem `new`.**
  Dataclass compila para classe JS, e classe sem `new` é `TypeError` duro: o
  default aninhado saía `(Address)()` e o app morria no primeiro
  `makeState()`. Medido no `br-cadastro`.

Cada um tem teste que falha sem a correção.

Quatro achados de paridade ficaram **fora** deste ciclo por serem do core ou do
renderizador compartilhado — medidos em Modo B e Modo C antes de atribuir:
[#134](https://github.com/mauriciobenjamin700/tempestweb/issues/134) (handler
com parâmetro default-bound recebe o evento no lugar do valor capturado),
[#135](https://github.com/mauriciobenjamin700/tempestweb/issues/135) (a chave
literal `accordion-header` colide entre instâncias),
[#136](https://github.com/mauriciobenjamin700/tempestweb/issues/136)
(`MaskedInput` renderiza um `div` vazio nos três modos) e
[#137](https://github.com/mauriciobenjamin700/tempestweb/issues/137) (o Modo C
trata `dict` como lista em `if`, `len` e `in`).

## [0.89.0] — 2026-08-23

### Added

- **Os componentes do próprio tempestweb rodam em Modo C**: `TextField`,
  `EmailField`, `PasswordField`, os formulários prontos `LoginForm` e
  `SignupForm`, e os apelidos `PhoneField`/`CPFField`/`CNPJField`/`AddressField`
  sobre os campos do core. Eles derivam a chave de cada filho da chave do
  componente — que é como o roteador de evento acha o handler que disparou — e o
  Modo C carrega essa derivação, senão dois campos na mesma tela disputariam o
  nome do `Input` que emite o evento.
- **11 casos novos na matriz de paridade** (`transpile_component_samples.json`,
  agora 151), incluindo a assimetria de chave do `LoginForm` (os filhos saem de
  `key or "login"`, a coluna de `key or "login-form"`) e o fato de o `EmailField`
  do tempestweb **não** passar `error` para o `Input` interno — a mensagem
  aparece na linha própria e a caixa mantém o contorno de repouso, ao contrário
  do `EmailInput` do core.

Corpus do Modo C: **40 dos 57 exemplos** (era 39). Desbloqueado: `login_demo`.

## [0.88.0] — 2026-08-23

### Added

- **Os seis campos brasileiros do core rodam em Modo C**: `EmailInput`,
  `PasswordInput`, `PhoneInput`, `CPFInput`, `CNPJInput` e `AddressInput`. Cada
  um é o rótulo mudo acima, o `Input`/`MaskedInput` com a máscara e o teclado
  certos, e a linha de erro abaixo — presentes na árvore só quando têm conteúdo,
  para o reconciliador inserir e remover em vez de renderizar em branco. O
  `on_change` recebe a **string** nova (o `AddressInput` recebe `(campo, valor)`),
  como no core: o app nunca toca no objeto de evento.
- **14 casos novos na matriz de paridade** (`transpile_component_samples.json`,
  agora 140), cobrindo rótulo ausente, erro presente, os três tratamentos de
  campo, tamanho, esquema e o bloco de endereço preenchido.

### Fixed

- **Campo inválido não ficava vermelho no Modo C.** Um `Input` com `error`
  preenchido está inválido, e o core repinta a borda e o texto no papel `error`
  **ao construir** — regra que mora no estilo construído, não na folha, então o
  builder gerado (passthrough) a perdia em silêncio. O campo compilava, montava
  e mentia: a mensagem aparecia embaixo e o campo continuava com cara de válido.
  Agora `Input` resolve por `resolveFieldStyle`, que aplica a regra do core:
  borda de 1px no papel `error`, `SideBorder` só embaixo quando o `field_variant`
  é `flushed`, e o `style` do chamador ainda ganha por último. Fixado por
  `tests/fixtures/transpile_field_samples.json` (10 cenários construídos do core
  real) — o teste falha sem a correção.

Corpus do Modo C: **39 dos 57 exemplos** (era 38). Desbloqueado: `br-cadastro`.

## [0.87.0] — 2026-08-23

### Added

- **`Accordion` e `Tabs` rodam em Modo C.** Estavam na lista de "componentes
  dirigidos por dados", junto de `DataTable` e dos gráficos, e a classificação
  estava errada: a árvore do `Accordion` é header + corpo opcional, e a do
  `Tabs` é um botão por rótulo — composição fixa, do mesmo tipo que
  `SegmentedControl` e `RadioGroup`, que já estavam portados. O que é
  genuinamente dirigido por dado é a *forma* da árvore mudar com o registro (uma
  linha de células por linha de dado, uma barra por ponto), e isso continua fora.
- **Nove casos novos na matriz de paridade** (`transpile_component_samples.json`,
  agora 126): `Accordion` fechado, aberto, `outlined`/`primary` e
  `elevated`/`error`; `Tabs` default, ativo com `size="lg"`, `secondary`/`sm`,
  lista vazia e `active` fora de alcance.

### Changed

- **O teste que fixa o fora-de-escopo passou a dizer o critério certo.**
  `test_a_data_driven_component_is_still_out_of_scope` agora guarda `DataTable`,
  `Table`, os gráficos e `DetectionOverlay` — a *forma* da árvore depender do
  dado — e um teste irmão exige que `Accordion` e `Tabs` estejam servidos.

Corpus do Modo C: **38 dos 57 exemplos** (era 35). Desbloqueados:
`core-profile-cards`, `core-tabbed-settings`, `faq-accordion`.

## [0.86.0] — 2026-08-23

### Added

- **Listas virtualizadas rodam em Modo C**: `LazyColumn`, `LazyRow` e `LazyGrid`
  eram os três widgets marcados como inportáveis, porque um builder gerado é
  passthrough e eles são o único caso em que os filhos não existem até alguém
  **rodar** — o core resolve a janela visível e chama `item_builder(índice)`
  sobre ela, re-chaveando cada item pelo índice absoluto. O corpo agora é gerado
  junto: `lazyChildren` espelha `_resolve_window` + `_materialize_items`,
  incluindo o clamp nas duas pontas.
- **A janela desliza no Modo C**, como o servidor faz no Modo B: o evento de
  `scroll` chama `App.slide_window` e a janela rastreada é publicada para os
  builders durante o build (o equivalente do `_inject_windows` do core). Sem
  isso a lista materializava só a primeira janela para sempre — 200 itens com 30
  visíveis e nenhum jeito de chegar no resto.
- **Fidelidade fixada por matriz do core real**
  (`tests/fixtures/transpile_lazy_samples.json`, 16 cenários): janela default,
  explícita, `window_size` menor que a contagem, clamp nas duas pontas, janela
  invertida, fora de alcance, lista vazia, `refreshing`, `columns` e estilo.

### Fixed

- **`Edge` do Modo C não era chamável.** No core `Edge` é um modelo de quatro
  campos com default `0.0`, então `Edge(top=20.0, left=20.0)` é escrita normal —
  e o Modo C exportava só os helpers `all`/`symmetric`. A chamada compilava e a
  página morria no mount com `Edge is not a function`: medido no
  `examples/image-gallery`, que renderizava **nada**.
- **Janela deslizada sobrevive ao rebuild.** O `view` re-roda a cada mudança de
  estado e não declara janela nenhuma, então sem o mapa rastreado a lista voltava
  para `[0, window_size)` no próximo `set_state` — a lista pulava para o topo
  quando qualquer coisa não relacionada mudava.

### Notas

- **Medido no corpus: 35 dos 57 exemplos transpilam** (eram 31). Entraram
  `fetch`, `list_demo`, `todo` e `image-gallery`.
- Verificado em Chrome real, SW e caches limpos: `list_demo` desliga a janela de
  `0-24` para `6-35`, `26-55` e `45-74` com a roda do mouse, mantendo 30 nós no
  DOM para 200 itens; `end_reached` carrega 25 → 50 → 75; pull-to-refresh arma
  `data-tw-pull-armed` e recarrega. `image-gallery` monta os 12 thumbs da janela
  inicial. Console limpo, sem overflow horizontal a 390px e 1280px.
- **Dois achados de paridade, medidos nos dois modos e fora do escopo deste
  bloco:** `LazyGrid.columns` é ignorado pelo renderizador compartilhado (Modos
  B e C rendem `display: block`, 1 item por linha) — #132; e uma janela deslizada
  contra uma lista que **encurta** clampa para vazio no core
  (`_resolve_window` prende o `start` na contagem em vez da última página),
  deixando a lista sem item e sem scroll para se corrigir — #133.

## [0.85.0] — 2026-08-23

### Added

- **As três formas de import de capacidade nativa chegam na mesma fachada**
  (#117): `from tempestweb import native`, `from tempestweb.native import
  storage` e `from tempestweb.native.geolocation import get_position`. Só a
  primeira compilava, e a recusa das outras duas listava `tempestweb.native`
  entre os módulos que ela permitia — mensagem que se contradizia e ensinava
  errado: quem lia concluía que a capacidade não existia em Modo C, quando a
  fachada em `./native.js` a serve.
- **Manifesto da fachada gerado das duas fontes honestas**
  (`tempestweb/transpile/_native.py`, via `python -m
  tests.conformance._transpile_native`): a **forma** vem do
  `client/transpile/native.js` — é o que o browser carrega — e a **resolução de
  nome solto** vem do pacote Python, o único que sabe que `get_position` é
  re-export de `geolocation`.
- **Enum nativo de string vira tabela congelada.** A fachada devolve o valor
  cru (`"granted"`), então `perm is NotificationPermission.GRANTED` é comparação
  de string assim que os dois lados são emitidos — os mesmos `Object.freeze` que
  os enums do core já usam.
- **Recusa que diz qual modo tem a capacidade:** `camera` não tem fachada em
  processo (`camera.capture` é `mode_c=False` no contrato), e importá-la agora é
  erro de build apontando Modo A ou B. Membro desconhecido é recusado **pelo
  nome** (`geolocation.triangulate`, com o que o grupo serve), e `import
  tempestweb.native` diz qual forma escrever no lugar — antes listava os módulos
  de stdlib servidos, que não tinham nada a ver.

### Fixed

- **Campo de dataclass chamado `get` era lido como acesso a dict.**
  `examples/file-storage` injeta `storage.get` no estado e abre uma nota com
  `app.state.get(key)`; isso compilava para `app.state[key]` — JS válido que
  devolve `undefined`, então a página carregava e nenhuma nota abria. Nome que o
  módulo declara como campo é atributo, e ganha do mapeamento.
- **`except X as Y` comparava com o apelido.** O Modo C despacha `except` pelo
  **nome de classe** em string, e um import renomeado gerava `_err.name ===
  "Failure"` enquanto o erro carrega `"NativeError"` — o handler era código
  morto e o erro escapava. Agora compara o nome de origem.
- **A fachada passa a ser reconhecida pelo que o módulo importou**, não pelo
  nome solto `native`: `native.storage.get(k)` só escapa do mapeamento de
  `dict.get` quando `native` foi de fato importado.
- **Handler do Modo C recebia o evento do fio, e o app lê o evento plano.**
  Nos Modos A e B o handler recebe um objeto tipado com campo raso — `e.value`
  num `TextChangeEvent` —, e o Modo C entregava `{type, key, payload}`: todo
  input de texto gravava `undefined` no estado. Medido no browser: digitar no
  `file-storage` não mudava nada e o primeiro `title_draft.strip()` derrubava o
  handler. O campo do payload agora vem raso, com `payload` ainda alcançável.

### Notas

- **Medido no corpus: 31 dos 57 exemplos transpilam** (eram 26). Entraram
  `geo_demo`, `file-storage`, `weather-native`, `clipboard-share` e
  `pwa-webpush`; `photo-capture` fica recusado — `camera` não é capacidade de
  Modo C, e dizer isso é a resposta certa.
- Verificado em Chrome real, service worker e caches limpos antes de medir:
  `file-storage` salva a nota no IndexedDB (`storage.put`), lista a chave,
  abre o conteúdo (`app.state.get`) e apaga; `geo_demo` vai de `idle` a
  `located` com `-8.048, -34.877` com a permissão concedida, e a `error:
  NativeError: permission_denied` com ela negada. Console limpo nos dois, sem
  overflow horizontal a 390px e 1280px.
- **Fora do escopo, achado na medição:** o `TextArea` renderiza um `<div>`
  vazio, sem campo editável — o corpo da nota do `file-storage` não é digitável.
  Vale nos três modos, porque `client/dom.js` é compartilhado (#130).

## [0.84.0] — 2026-08-23

### Added

- **`import x` funciona, para os módulos que o browser tem** (#110): `re`, `json`,
  `math`, `base64` e `asyncio`, nas **duas** formas de import (`import re`,
  `from math import ceil`). Antes a recusa era pela *forma*, então nem um módulo
  cujo conteúdo o Modo C sabia traduzir passava.
- **Semântica de `re` do Python, que o JS não dá de graça:** `Pattern.match`
  ancora no início (`test`/`exec` não ancoram), `fullmatch` ancora nas duas
  pontas, e `re.sub` troca **todas** as ocorrências. Os helpers vivem em
  `client/transpile/runtime.js` e são importados com alias `$` — ilegal em
  identificador Python, logo um `sleep` do app não colide com o helper. Conferido
  membro a membro contra o Python: `match`/`search`/`fullmatch`/`sub`/`findall`
  dão o mesmo resultado nos dois lados.
- **`enum` do app** (#112): `class Phase(StrEnum)` vira `Object.freeze({…})`, como
  os enums do core já viajam em `values.gen.js`. Os 6 exemplos que usam `enum`
  usam `StrEnum` com membro string.
- **`math`** (#112) com os membros de equivalente exato (`Math.*`,
  `Number.isNaN`/`isFinite`) e as constantes (`pi`, `e`, `tau`, `inf`, `nan`).
- **`asyncio.sleep`**, convertendo segundos para milissegundos — medido no
  browser: `sleep(0.4)` espera ~400 ms, não 0,4 ms.
- **Generator expression** (`any(x for x in xs)`) toma o caminho da comprehension:
  JS não tem gerador lazy, então o array é materializado — diferença de custo, não
  de resultado. Junto vieram `any`/`all` (que não existiam e emitiam chamada a
  nome inexistente), `dict.get` com default, e os predicados de `str`
  (`c.isdigit()` → teste de padrão).
- **Recusa que ensina** (#112): módulo fora da lista diz o que fazer no lugar —
  `datetime` → formate no estado e passe a string; `functools` → `partial` é
  lambda e `reduce` é `.reduce`. Vale nas duas formas de import. Membro
  desconhecido de módulo servido é recusado **pelo nome** (`re.escape`).

### Fixed

- **Comprehension sobre string emitia `.map` em string.** Python itera qualquer
  iterável (`for c in str(value)` anda pelos caracteres) e string em JS não tem
  `.map`. O iterável passa a ser espalhado (`[...expr]`).
- **`dict.get` não existia.** Dict é objeto simples em JS, então
  `state.errors.get("email", "")` carregava a página e morria na primeira
  renderização (medido em `signup-wizard`). Agora é leitura indexada com `??` — e
  não `||`, para valor falsy guardado (`0`, `""`) não ser trocado pelo default. O
  `.get` da fachada nativa (`native.storage.get`) é preservado.
- **Método de widget do core compilava e morria.** `form.validate(values)`
  transpilava limpo e levantava `form1.validate is not a function` na primeira
  renderização, porque o cliente porta o *builder* de cada widget e não os
  métodos Python da classe. Agora é erro de compilação com `arquivo:linha`:
  compilar algo que morre é pior que recusar, que é justamente o que a checagem
  de nome servido existe para evitar.

### Notas

- **Medido no corpus: 26 dos 57 exemplos transpilam** (eram 25 antes deste PR e
  14 antes da 0.83.0). `async_demo` entrou; `signup-wizard` saiu do estado
  "compila e quebra" para "recusado com motivo".
- Verificado em Chrome real, service worker e caches limpos antes de medir:
  `async_demo` vai de `idle` → `loading…` → `done` com o sleep de 400 ms;
  `rating-review` troca a dica de `Tap a star to rate` para `Very good` ao clicar
  a quarta estrela, que é o `dict.get` com default rodando. Console limpo nos dois.

## [0.83.1] — 2026-08-23

### Fixed

- **`IconButton` passa a ser desenhado — nos dois renderizadores.** Nem
  `TAG_BY_TYPE` (`client/dom.js`) nem `_TAG_BY_TYPE`
  (`tempestweb/html/renderer.py`) o mapeavam, e `renderIcon` só rodava para um nó
  `Icon`, então o widget tinha três sintomas com uma raiz só: caía no fallback
  `div` (não focável, não anunciado, sem o state layer da folha base), **nunca
  desenhava o glifo** — o `Burger` escrevia a palavra "menu" onde deveria ir `☰`,
  e o botão de limpar do `SearchBar` escrevia "clear" em vez de `×` — e no HTML
  estático saía um `<div>` de 48×48 **vazio**. Agora é `<button type="button">`
  com o glifo num `<svg>` do renderizador (legal porque `IconButton` é folha da
  IR) e o `label` em `aria-label`; `semantics.label` explícito continua ganhando.
  A folha base passou a cobrir `[data-tw-type="IconButton"]` nas mesmas regras do
  `Button`, então o reset de UA e o state layer de hover/foco/press valem para o
  controle só-de-ícone. Anterior a esta versão e válido nos três modos; ficou
  visível quando o `Burger` chegou ao Modo C na 0.82.0.

  Medido em Chrome real, antes e depois: a árvore de acessibilidade dizia
  `generic "menu"` e agora diz `button "menu"`; `Tab` alcança o `Burger` em um
  salto e `Enter` abre o `Drawer` (0 → 1 nó); o glifo é o path Lucide do menu, e o
  do `search-clear` é o do `×`. Modo B mede idêntico ao Modo C em tag,
  `aria-label`, glifo, caixa de 48×48 e comportamento do teclado.

### Notas

- **O HTML estático continua sem glifo, agora por limitação declarada:** o
  renderizador SSR não carrega dado de path de ícone nenhum (um `Icon` também sai
  como `<span>` vazio lá), então um `IconButton` estático é um botão **nomeado e
  focável** cujo glifo aparece quando o cliente hidrata. Ícone no SSR é lacuna
  própria, anterior a esta mudança.

## [0.83.0] — 2026-08-23

### Added

- **O subset do Modo C aceita as formas que um app real escreve.** Medido no
  corpus: **25 dos 57 exemplos transpilam** (eram 14). Sete mudanças, nenhuma
  delas uma capacidade nova — todas eram recusa por forma:
    - **import só de anotação** (#111): `collections.abc` e `typing` são fontes
      type-only, então o nome custa zero JS. Alias de tipo em nível de módulo
      (`Fetcher = Callable[[], Awaitable[list[str]]]`) é reconhecido e descartado;
      usar nome type-only como **valor** virou erro com `arquivo:linha`, em vez de
      identificador nu que só quebra na linha que roda.
    - **`from tempestweb.components import …`** (#113): o import que o tutorial
      ensina, e que era recusado como módulo — embora **63 dos 77 nomes que ele
      exporta sejam o objeto do core** (identidade medida com `is`). Agora roteia
      como um import de `tempest_core`; nome que o cliente não tem é recusado
      **pelo nome** (#114 acompanha o port da camada própria).
    - **`*` em literal** (#116): `[a, *rest]`, o idioma de "nova lista sem mutar".
    - **alvo destructurado** (#116): `for i, (q, a) in enumerate(pairs)`, no `for`
      e no assignment, aninhado quanto o Python aninhar.
    - **`is` / `is not`** (#116): contra `None` emite `== null` / `!= null` — a
      única tradução correta aqui, porque campo que o objeto JS nunca atribuiu é
      `undefined` e o `is None` do Python responde verdadeiro para ele. Contra
      qualquer outro operando é identidade (`===`/`!==`).
    - **`f"{n:0Nd}"`** (#116): zero-pad de relógio e placar. `padStart` sozinho
      está errado para negativo (Python dá `-0042`, `padStart` dá `00-42`): o
      emitido mantém o sinal fora do preenchimento e avalia o argumento uma vez.
    - **dataclass como se escreve** (#115): campo sem default (fica `undefined`
      até o `make_state` preencher), `@dataclass(frozen=True)` e as demais opções
      que não mudam o JS emitido, e `field(default_factory=…)` com callable
      próprio. Opção fora da lista de no-ops é recusada citando a chave.
- **Conversão de container:** `list(xs)`/`tuple(xs)` → `[...xs]`, `set(xs)` →
  `new Set(xs)`, `dict(pairs)` → `Object.fromEntries(pairs)`, mais as formas sem
  argumento.

### Fixed

- **Fábrica de default guardava a função em vez do valor.**
  `field(default_factory=lambda: list(NAV_ITEMS))` emitia
  `() => list(NAV_ITEMS)()`, que pela precedência guardava a arrow. Achado
  dirigindo o `core-app-shell` em Chrome real: compilava, gate verde, e a página
  ficava **em branco** com `state.items.map is not a function`. Junto veio a
  segunda causa: `list(NAV_ITEMS)` chamava um `list` que não existe em JS.
  `node --check` parseia as duas e o golden compara texto, então nada na suíte
  via o app morto na primeira renderização.

### Notas

- A mensagem de allowlist de import mudou, então `docs/troubleshooting.md` e o
  `.en` foram atualizados — o guard `test_docs_troubleshooting.py` pegou a
  defasagem. Para a página continuar pesquisável, a mensagem ficou **literal** em
  vez de interpolar o nome do módulo: o guard não resolve f-string, e mensagem que
  ele não acha é mensagem que o usuário também não acha.
- Verificado em Chrome real, service worker e caches limpos antes de medir:
  `stopwatch` (Modo C) mostra `00:00.1` → `00:00.9` → `00:01.0` → `00:01.2` e, com
  100 ticks, `00:10.0`; `core-app-shell` renderiza 28 nós com `AppBar`, `Sidebar`
  de 260px e três `ListTile`, e clicar `nav-1` move a pílula ativa. **Modo B mede
  idêntico** nos dois. Console limpo.
## [0.82.0] — 2026-08-22

### Added

- **25 componentes estruturais do core rodam em Modo C** — de 10 exports para 35.
  Superfície e estrutura: `Surface`, `StyledContainer`, `Grid`, `Sidebar`,
  `Drawer`. Barras e navegação: `Header`, `Footer`, `NavBar`, `Breadcrumb`,
  `Burger`. Conteúdo: `ListTile`, `Avatar`, `Tag`, `Rating`, `Stepper`,
  `SearchBar`. Feedback: `Banner`, `Alert`, `Badge`, `EmptyState`, `Stat`,
  `ProgressStepper`. Composição: `MetricCard`, `StatCard`, `ConfidenceBadge`, mais
  a função pura `confidence_scheme` (é como a app escolhe o esquema do badge).
  Mesmo caminho do 0.81.0: composição reescrita em
  `client/transpile/components.js` a partir do `render()` do core, com as mesmas
  chaves, e estilo vindo de tabela gerada.
- **Quatro tabelas de estilo novas** em `component-styles.gen.js`: `ALERT_STYLES`
  (variante × esquema), `FIELD_STYLES` (variante × tamanho × esquema, no estado de
  repouso), `TYPOGRAPHY` (reduzida ao par `font_size`/`font_weight` que o
  componente lê) e `AVATAR_COLORS` (par tonal `container`/`on_container`,
  resolvido pelo mapa de papéis do próprio core). 164 KB → 237 KB.
- **A matriz de paridade foi de 28 para 117 casos**
  (`tests/fixtures/transpile_component_samples.json`), construídos do core real:
  por componente, o eixo que muda o estilo resolvido ou a composição — variante,
  esquema, tamanho, elevação, passo de token, tom legado, esquema desconhecido e a
  presença de cada slot. O teste JS agora exige que **todo** caso da fixture tenha
  builder correspondente, então componente novo não entra sem prova.
- **Oito widgets voltaram para o Modo C:** `IconButton`, `AspectRatio`, `Hero`,
  `Animated`, `Shimmer`, `Navigator`, `RouteDrawer` e `TabView`. Eles não estavam
  fora por decisão: `_CANDIDATE_ARGS` não tinha candidato para `child`, `drawer`,
  `icon`, `ratio` e `hero_tag`, então a construção nua levantava, o spec voltava
  `None` e o widget era descartado **em silêncio** — enquanto o renderizador
  compartilhado já os desenhava nos Modos A e B.
- **`examples/mode-c-components`**, um app só que exercita o lote inteiro (é o que
  foi dirigido no Chrome para validar).

### Fixed

- **`widgets.js` re-exportava os componentes por lista escrita à mão**, então um
  componente presente em `components.js` mas ausente da lista era um nome que o
  compilador aceitava (o manifesto servido é gerado por módulo) e o browser
  depois recusava resolver: página em branco a partir de um build verde. Agora é
  `export * from "./components.js"`, com guard em `tests/client/transpile.test.js`
  e em `tests/transpile/test_widgets.py` fixando que as duas superfícies
  concordam.

### Notas

- **Os três scrollers lazy continuam fora do Modo C, agora por decisão declarada**
  (`UNPORTABLE_WIDGETS`): o builder gerado é passthrough, e `LazyColumn` chama
  `item_builder` no build para materializar a janela — um passthrough emitiria
  viewport vazio. Precisam de builder à mão.
- **Colisão de chave de filho vale para mais componentes do que a doc dizia.**
  Medido numa tela com duas instâncias de cada: `Rating` (`star-N`), `NavBar`
  (`nav-N`), `Breadcrumb` (`crumb-N`/`sep-N`), `Stepper` (`step-up`/`step-down`) e
  `SearchBar` (`search-input`/`search-clear`) duplicam chave, como
  `SegmentedControl`/`RadioGroup` já faziam — e passar `key=` diferente no
  componente não resolve, porque a chave do filho não herda a do pai. Defeito do
  `tempest-core` ([tempest-core#20]), reproduzido fielmente aqui; documentado nos
  dois idiomas.
- **`IconButton` renderiza como `div`, não como `button`.** `TAG_BY_TYPE`
  (`client/dom.js`) e `_TAG_BY_TYPE` (`tempestweb/html/renderer.py`) não o mapeiam,
  então ele clica com o mouse mas não é focável nem anunciado como botão — vale
  nos três modos e é anterior a esta versão (só ficou visível agora que o `Burger`
  existe em Modo C). Muda o tag de um widget existente nos três renderizadores,
  então é decisão de contrato de renderização, não refactor: fica registrado aqui
  e não foi alterado.

[tempest-core#20]: https://github.com/mauriciobenjamin700/tempest-core/issues/20

## [0.81.0] — 2026-08-22

### Added

- **Os componentes estruturais do core rodam em Modo C:** `Card`, `AppBar`,
  `Scaffold`, `Divider`, `Chip`, `SegmentedControl` e `RadioGroup` (os aliases
  `HStack`/`VStack` já rodavam). A composição de cada um foi reescrita em
  `client/transpile/components.js` e o *resultado* dos resolvedores de estilo do
  core viaja em tabela gerada (`client/transpile/component-styles.gen.js`) — os
  resolvedores são puros, então a saída deles pode ser tabelada, o mesmo truque
  que `widget-styles.gen.js` usa pelos widgets. A tabela é esparsa (só o campo que
  o resolvedor setou; o `Style()` do JS preenche o resto), o que a mantém em
  ~160 KB em vez de 412 KB.
- **Fixture de paridade com matriz.** `transpile_component_samples.json` passou de
  5 para 28 casos, construídos do core **real** e cobrindo, por componente, os
  eixos que mudam o estilo resolvido: variante, esquema de cor, tamanho,
  elevação, os passos de token e a presença de cada slot opcional. Um caso por
  componente fixaria o caminho felizardo e deixaria todo o resto driftar em
  silêncio.
- `Edge.symmetric` no cliente do Modo C (o `Edge` só tinha `all`).

### Fixed

- **Os 5 exemplos que o Modo C recusava por falta de nome voltaram a compilar** —
  `a11y_demo`, `i18n-greeting`, `onboarding-carousel`, `search-autocomplete` e
  `settings-panel`. Medido: 13 exemplos transpilam, **0 com import morto**.

### Notas

- **Defeito do `tempest-core` encontrado ao validar, não corrigido aqui:**
  `SegmentedControl.render` nomeia os filhos com chave fixa (`seg-0`, `seg-1`, …)
  sem prefixo da chave do componente, e `RadioGroup` faz o mesmo (`radio-N`). Como
  o evento é roteado por chave, duas instâncias na mesma tela colidem — o Python
  resolve para a **primeira** ocorrência (`_find_node_by_key` é depth-first e para
  no primeiro match) e o Modo C para a **última**. Medido no `settings-panel`:
  clicar "Light" no controle de tema muda a *qualidade* para "Medium". Vale nos
  três modos; o conserto é no core (prefixar a chave do componente) e aí a fixture
  regenera. Documentado em `docs/tutorial/components.md`.
- Continua fora do Modo C o que é **dirigido por dados** (`DataTable`, `Tabs`,
  `Accordion`, `BarChart`/`LineChart`, pickers de formulário): a árvore depende
  dos dados recebidos, então não há composição fixa para portar.

## [0.80.0] — 2026-08-22

### Fixed

- **Modo C deixou de emitir import que o browser não resolve.** O transpiler
  roteava todo nome do `tempest_core` para um import no JS gerado, sem verificar
  se o alvo existe. Medido no corpus: **5 dos 13 exemplos que transpilavam
  produziam um módulo que não carrega** — `Semantics`, `TextAlign`, `FontWeight`,
  `AlignItems`, `JustifyContent`, `ACCENT`, `ON_SURFACE`, `Card`, `Divider`,
  `Chip`, `AppBar`, `Scaffold`, `SegmentedControl`, `RadioGroup`. Nenhum guard
  via: `node --check` parseia sem resolver import, e os goldens comparam texto.
  Resultado era página em branco com erro de import no console e build verde.
- **O `keyboard` do `Input` chegou ao DOM.** O widget declarava
  `KeyboardType.EMAIL` — é o que o `EmailField` constrói — e o renderizador
  descartava: saía um campo de texto comum, então o celular abria o teclado
  errado, o browser não oferecia o endereço salvo e o DevTools reclamava de
  `autocomplete` ausente. Agora `EMAIL`/`PHONE`/`URL` viram `type` + hint de
  autofill, `NUMBER` vira `inputmode="numeric"` (não `type="number"`, que briga
  com campo controlado) e `PASSWORD` vira `type="password"`. `secure` continua
  ganhando o tipo, `secure: false` explícito continua desmascarando, e
  `autocomplete` que a app passou por `attrs` vence o derivado — só a app sabe se
  o campo é login ou cadastro.
- **Controle de formulário renderizado ganhou `name`.** `<input>`, `<textarea>` e
  `<select>` saíam sem `name` nem `id` — beco sem saída de acessibilidade e de
  autofill, e um *issue* do DevTools em toda página com campo. O renderizador
  agora deriva o `name` da `key` do widget (inclusive no `<input>` aninhado no
  `<label>` do `Checkbox`), sem passar nada novo no fio.

### Added

- **`client/transpile/values.gen.js`** — gerado do core: os 32 enums (objeto
  congelado nome → valor de fio), os objetos de valor não-widget (`Semantics`,
  `Border`, `Shadow`, `Gradient`, `GradientStop`, `Corners`, `SideBorder`,
  `MenuItem`, `TableRow`/`TableCell`, `ChartSeries`, …) como fragmentos de fio, e
  os tokens de design (`ACCENT`, `ON_SURFACE`, `HOVER_OPACITY`,
  `MIN_TOUCH_TARGET`, …). Evento e tipo interno da IR ficam fora: o runtime JS os
  constrói, então builder ali seria byte morto em todo artefato. Regenerar:
  `python -m tests.conformance._transpile_values`.
- **`tempestweb/transpile/_served.py`** — manifesto gerado do próprio JS com os
  186 nomes que o cliente do Modo C exporta. O compilador recusa qualquer outro
  com `arquivo:linha` (`` `Card` is not available in Mode C ``) em vez de emitir
  o import morto. Importar tipo só para anotação continua livre — anotação é
  descartada, o nome nunca é referenciado. Regenerar:
  `python -m tests.conformance._transpile_served`.
- **Conformance**: goldens de `values.gen.js` e de `_served.py`, mais um teste de
  que `values.gen.js` está em `_TRANSPILE_ASSETS` (módulo gerado que ninguém
  copia não existe no artefato).

### Notas

- Os 4 exemplos que dependem de componente (`i18n-greeting`,
  `onboarding-carousel`, `search-autocomplete`, `settings-panel`) **passaram a ser
  recusados** no Modo C em vez de gerar página em branco. Continuam sendo
  exemplos de Modo A/B. Portar `Card`/`Divider`/`Chip`/`AppBar`/`Scaffold`/
  `SegmentedControl`/`RadioGroup` para o Modo C é feature nova, não corrigida
  aqui.

## [0.79.0] — 2026-08-22

### Changed

- **O Modo C passou a validar kwarg de widget no build, e o builder passou a
  aceitar o slot de filho do core.** As duas metades do mesmo defeito: o Modo C
  não tem Python em runtime, então o builder gerado desestrutura o objeto que
  recebe e ignora toda chave que não nomeia. Enquanto todo builder aceitava
  apenas `children`, `Container(child=...)` — a forma que o core exige —
  **perdia a subárvore em silêncio**, e `Container(children=[...])` — que o core
  recusa desde 0.14.0 — funcionava. `Form` era o caso extremo: seu slot é
  `fields`, nenhum builder o declarava, então todo campo de formulário
  transpilado ia para o chão. Agora cada builder declara o nome do próprio core
  (`child`, `children`, `fields`, e `child` + `drawer` no `RouteDrawer`, nessa
  ordem) e dobra os slots no array `children` da IR, enquanto o compilador
  confere cada chamada de modelo do core contra os campos reais e falha com
  `arquivo:linha`.
- **Prop de widget passou a ser camelizada por regra, não por tabela.** O
  transpiler mantinha uma lista de 9 renomeações à mão (`on_click`, `on_change`,
  `max_length`, …) e emitia todo o resto em snake_case dentro de um objeto cujo
  builder desestrutura camelCase — então a prop simplesmente não existia em
  runtime. Eram **38 campos do core em 64 widgets**: `on_drop`, `on_drag`,
  `on_tap`, `on_swipe`, `on_long_press`, `on_submit`, `on_validate`,
  `on_reorder`, `on_page_change`, `drag_data`, `min_value`/`max_value` do
  `Slider`, `focus_order` de todo widget, e mais. `Style`/`Color` continuam com a
  chave snake_case do fio, que é o formato que eles próprios são.
- **`RetryOptions` recusa kwarg que não declara** (`extra="forbid"`). Era
  `ConfigDict(frozen=True)`, logo `extra="ignore"`: `RetryOptions(backoff=0.5)`
  deixava a política nos defaults enquanto o código lia como se estivesse
  ajustada — foi o que deixou a doc mentir por releases. A regra que fica: modelo
  de **opção escrita pelo desenvolvedor** recusa nome desconhecido; modelo de
  **payload lido do browser** continua ignorando extras, senão uma chave nova de
  cliente novo quebra um Python antigo.

### Migração

- `Container(children=[...])`, `Draggable(children=[...])` e afins **falham no
  build** do Modo C, com o slot certo na mensagem: troque para `child=`. Nos
  Modos A e B essas chamadas já levantavam `ValidationError` — o Modo C só parou
  de discordar.
- `Container(child=...)` e `Form(fields=[...])` **passaram a renderizar** no Modo
  C. Se você contornou o bug duplicando a árvore por modo, o contorno pode sair.
- Handler de gesto e prop multi-palavra **passaram a chegar** no widget em Modo C
  (`on_drop`, `drag_data`, `min_value`, `on_submit`, …). Se você duplicava lógica
  por modo por causa disso, dá para unificar.
- `RetryOptions(backoff=...)` levanta `ValidationError` nomeando o campo. O botão
  equivalente é `base_delay` (espera antes do primeiro retry) ou `factor`
  (multiplicador por tentativa).

### Added

- **Conformance de alcance**: um teste afirma que todo campo do core é um
  parâmetro do builder gerado (exceto `theme`/`media`, que alimentam a resolução
  de estilo MD3 dentro do próprio builder) — então campo novo no core que ninguém
  regenerou falha em vez de virar prop morta.
- **Conformance dos slots**: dois testes afirmam, contra o core vivo, que todo
  builder gerado declara o nome de slot do core e o dobra no `children` da IR na
  ordem de declaração (`RouteDrawer` constrói `[child, drawer]`, nunca o
  contrário).

## [0.78.1] — 2026-08-22

### Fixed

- **Modo C voltou a funcionar para a app que o próprio `tempestweb new`
  escreve.** O transpiler fixava o nome da base injetada como `State`, então um
  módulo que declara a própria dataclass `State` — exatamente o que os dois
  templates de scaffold escrevem — emitia `import { State } from "./runtime.js"`
  **e** `export class State extends State`: duas declarações do mesmo
  identificador, `SyntaxError` que derruba o módulo inteiro. Nada falhava no
  transpile; o browser logava `Identifier 'State' has already been declared` e a
  página ficava em branco. Agora a base entra sob alias (`State as State$`) e a
  classe local vence, como em Python. O `$` é legal em identificador JS e nunca
  em identificador Python, então o alias não pode colidir com nome transpilado.
- **Classe local que sombreia qualquer nome importado** (`class Text`, por
  exemplo) deixa de emitir o import junto com a declaração — mesma dupla
  declaração, para qualquer nome que o módulo reusa.

### Added

- **Guard: todo JS que o transpiler emite tem que parsear** como ES module
  (`node --check`), cobrindo os dois templates de scaffold e cada
  `examples/*/app.py` dentro do subset do Modo C. Os goldens comparavam o texto
  gerado, então o transpiler podia emitir um módulo que o browser recusa a
  carregar com a suíte inteira verde — foi assim que este bug passou. Sem o fix,
  o guard falha nos dois templates.

## [0.78.0] — 2026-08-22

### Changed

- **Piso `tempest-core>=0.14.0`**, e todo import passa a vir da raiz do pacote.
  A 0.14.0 re-exporta os 343 símbolos públicos do core (eram 101), então
  `from tempest_core import Input` finalmente funciona — e os **104 arquivos**
  deste repo que importavam de submódulo (`tempest_core.widgets.inputs`,
  `.style`, `.widgets.events`, …) passaram a seguir a própria regra de casa:
  237 imports em código, 481 em docs e README.

  Isso era dívida com juros: cada exemplo da documentação ensinava o caminho que
  a regra proíbe, porque era o único que funcionava.

- **`ActionSheet` agora declara `on_dismiss`** (via core 0.14.0), então `Escape`
  e clique no scrim fecham uma action sheet — o cliente já reportava o evento e
  não havia handler para receber. O `client/transpile/widgets.gen.js` foi
  regenerado para incluí-lo.

### Fixed

- **Dois kwargs inválidos que passavam em silêncio nos testes deste repo**,
  revelados pelo `extra="forbid"` do core 0.14.0:

  - `Alert(message="heads up")` — o widget declara `title`/`body`, então o alerta
    era construído **vazio** e o teste passava porque só conferia os tipos de nó
    em que um componente aterrissa;
  - `Text(content=..., on_click=...)` — `Text` não declara handler. O teste
    afirmava que um clique **não** dispararia o handler e passava pelo motivo
    errado: o handler nunca existiu. Virou `Button`.

## [0.77.2] — 2026-08-22

### Fixed

- **Um reporte de viewport por frame, e nenhum quando nada mudou.** `resize`
  dispara continuamente enquanto a borda da janela é arrastada, e no Modo B cada
  reporte é ida-e-volta no socket mais rebuild e diff — o fluxo que sai de graça
  no Modo C não sai lá. Os reportes passam a colapsar num por animation frame, e
  um frame cujo snapshot é igual ao último enviado não reporta nada.

- **`apply_media` recusa booleano em campo numérico.** `isinstance(True, int)` é
  verdadeiro em Python, então o Pydantic aceita `{"width": true}` como
  `width=1.0` — medido. A validação passou a ser campo a campo: número que não é
  número, ou tipo errado em qualquer campo, descarta o payload inteiro em vez de
  envenenar o contexto com um snapshot parcial.

  Os dois vêm do PR paralelo #84, que resolveu a issue #74 por outro caminho;
  ficou a estrutura desta base com o throttle e a validação de lá, mais os testes
  que os cobrem (rajada de resize, frame sem mudança, payload parcial e
  malformado).

## [0.77.1] — 2026-08-22

### Fixed

- **O trap de foco de modal ficou mais preciso sobre o que é um ponto de
  tabulação.** A lista passou a incluir `area[href]`, `iframe`, `object`, `embed`
  e `[contenteditable="true"]` — um editor de texto dentro de um diálogo é,
  muitas vezes, a razão de o diálogo ser modal —, e um controle que a app
  esconde (`hidden`, ou invisível segundo `checkVisibility`) deixa de ser
  focado em silêncio.

  A checagem de visibilidade é `checkVisibility()`, **não** `offsetParent !==
  null`: esse atalho é nulo para elemento `position: fixed`, que é exatamente o
  que um overlay é — usá-lo chamaria todo ponto de todo modal de escondido, e o
  trap cairia no fallback de focar a caixa em página real, não só sob jsdom.

  Refinamentos trazidos do PR paralelo #88, que resolveu o mesmo item da #77 por
  outro caminho; ficou a estrutura desta base com a precisão de lá, mais três
  testes que ele escreveu — modal empilhado devolvendo o teclado ao de baixo,
  controle escondido fora da ordem, e região editável como ponto de tabulação.

## [0.77.0] — 2026-08-22

### Changed

- **Item de menu alinha o rótulo quando o menu tem ícones.** A 0.71.0 passou a
  desenhar o `icon` do `MenuItem`, mas só nos itens que nomeiam um: o rótulo dos
  demais começava uma largura de glifo à esquerda, o que lê como menu quebrado e
  não como menu com alguns ícones. Agora, assim que **algum** item nomeia um
  ícone, todos ganham o slot — vazio onde não há ícone —, e o rótulo leva o resto
  da linha (`flex: 1 1 auto`), então rótulo longo quebra dentro do item em vez de
  empurrar o glifo. Menu sem ícone nenhum não ganha slot.

  Refinamento trazido do PR paralelo #86, que resolveu o mesmo item da #77 por
  outro caminho: ficou a estrutura desta base (`data-tw-part="item-label"`, que é
  o que o listener de seleção lê) com o comportamento de alinhamento de lá, mais
  os quatro testes que ele escreveu — slot vazio, menu sem ícones, nome
  desconhecido e clique sobre o glifo.

## [0.76.0] — 2026-08-22

Os dois últimos handlers inertes: a câmera.

### Fixed

- **`CameraPreview` e `QrScanner` renderizavam caixas vazias** (issue #77,
  item 1 — o último). Os dois declaram handler (`on_frame`, `on_scan`) e o
  renderizador DOM não os conhecia: nenhum stream, nenhum preview, nada para
  amostrar ou decodificar. Ambos são folhas da IR, então o renderizador é dono do
  que vai dentro — um `<video>` tocando o stream, como um `ProgressBar` é dono do
  próprio fill.

  O stream abre quando o widget aparece e **fecha quando ele sai**, o que aqui
  importa mais que na maioria dos recursos: câmera aberta é luz acesa no celular
  de alguém.

- **`on_frame` funciona.** O preview amostra o vídeo num canvas a cada
  `frame_interval_ms` e reporta `{width, height, data, rotation}` com o frame em
  base64 — o `CameraFrameEvent` do core. `facing` vira o `facingMode` do
  `getUserMedia`.

- **`on_scan` funciona**, usando o `BarcodeDetector` do próprio navegador, e
  reporta a **mudança** de código, não a presença: um QR fica no enquadramento
  por dezenas de frames, e reportar cada um transformaria uma leitura em dezenas
  de chamadas de handler.

  Onde o `BarcodeDetector` não existe (hoje, tudo fora de Chrome/Android) o
  widget mostra a câmera e **avisa no console**, uma vez. Não há decoder de
  reserva de propósito: este cliente não embute dependência de runtime, e a
  alternativa honesta é `CameraPreview` + decodificação própria sobre os frames.

- **Permissão negada e API ausente falham alto.** `getUserMedia` que rejeita
  avisa com a mensagem do browser e não deixa `<video>` órfão; página sem
  `mediaDevices` (contexto inseguro) avisa uma vez para a página, não uma por
  widget.

### Added

- **`examples/camera_demo`** — preview com contador de frames e tamanho do último,
  mais um leitor de QR com histórico. Verificado em Chrome real com um stream de
  `canvas.captureStream()` e um `BarcodeDetector` stub (não há câmera neste
  ambiente): 4 frames em 2,5s no intervalo de 500ms, último `320 × 240` com 2064
  caracteres base64, dois códigos deduplicados na ordem certa, `<video>` com
  `object-fit: cover`.

### Docs

- A página de capacidades (PT + EN) ganhou "Preview ao vivo e leitor de QR",
  separando a **capacidade** (`camera.capture()`, uma foto) dos **widgets** (a
  câmera ligada), com o orçamento de rede do `frame_interval_ms` e o aviso sobre
  o `BarcodeDetector`.

## [0.75.0] — 2026-08-22

A paleta que um app declara agora chega aos componentes — nos dois modos Python.

### Fixed

- **O Modo A não tinha como receber tema nenhum** (issue #77, item 3). O
  `AppSession` aceita `theme=` desde a 0.66.0 e o `WasmRuntime` não aceitava
  nada: um app em Modo A renderizava botões roxos-baseline por construção, sem
  caminho para a própria paleta. `WasmRuntime(..., theme=)` fecha isso, e
  `bootstrap` o repassa.

- **Os artefatos gerados ignoravam a paleta do app.** O `server.py` do Modo B
  chamava `create_app(make_state, view, title=...)` e o `bootstrap.js` do Modo A
  chamava `bootstrap(make_state(), view, ...)`, os dois sem tema — então
  declarar uma paleta não tinha efeito. Ambos passam a ler `app.THEME` (opcional)
  e entregá-la nas duas pontas: à árvore (componente resolve cor em **Python**) e
  à página (os tokens `--tw-*` que a folha base lê). No Modo A a página é
  estática e o app só existe depois do Pyodide, então o CSS vem do
  `WasmAppHandle.theme_css()` e é injetado antes do primeiro mount.

- **`examples/theme-switcher` mostrava botões roxos com accent teal.** A causa
  não era o caminho do tema: um `Theme` carrega um **conjunto de tokens** e
  alguns campos soltos de conveniência (`primary`, `background`, …), e os
  componentes leem os tokens. O exemplo montava o tema preenchendo só os campos
  soltos, então a árvore inteira ficava na paleta baseline. Passou a usar
  `Theme.from_seed`. Medido em Chrome: escolher o swatch teal leva o botão de
  `rgb(88, 71, 133)` para `rgb(28, 176, 163)`.

### Added

- **Convenção `THEME`**: um módulo de app que expõe `THEME: Theme` tem a paleta
  entregue pelo host, sem configurar nada no artefato. `examples/theme-switcher`
  declara a sua, então o Modo A abre já no azul da marca (medido:
  `--tw-primary: #1c4ab0` e botão `rgb(28, 74, 176)` no primeiro paint, com o
  `<style id="tw-app-theme">` presente).

- **`tempestweb/html` entrou no bundle do Modo A**, porque é de lá que sai o
  emissor de tokens de tema. Python puro sobre o core, nenhuma dependência nova;
  o guard de fechamento do bundle (0.67.0) pegou a falta na hora.

### Docs

- A página de temas ganhou "Declare o tema, e o host o entrega" (PT + EN), com
  os dois avisos que custam tempo: `Theme(primary=...)` **não** é
  `Theme.from_seed(...)` (campo solto não é token, e é o token que pinta), e tema
  trocado em runtime repinta os componentes mas não reescreve os tokens da
  página.

## [0.74.0] — 2026-08-22

Os gestos multi-ponteiro que o core declarava e o cliente nunca reconheceu.

### Fixed

- **`on_pan`, `on_scale`, `on_double_tap` e `on_interaction` funcionam**
  (issue #77, item 1 — o último bloco de gestos). O cliente rastreava **um**
  ponteiro e só classificava tap / swipe / long press: um `PanHandler` era uma
  caixa inerte, uma pinça não existia, e o duplo toque — o atalho que toda
  superfície de zoom precisa — não era detectado em nenhum widget.

  Agora é **um** reconhecedor (`client/gestures.js`), porque os gestos
  compartilham uma máquina de estado: o mesmo `pointerdown` pode virar tap, pan,
  pinça ou a segunda metade de um duplo toque, e só os ponteiros ainda em contato
  decidem qual. Dois reconhecedores no mesmo root veriam metade da história cada.
  O reconhecimento de tap/swipe/long-press saiu de dentro do `events.js` para lá,
  sem mudança de comportamento — `bindEvents` continua sendo a única porta de
  entrada de input que um mount usa.

- **Gesto contínuo custava uma ida e volta por `pointermove`.** `pan`,
  `scale` e `interaction` passam a ser reportados no máximo uma vez por frame,
  mantendo o **último** valor: reportar o primeiro faria o gesto atrasar e depois
  pular.

- **Largar uma pinça deixava a app um passo atrás.** O pendente do frame é
  descarregado quando um ponteiro sai. Medido no Chrome com dois dedos de
  verdade (via CDP): uma pinça de 100px → 200px assentava em **1,5×** antes, e
  fecha em **2,00×** agora.

- **Uma superfície de gesto não recebia `pointermove` no celular.** Um browser
  não manda nada enquanto está ocupado rolando a própria página; a folha base
  agora tira o `touch-action` de `PanHandler`, `ScaleHandler` e
  `InteractiveViewer` — e **só** desses. `GestureDetector` fica de fora de
  propósito: tap, swipe e long press convivem com a rolagem, e tirar o
  `touch-action` dele quebraria o scroll de qualquer lista que envolva as linhas
  num detector.

### Changed

- **`examples/gesture_demo`** passou a ter as três superfícies (discreta, pan e
  viewer) com o estado de cada uma na tela. Verificado em Chrome real: arrastar
  o `PanHandler` com o mouse acumula exatamente o deslocamento aplicado
  (`offset 100, 30`), dois cliques rápidos no pad viram `tap` → `double tap`, e
  no viewer a pinça de dois dedos fecha em 2,00× enquanto um dedo reporta
  `scale=1` com o foco onde o dedo está.

### Docs

- A página "Arrastar, reordenar, paginar" ganhou a seção de gestos de ponteiro,
  com a tabela widget → handler → evento e as três coisas que decidem se o gesto
  fica bom: `on_pan` é relativo, `on_interaction` é `ScaleEvent` mesmo no pan, e
  `touch-action` sai só das superfícies contínuas.

## [0.73.0] — 2026-08-22

Um campo de código que não existia, e um formulário que só falava no fim.

### Fixed

- **`PinInput` renderizava como uma `div` vazia** (issue #77, item 1). O widget
  declara `length`, `value`, `secure`, `on_change` e `on_complete`, e o
  renderizador DOM não o conhecia: não havia o que digitar, então nenhum dos
  dois handlers era alcançável. Agora é um `<input>` de verdade com
  `maxlength`, `inputmode="numeric"` e `autocomplete="one-time-code"` — um
  campo, não `length` caixinhas, porque é isso que a plataforma recompensa: o
  browser (e o iOS/Android) oferece preencher o código do SMS, o teclado
  numérico aparece, e colar o código inteiro funciona. A folha base espaça os
  caracteres para continuar lendo como campo de código.

- **`on_complete` funciona.** O cliente reporta `complete` na **transição** para
  cheio — uma tecla num campo já cheio não reporta de novo, e limpar rearma —
  junto do `change` de sempre, porque a app ainda quer cada tecla.

- **`on_validate` funciona** (issue #77, item 1). Um `FormField` não levava o
  próprio `name` para o DOM, então o cliente não tinha o que reportar e a
  validação só podia acontecer no submit: o leitor descobria o e-mail errado
  depois de preencher seis campos. O cliente agora reporta a **ocasião** — este
  campo, este valor — no `focusout` (que borbulha, ao contrário do `blur`), e o
  handler roda os validadores de verdade. Ele não pode validar sozinho: os
  validadores de um campo são callables Python que nunca atravessam o fio.

- **O `error` de um `FormField` era prop que ninguém desenhava.** Ele não pode
  virar filho sem deslocar o índice pelo qual o filho do campo é endereçado, então
  vira atributo e a folha base o pinta sob o controle via `::after` — o mesmo
  truque do título de um `Dialog` —, com `aria-invalid` no campo para a mensagem
  ser anunciada e não apenas exibida.

### Added

- **Guard contra o backtick no `client/theme.js`.** O CSS base vive dentro de um
  template literal, então um backtick num comentário é `SyntaxError` que derruba
  o cliente inteiro — e a mensagem aponta para o comentário, não para o que
  quebrou. Aconteceu três vezes escrevendo as seções novas desta leva; agora um
  teste lê o arquivo como texto (importar o módulo seria a própria falha) e
  falha explicando onde está o backtick.

### Changed

- **`examples/form`** ganhou o terceiro campo (código de convite, com
  `PinInput` + `on_complete`) e `on_validate` nos dois primeiros, então o exemplo
  passou a demonstrar validação ao sair do campo em vez de só no submit.
  Verificado em Chrome real: sair do e-mail vazio pinta "Email is required" com
  `aria-invalid=true` e `content` do `::after` medido; corrigir e sair limpa;
  digitar `12` mantém "pending" e completar `1234` vira "accepted".

## [0.72.1] — 2026-08-22

### Fixed

- **O artefato do Modo C não linkava ícone de aba.** Um browser não lê o
  manifest para o ícone da aba: sem `rel="icon"` ele sonda `/favicon.ico`, e um
  bundle estático não tem rota para responder — então todo carregamento de todo
  deploy em Modo C abria o console com um 404 que ninguém pode resolver. A
  0.67.0 corrigiu isso nos Modos A e B e passou reto pelo C. Agora um teste
  parametrizado cobre os três shells: cada um linka `rel="icon"` e o arquivo
  apontado existe no artefato.

### Docs

- A skill `validate-implementation` e o `CLAUDE.md` ganharam as armadilhas que
  esta rodada de validação custou: **limpar service worker e caches antes de
  medir** (um SW servia o build anterior — e, numa porta reusada, outro app
  inteiro), verificar durante o gesto e não só no fim (posição intermediária de
  scroll reportada faz a app desfazer o próprio movimento), e que um widget do
  core **ignora kwarg que não declara** (`Container(on_click=...)` é aceito e
  descartado, sem erro).

## [0.72.0] — 2026-08-22

Dois gestos de container que o core declarava e o DOM não tinha.

### Fixed

- **`on_reorder` funciona: uma `ReorderableList` pode ser ordenada arrastando**
  (issue #77, item 1). O contrato HTML5 de drag existia para
  `Draggable`/`DragTarget`, mas as linhas de uma lista reordenável são widgets
  comuns — quem declara o handler é a **lista**, e o evento que ela quer é um
  par de posições. O cliente marca as linhas arrastáveis depois de cada batch
  (uma linha entra e sai por patch no *pai*, que nunca passa pelos props do
  próprio pai) e lê um arrasto entre duas delas como
  `{from_index, to_index}`. As posições são calculadas do DOM no momento do
  evento: índice gravado na linha ficaria velho no primeiro remanejamento.

- **`on_page_change` funciona: um `PageView` é um carrossel** (issue #77,
  item 1). O widget renderizava como caixa comum — não havia página para
  arrastar nem o que reportar. A folha base o transforma num scroller
  horizontal com snap (um filho por largura de viewport), o que traz swipe de
  touch, trackpad e `shift`+roda do próprio navegador; `client/pages.js` reporta
  em qual página o scroll assentou, e `dom.js` rola até a página que a app
  pediu, então o caminho é de mão dupla.

  O reporte **espera o scroll parar**, e isso não é refinamento: uma rolagem é
  um fluxo de eventos cujas posições intermediárias arredondam para a página que
  está sendo deixada. Medido no Chrome: apertar "Next" enviava o clique e, no
  mesmo instante, um `page_change` dizendo "voltei para a página anterior" — a
  app desfazia o próprio movimento. Com o assentamento, `Next` leva 0 → 1 → 2
  (scrollLeft 0 → 452 → 904) e o swipe de volta leva 2 → 1.

### Added

- **`examples/reorder_demo`** — uma lista de tarefas ordenada por arrasto, com
  log dos movimentos. Verificado em Chrome real: arrastar a primeira linha sobre
  a última reordena de fato (`Write the spec: 0 → 3`).

- **Nova página de tutorial bilíngue "Gestos: arrastar, reordenar, paginar" /
  "Gestures: drag, reorder, paginate"** (`docs/tutorial/gestures.md`), que
  também documenta o par `Draggable`/`DragTarget`, que não tinha página.

## [0.71.0] — 2026-08-22

O resto do contrato de modal, e o ícone que um item de menu declarava.

### Fixed

- **Nenhum overlay prendia o foco** (issue #77, item 4). Um modal pintava sobre
  a app com scrim e `Escape`, e o teclado continuava na página **atrás** dele:
  `Tab` passeava por formulários que o leitor não podia ver, e fechar deixava o
  foco em lugar nenhum. `client/focus.js` fecha as três obrigações — foco entra
  ao abrir (primeiro controle, ou o próprio overlay quando não há nenhum),
  `Tab`/`Shift+Tab` circulam dentro e embrulham nas pontas, e ao fechar o foco
  volta para o elemento que abriu. Overlay não-modal (`Menu`, `Popover`,
  `Toast`) é deixado em paz, porque roubar o foco quebraria o widget que o
  abriu.

  Medido em Chrome real no `examples/overlay_demo`: foco `open` → `close` do
  diálogo ao abrir, `Tab` preso, `Escape` devolvendo para `open`; e na action
  sheet, `Shift+Tab` do primeiro item embrulhando para o último.

- **`Menu` e `ActionSheet` descartavam o `icon` do `MenuItem`** (issue #77,
  item 2). `MenuItem` declara `label`, `value` e `icon`; o renderizador
  desenhava os dois primeiros. Agora o ícone é resolvido pelos mesmos dois
  registros do widget `Icon` (nome puro = Lucide, prefixo `material:` =
  Material) e inserido antes do rótulo, que passou a viver num span próprio para
  o `select` continuar lendo o rótulo limpo. O item virou uma linha flex com
  gap, e o glifo tem tamanho fixo.

### Added

- **Nova página de tutorial bilíngue "Overlays e modais" / "Overlays and
  modals"** (`docs/tutorial/overlays.md`): abrir e fechar pelo id, o que
  `barrier=True` significa, o contrato de teclado, menu com ícone, overlay
  ancorado e toast — mais o aviso de que um modal sem `on_dismiss` nem botão de
  fechar prende o usuário.

- **`examples/overlay_demo`** ganhou um `ActionSheet` com ícones e um handler de
  seleção, então o exemplo cobre as duas metades que faltavam ao contrato de
  modal.

## [0.70.0] — 2026-08-22

Um app em Modo A ou B não sabia o tamanho da própria janela.

### Fixed

- **`App.media` agora segue o browser nos três modos** (issue #74). A docstring
  do `MediaQueryData` sempre prometeu que "o renderizador mantém isso
  atualizado via `App._update_media` em resize / mudança de configuração", e
  nada neste pacote chamava: o reporter (`media.js`) morava em
  `client/transpile/` e só o runtime do Modo C o instalava. Um app em Modo A ou
  B rodava para sempre com `width = height = 0`, então:

  - uma `view` que escolhe layout por breakpoint escolhia sempre o mesmo ramo;
  - um frame que se limita pela altura do viewport (`Scaffold(scroll=True)`, que
    só segura `app_bar`/`bottom_bar` se a coluna em volta for limitada, e
    `Style` não tem `100vh`) não tinha limite nenhum — a página inteira rolava e
    as ações iam para o fim do documento.

  O módulo sempre foi genérico (depende só do `transport`), então virou
  `client/media.js` e o `mount()` compartilhado o instala. `apply_media` faz a
  metade Python: valida o payload num `MediaQueryData` e entrega ao
  `App._update_media`, que já pede o rebuild coalescido. Campo ausente mantém o
  default (nenhum browser reporta `text_scale_factor`); payload malformado é
  ignorado.

  Medido nos três modos com Chrome real, no novo `examples/responsive_demo`:
  1200×850 monta em `Row`, estreitar para 430px vira `Column`, e o snapshot
  impresso na tela acompanha resize, orientação e `prefers-color-scheme`.

- **O reporte inicial de viewport era descartado no Modo C.** O `installMedia`
  reporta na hora, e no Modo C esse reporte reconstrói a árvore em processo —
  mas ele era instalado antes de `transport.onPatches`, então os patches iam
  para um sink inexistente **enquanto a árvore do runtime avançava**: o DOM
  ficava no render anterior (`0 × 0` até o primeiro resize) e todo diff seguinte
  era calculado contra uma árvore que o DOM não tinha. A instalação agora é a
  última coisa que o `mount()` faz.

- **Variável local tipada não era emitida pelo transpiler (Modo C).**
  `ast.AnnAssign` estava agrupado com `pass` no dispatcher de statements, então
  `layout: Widget = Row(...) if wide else Column(...)` — a forma que as regras
  de estilo deste repo pedem — desaparecia do módulo gerado. Nada falhava no
  transpile; o browser levantava `ReferenceError: layout is not defined`.
  Declaração sem valor (`total: int`) segue emitindo nada.

### Added

- **`examples/responsive_demo`** — a mesma `view` em dois layouts, com a foto do
  viewport impressa na tela, rodando nos três modos.

- **Nova página de tutorial bilíngue "Layout responsivo" / "Responsive layout"**
  (`docs/tutorial/responsive.md`): os seis campos de `app.media`, breakpoint por
  conteúdo, frames com altura de viewport, tema do sistema, e como o evento
  `media` chega em cada modo.

## [0.69.0] — 2026-08-22

Uma auditoria da perna do Modo B, e depois um browser em cima dela.

### Fixed — Modo B (transporte, sessão, segurança)

- **Um frame de WebSocket inválido matava a sessão inteira — sem log.** O demux
  de entrada capturava apenas `(WebSocketDisconnect, RuntimeError)`, mas o
  `receive_json` do Starlette levanta `KeyError` num frame **binário** (ele lê
  `message["text"]`) e `JSONDecodeError` num texto que não é JSON. Nenhum dos
  dois era capturado, então um único frame ruim encerrava o pump — e no Modo B a
  conexão **é** a sessão: o cliente perdia todo o estado da aplicação, reconectava
  numa sessão nova e a tela voltava ao início. Medido contra um uvicorn real:

  ```text
  baseline                  -> sessão VIVA
  frame texto "nao-json"    -> sessão MORTA (sem close frame)
  frame binário JSON-válido -> sessão MORTA
  ```

  Pior: o `close()` aguardava a task morta sob `suppress(Exception)`, então o log
  do servidor ficava **vazio** enquanto o app do usuário reiniciava. Agora os
  frames passam por um decoder que aceita os dois opcodes (o wire format é JSON
  de qualquer jeito) e **descarta** um frame indecifrável com um aviso, em vez de
  encerrar o pump; um pump que ainda quebre é logado.

- **Patches podiam chegar fora de ordem no WebSocket.** A sessão dispara uma task
  de envio por tick (a reconstrução coalescida do core não pode `await`), então
  dois batches podiam estar dentro do `send_json` ao mesmo tempo e, sob
  backpressure, alcançar a rede trocados. Patch é relativo a índice: um par
  invertido corrompe a árvore do cliente. Os envios agora passam por um lock FIFO.

- **O replay do SSE reentregava, duplicava e perdia ticks.** Cada envelope era
  escrito no buffer de replay **e** numa `asyncio.Queue`; o `stream()` replayava o
  buffer e depois drenava a fila. Um cliente reconectando com `Last-Event-ID: 1`
  contra um buffer de 3 e 6 ticks enfileirados recebia `4, 5, 6, 1, 2, 3, 4, 5, 6`
  — fora de ordem e com três duplicatas. Pior, a fila fazia dois streams no mesmo
  transporte **dividirem** o stream de ticks entre si: cada um recebia metade dos
  envelopes e nenhum tinha a árvore inteira. O stream agora é um cursor sobre o
  buffer, que é a única fonte de envelopes de saída, e abrir um stream **retira** o
  anterior.

- **O `session` da URL do SSE autorizava qualquer um.** O id é escolhido pelo
  cliente, mas o `_open_sse` anexava quem o apresentasse à sessão já registrada
  sob aquele id. Um segundo requisitante lia então o stream de patches da vítima —
  o estado renderizado da tela dela — e podia postar eventos na sessão dela;
  reusar um id vivo também pulava o rate limit e o teto de conexões, que são
  condicionados ao id ser novo. Reproduzido contra um servidor real:

  ```text
  sessions vivas: 1          <- o atacante entrou na sessão da vítima
  VITIMA    patches n=1
  ATACANTE  patches n=2      <- leu o estado da vítima
  VITIMA    patches n=3
  ```

  A sessão agora grava a impressão digital de quem a abriu (o token de auth
  quando o host autentica, senão o endereço do cliente) e todo `GET`/`POST`
  posterior naquele id precisa casar, ou responde `403`. Reabrir o stream é um
  **takeover**: só o dono do token de stream mais novo pode desmontar a sessão —
  a limpeza anterior derrubava a sessão que o cliente tinha acabado de retomar.

- **`X-Forwarded-For` do cliente contornava todo limite por IP.** O header é dado
  enviado pelo cliente; variá-lo por request comprava uma identidade nova, então
  contra `max_connections_per_minute=3` oito conexões forjadas foram todas
  aceitas. Agora ele só é lido quando `SecurityConfig.trusted_proxies` declara o
  peer como proxy, e então **da direita para a esquerda** — um proxy anexa o
  endereço que viu, então o hop mais à direita que não é proxy é o mais distante
  de que o deploy pode dar fé. Default: o peer do socket.

- **O `RateLimiter` guardava uma entrada por endereço já visto.** Os buckets só
  eram podados quando a própria chave voltava, então 10 mil endereços distintos
  deixavam 10 mil entradas — memória que um flood de valores forjados crescia à
  vontade — enquanto a docstring afirmava o contrário. Chaves cuja janela passou
  agora são varridas periodicamente.

- **Dois espaços de `call_id` colidiam no mesmo registro.** `AppSession.native_call`
  cunhava ids de um contador por sessão enquanto toda capacidade (`await native.*`)
  usava o global do módulo de dispatch — e ambos caem no mesmo
  `ProxyBridge._pending`. Dois chamadores podiam entregar o mesmo `"c1"`: o
  segundo registro substituía o future do primeiro, então um `await` ficava
  pendurado pela vida da sessão e a única resposta do cliente resolvia a chamada
  que ainda detinha o id — a leitura de clipboard podia ser entregue a quem
  esperava uma posição de GPS.

- **`native_call` esperava para sempre.** Uma aba fechada no meio, ou uma
  capacidade que quebrou antes de responder, suspendia o handler até a sessão
  terminar. Agora falha com o código `timeout` documentado após
  `DEFAULT_NATIVE_CALL_TIMEOUT` (30s).

- **Uma prop `null` não limpava o DOM que ela mesma tinha escrito.** O conjunto
  de props de um widget é fixo, então uma prop que o app deixa de passar chega
  como `set_props: {"<nome>": null}` — e todo aplicador testava `!= null`, lendo
  isso como "não mexa". Verificado com os patches que o core realmente emite: ao
  limpar o `semantics` de um `Text`, o elemento continuava com
  `aria-label="rotulo"` e `role="alert"`; um `max_length` limpo continuava
  limitando o input. O `unset_props` tinha o mesmo buraco pelo outro lado, cobrindo
  só `style`/`content`/`label` enquanto `src`, `value`, `attrs` e os atributos de
  acessibilidade ficavam para trás. Confirmado em browser real (Mode B): a árvore
  de acessibilidade ia de `status "the greeting"` para `generic` só depois da
  correção.

- **Um patch que não aplicava deixava a tela derivando.** O `applyPatches`
  abortava o batch no meio com um `RangeError` e nenhum reparo: a árvore ficava
  meio-atualizada e cada tick seguinte aplicava mais patches relativos a índice
  sobre ela. Agora o batch para na primeira falha e o mount pede um **resync**.

- **`RedisSessionRouter.deliver` mentia.** Retornava `True` houvesse ou não
  instância assinando o canal, então um POST para uma sessão já encerrada
  respondia `204` e o evento evaporava. Agora usa a contagem de assinantes que o
  `PUBLISH` devolve, e o chamador responde `404` como o contrato do
  `SessionRouter` manda.

- **Um handler que levantava encerrava a sessão do Modo B.** No despacho serial a
  exceção subia pelo `run()` e fechava a conexão — e a conexão é a sessão, então
  um handler com bug jogava fora todo o estado do cliente, que reconectava numa
  sessão nova e voltava à tela inicial sem nada no log explicando. Agora é logado
  e o laço segue, como o despacho concorrente já fazia. (Encontrado ao verificar
  as correções do DOM num browser.)

- **Os locks de ordenação por key cresciam sem limite.** Um deles era guardado
  para cada key já despachada, liberados só no teardown; agora são contados por
  referência e descartados quando ninguém está na fila.

- **Os wheels do Pyodide eram gravados sem conferência.** O `vendor_pyodide`
  escrevia no artefato o que o CDN devolvesse, ignorando o `sha256` que cada
  entrada do `pyodide-lock.json` publica. Os digests agora são verificados, então
  um wheel truncado ou trocado quebra o build em vez de ser distribuído. Não
  defende contra um lock errado — ele vem do mesmo host — e os arquivos de
  runtime, que o lock não cobre, seguem sem verificação.

### Changed

- **`verify_jwt` passa a exigir o claim `exp`.** A função prometia validar
  "assinatura e expiração", mas o PyJWT só confere uma expiração que existe: um
  token emitido sem `exp` era aceito para sempre. Passe `require_expiry=False`
  (em `verify_jwt` e `jwt_authenticator`) para um token cuja vida outra coisa
  limita.
- **`attrs` recusa atributo de evento inline** (`onclick`, `onerror`, …) nos dois
  renderizadores. É um escape hatch para markup que o app possui (`id`, `class`,
  `data-*`, `hx-*`); um valor `on*` é **código**, então um widget construído com
  dado que o app não escreveu embarcaria um script na página. O SSR levanta, o
  renderizador de DOM ignora com aviso.
- **Servir sem `SecurityConfig` agora loga um `WARNING`** dizendo o que está
  desligado: sem auth, sem allowlist de origem (qualquer site abre um WebSocket —
  o CORS não protege o upgrade) e sem limites.

### Fixed — renderização (encontrados no browser)

- **`Draggable` e `DragTarget` não arrastavam.** O core sempre teve os dois
  widgets, o renderizador SSR desenhava suas caixas e a documentação ships um
  tutorial bilíngue inteiro do exemplo kanban — mas nada implementava a
  interação. O renderizador do DOM os deixava como `div` anônimos (nada marcado
  `draggable`, nenhum alvo de drop), o `events.js` não capturava evento de drag
  algum, e a tabela de roteamento não tinha os tipos `drag`/`drop` — então mesmo
  um envelope enviado à mão não resolvia handler. Verificado no Chrome antes da
  correção: arrastar um cartão até a lixeira não fazia absolutamente nada.

  É o modo de falha do `ProgressBar` em 0.65.0 outra vez: a árvore afirma uma
  feature que a tela nunca teve. Agora um `Draggable` é um elemento arrastável de
  verdade com seu payload em `data-tw-drag-data`, o `dragover` de um `DragTarget`
  chama `preventDefault` (sem isso o browser recusa o drop inteiro), e o `drop`
  emite o payload contra a key do alvo — nos três modos, porque o Modo C monta
  pelo mesmo cliente.

- **A camada de overlay não sobrepunha nada.** O `mount()` aplica os patches da
  camada de overlay num host próprio, mas o host era um `<div>` sem estilo
  anexado depois da árvore e nenhum widget de overlay tinha regra própria. O
  "I am a floating dialog" do exemplo renderizava **no fluxo**, no fim da página:
  sem card, sem scrim, sem centralização — e o `title` ("Hello") nunca era
  desenhado, porque o título de um `Dialog` é prop, não filho.

  O host agora é uma camada fixa de viewport inteiro, transparente ao ponteiro
  (para não engolir cliques na app quando vazia), com cada overlay recuperando o
  ponteiro. `Dialog` é card centralizado com scrim, `BottomSheet` é painel
  inferior, `Toast` é pílula transitória sem scrim. O título é pintado a partir de
  `data-tw-title` por `::before` — inserir um elemento deslocaria os índices a que
  todo patch de filho é relativo — e espelhado em `aria-label`. `Dialog`/
  `BottomSheet` ganham `role=dialog` + `aria-modal`; `Toast`, `role=status` +
  `aria-live=polite`, porque um toast que ninguém anuncia é invisível para leitor
  de tela.

- **Um `Canvas` era um bitmap esticado.** Um canvas tem dois tamanhos — o buffer
  de pixels e a caixa que o CSS lhe dá — e só o buffer era definido. Dentro de um
  flex column, `align-items: stretch` (o default do CSS) puxava um gráfico de
  320×200 para 909×568: os rótulos de eixo do admin-console saíam 2,8× maiores e
  borrados, e o card superdimensionado empurrava o resto da página para fora da
  tela. Em tela HiDPI o mesmo bitmap era esticado outra vez pelo device pixel
  ratio. Agora a caixa é fixada no tamanho declarado (default que o `Style` da app
  sobrescreve), o buffer é dimensionado pela caixa real vezes o DPR, e o contexto
  é escalado para preservar o sistema de coordenadas em que os comandos de desenho
  foram escritos. Canvases repintam depois do layout e no resize.

- **O `role` default de cada widget era apagado.** A limpeza de prop `null`
  (0.66.0) fez `semantics: null` remover `role`/`aria-label` — correto por si, mas
  rodava **depois** de cada widget definir seus próprios defaults, então os
  apagava. E o core põe toda prop declarada no fio, logo `semantics: null` é o que
  um widget sem semantics sempre manda. Medido contra as props reais:

  ```text
  ProgressBar  role=null  aria-valuemin=0   <- valuemin sem role
  Spinner      role=null
  Toast        role=null                    <- não anunciava nada
  Dialog       role=null  aria-label=null   <- e título sem nome acessível
  ```

- **Um campo de senha se desmascarava na primeira tecla.** O `type` do `Input`
  era rederivado de todo bag de props (`props.secure ? "password" : "text"`).
  Digitar aplica patch só em `value`, então o update seguinte não trazia `secure`,
  lia `undefined` e definia `type="text"` — a senha ficava mascarada só até o
  usuário digitar uma.

- **O `label` de um container era escrito como seu texto.** Qualquer widget com
  prop `label` tinha o `textContent` sobrescrito, então um `FormField` — cujo
  label é metadado, e cujo `Text` filho o core já renderiza — mostrava um segundo
  rótulo sem estilo, em Times New Roman ao lado do rótulo temático. O SSR nunca o
  desenhou, então os dois renderizadores discordavam sobre a mesma árvore. Pior:
  um Update com `label` teria substituído os filhos do campo por aquela string.

- **O artefato do Modo A não bootava.** O timeout de chamada nativa (0.66.0)
  importa `tempestweb.core.constants` em `native/bridges.py`, mas o bundle wasm
  embarca um subconjunto explícito do pacote e `core` não estava nele. Todos os
  testes Python seguiam verdes — o processo de teste tem o pacote inteiro
  instalado — enquanto o artefato morria no browser com
  `No module named 'tempestweb.core'`. Um guard novo caminha pelos arquivos
  embarcados e exige que todo import de nível de módulo `tempestweb.X` nomeie uma
  parte que também está embarcada.

- **Nenhum artefato tinha ícone de aba.** Nenhum shell linkava um, então o browser
  pedia `/favicon.ico` a cada carga e todo artefato respondia 404 — console de
  deploy abrindo com um erro que ninguém pode resolver, e aba com ícone em branco.

- **`Menu`, `ActionSheet`, `Popover` e `Tooltip` não desenhavam nada.** As
  escolhas de um menu vivem na prop `items` (lista de dicts no fio) e nenhum
  código as renderizava: o widget saía como caixa vazia, e não havia caminho para
  o `on_select` que ele declara. `Popover` e `Menu` carregam a `key` da própria
  âncora, ignorada. O `message` de um `Tooltip` nunca aparecia.

  Como esses widgets são folhas da IR — nenhum caminho de patch desce neles — o
  renderizador é livre para possuir seu conteúdo: os itens agora são botões
  renderer-owned com `role=menuitem`, e um clique reporta `select` com
  `{value, label}` contra a key do menu, que é o `MenuSelectEvent` que o handler
  declara. Um overlay ancorado é posicionado sob sua âncora no mesmo passo
  pós-layout que repinta canvases, com clamp na viewport para um menu aberto perto
  da borda seguir alcançável. O título do `ActionSheet` é pintado como o do
  `Dialog` (prop, não filho) e ele ganha scrim, porque é modal — `Menu` e
  `Popover` não ganham, porque não são. O `message` do `Tooltip` vira o atributo
  `title` nativo: aparece no hover e no foco por teclado, e leitor de tela já o lê;
  uma bolha própria precisaria de um id para apontar `aria-describedby` e brigaria
  com a do browser.

- **O `on_dismiss` de um overlay modal nunca disparava.** `Dialog` e `BottomSheet`
  declaram o handler e nada no cliente o acionava: com o scrim agora visível, ele
  prometia "clique fora para fechar" e não cumpria, e uma app sem botão próprio
  prendia o usuário. Um clique no scrim — que é o `::before` do host, então o
  clique aterra no host, o que no DOM é exatamente "clicou fora" — e a tecla
  `Escape` agora reportam `dismiss` para o overlay modal do topo. Clique **dentro**
  do overlay não fecha, e `Menu`/`Popover` não entram nesse caminho porque não têm
  scrim. Verificado no Chrome: abrir → clicar no scrim fecha; reabrir → `Escape`
  fecha; clicar no corpo do dialog mantém aberto.

### Fixed — exemplos

- **kanban-board, dashboard-shell, notification-center:** `on_click=lambda c=col:
  ...` é a forma usual de capturar variável de laço em Python e é uma armadilha
  aqui: a lambda passa a **aceitar** um argumento posicional, e o runtime entrega
  o evento tipado a todo handler que aceita um. O evento caía em `c`, então o
  rótulo do kanban lia `New card in [x=None y=None]` em vez do nome da coluna.
  `functools.partial` amarra o valor sem criar parâmetro.
- **data-table:** a coluna de salário ordenava como texto, então `R$ 8.750`
  caía depois de `R$ 20.000`. Célula que lê como número passa a ordenar por valor.
- **admin-console:** a paginação era decorativa — todas as linhas iam para
  `list_page` com `page_count` fixo em 2, então "Próxima" mudava o rótulo e
  deixava as mesmas cinco linhas na tela.
- **theme-switcher:** cada swatch de accent é um `Container` colorido cujo
  `Button` é só a área de clique, mas o botão não tinha `Style` — então o core lhe
  dava a variante filled: uma pílula roxa de 48px dentro de um círculo de 44px.
  Todo swatch aparecia roxo com uma lasca da cor real na borda, num exemplo cujo
  propósito é escolher cor.

### Added

- `SecurityConfig.trusted_proxies` — de quais peers o `X-Forwarded-For` pode ser
  acreditado (`None` ignora o header; `["*"]` confia em qualquer peer).
- `AppSession.resync()` e o tipo de evento reservado `resync` no contrato: o
  cliente que não conseguiu aplicar um batch pede a cena inteira, e a perna SSE
  emite o mesmo reparo quando o gap do `Last-Event-ID` já saiu do buffer.
- `SSETransport.missed_since()` / `last_id`, `RateLimiter.tracked_keys()`,
  `package_digests()` e o `timeout` do `ProxyBridge`.
- `applyPatches(root, patches, onError)` e `Transport.requestResync` no cliente.

- Tipos de evento `drag` / `drop` na tabela de roteamento, entregando o
  `DragEvent` tipado que os widgets já declaravam.
- `client/dom.js` exporta `DRAG_DATA_ATTR`, `DROP_TARGET_ATTR`, `TITLE_ATTR`,
  `ITEM_ATTR`, `ITEM_VALUE_ATTR` e `ANCHOR_ATTR`; `repaintCanvases(root)` redesenha
  os canvases depois do layout e `positionAnchoredOverlays(root)` coloca cada
  overlay ancorado junto da sua âncora.

### Tests

- Os cenários de conformidade eram checados contra um aplicador de referência
  escrito em Python, então o `client/dom.js` — o renderizador que de fato pinta
  todos os modos — nunca era confrontado com os patches do próprio core. Foi por
  aí que o caso `null` passou. Um cenário novo limpa props e um teste em jsdom faz
  o round-trip de **todos** os cenários pelo renderizador real, afirmando que a
  árvore patcheada é igual à construída.
- A perna SSE ganhou testes ponta a ponta contra um servidor de verdade em porta
  efêmera: o `TestClient` síncrono trava a thread num `GET` streaming (era por
  isso que o teste do round-trip estava `skip`) e o transporte ASGI do httpx
  bufferiza um corpo que nunca termina.

- Round-trip de drag/drop em jsdom, camada de overlay (posicionamento + papéis
  ARIA + o `role` default sobrevivendo a `semantics: null`), itens de menu
  desenhados e a seleção chegando ao handler pelos dois lados do fio, máscara de
  senha através de um update que só muda o valor, e o guard de fechamento de
  imports do bundle do Modo A.
- Os três modos foram exercitados num browser real: Modo B (kanban, overlays,
  data-table, admin-console, list_demo, login-form, theme-switcher), Modo A
  (counter sob Pyodide) e Modo C (counter transpilado).
## [0.68.0] — 2026-08-22

Uma lista declarava as duas bordas e nenhuma delas existia na tela.

### Added

- **`on_end_reached` funciona — infinite scroll de verdade.** `LazyColumn`,
  `LazyRow`, `LazyGrid` e `SectionList` declaram o handler desde sempre, e
  nenhum dos três modos jamais o chamava: ninguém detectava o fim da lista.
  O novo `client/lists.js` mede o progresso de scroll de toda lista marcada
  com `data-tw-end-threshold` (o `end_reached_threshold` do core, default
  `0.8`) e reporta `end_reached` uma vez por travessia, destravando quando a
  lista volta para trás do limiar.

  Duas geometrias contam, porque as duas existem na web: o viewport com
  altura própria (progresso sobre `scrollHeight`, que numa lista virtualizada
  já inclui o espaço reservado fora da janela, e portanto acompanha o
  `item_count` real) e a lista que corre na página, como um `SectionList`
  (progresso sobre quanto da caixa o viewport revelou).

  A detecção é só por scroll, nunca depois de um batch de patches: o handler
  típico acrescenta itens, e reavaliar ali dispararia de novo na lista maior
  — crescimento infinito sem o usuário mover um dedo.

- **`on_refresh` funciona — pull-to-refresh, o gesto que o browser não tem.**
  Reconhecido a partir de pointer events: arrasto ao longo do eixo do widget
  (`data-tw-refresh` = `y`/`x`, então num `LazyRow` o pull é para a direita),
  começando na origem do scroll — fora dela o arrasto é scroll, não pull — e
  mais longo no eixo do que atravessado. Passar de 64px arma o pull; soltar
  armado reporta `refresh`. Widget que a app marcou como `refreshing` é
  ignorado, então segurar a lista embaixo não enfileira um segundo reload.

  O estado é visível, porque gesto sem affordance é gesto que ninguém
  descobre: o tema base desenha uma faixa `inset` na borda do pull enquanto
  armado e enquanto a app recarrega, `refreshing` também vira `aria-busy`, e
  um `RefreshControl` — folha da IR que saía como div vazia — ganhou o
  spinner que o renderizador possui.

### Fixed

- **O spacer da lista virtualizada era encolhido pelo flex.** A barra de
  rolagem descrevia só a janela materializada, nunca o `item_count` — o
  contrário do que o `virtualize.js` promete. Um viewport lazy é
  `display:flex; flex-direction:column`, então os pseudo-elementos de spacer
  são flex items e o browser os encolhia até caberem. Medido num Chrome real
  no `examples/list_demo`: 200 itens, janela de 30, `::after` reservando
  5950px e `scrollHeight` de 1050px. Com `flex:0 0 auto` nas regras geradas,
  o mesmo cenário mede 7000px (200 × 35px) com 30 nós no DOM.

  Foi o `end_reached` que expôs isso: ele mede progresso sobre o
  `scrollHeight`, então com o spacer encolhido disparava sobre a extensão da
  janela em vez da lista inteira — três páginas carregadas por tick de roda.

### Changed

- **`examples/list_demo`** passou a demonstrar as três coisas ao mesmo tempo:
  janela virtualizada, infinite scroll até esgotar a fonte e pull-to-refresh
  com handler `async`, para o estado `refreshing` ser observável.

### Docs

- **Nova página de tutorial bilíngue "Listas longas" / "Long lists"**
  (`docs/tutorial/lists.md`): virtualização, `on_end_reached` com condição de
  parada, `on_refresh` + `refreshing`, `RefreshControl` avulso e como o
  cliente mede o fim em cada geometria.

## [0.67.0] — 2026-08-21

### Changed

- **Piso `tempest-core>=0.12.0`**, onde o tema do `App` finalmente alcança os
  componentes que a view constrói. As duas metades que a 0.66.0 entregou —
  `theme_css` na página e `theme=` até o `App` — só pintam de verdade com
  esse terceiro pedaço: o core instala o tema num `ContextVar` em volta da
  chamada da view, e os campos `theme` dos componentes passam a nascer com
  ele em vez de um baseline novo em folha.

  Sem a 0.12.0, um app com paleta própria ainda desenhava botões roxos
  sobre fundo rebrandeado — medido: `--tw-primary` ardósia no `:root` e o
  botão computando `rgb(88, 71, 133)`.

## [0.66.0] — 2026-08-21

Um app podia montar a própria paleta e não tinha como usá-la.

### Added

- **`tempestweb.html.theme_css(theme)`** — o tema de um app como as custom
  properties `--tw-*` que a folha base lê. A folha sempre disse que um app
  retematiza sobrescrevendo esses tokens, e nada os emitia: quem montava
  uma paleta com `Theme.from_seed` — 39 papéis Material 3, claro e escuro —
  não tinha como levá-la à página, então todo app tempestweb shippava o
  roxo baseline. Modo escuro vem junto e vem honesto: tema em `SYSTEM` emite
  o esquema claro no `:root` e o escuro em
  `@media (prefers-color-scheme: dark)`; tema fixado emite um só e nenhuma
  media query.

- **`theme=` em `create_app`, `TempestWebServer` e `AppSession`** — a outra
  metade, e a que o CSS não alcança. Componentes resolvem cor em **Python**:
  um botão preenchido carrega o fill como estilo inline, resolvido contra o
  tema com que o `App` foi construído. Como a sessão não recebia nenhum, a
  página rebrandeada continuava com botões roxos sobre fundo novo. Medido
  num app real antes e depois.

### Changed

- Tokens de status (`--tw-success`, `--tw-warning`, `--tw-info`,
  `--tw-neutral`) agora saem também do tema do app, e não só dos valores
  fixos da folha.


## [0.65.0] — 2026-08-21

Um widget que existia na árvore e não existia na tela.

### Fixed

- **`ProgressBar` e `Spinner` agora são desenhados.** Os dois estão no
  `tempest-core` e sempre atravessaram a IR corretamente, mas o renderizador do
  DOM não tinha entrada para eles em `TAG_BY_TYPE`: caíam no `div` genérico do
  fallback, sem trilho, sem preenchimento, sem altura. Medido num app real
  (Mode B, Chrome DevTools) antes da correção:

  ```html
  <div data-tw-type="ProgressBar" data-tw-key="job-bar-0"></div>
  <!-- width: 397px · height: 0 · children: 0 · background: transparent -->
  ```

  O texto ao lado dizia "65%" e a barra não estava lá. É o pior modo de falha
  disponível: a árvore afirma que o app está mostrando progresso, o teste que
  conta nós de `ProgressBar` passa, e o usuário não vê nada.

  Agora `client/dom.js` monta o trilho com um elemento de preenchimento próprio
  (renderer-owned, como o `input` dentro do `Checkbox`), escreve a família de cor
  em `data-tw-scheme` e mantém o trio ARIA — `role="progressbar"`,
  `aria-valuemin`/`aria-valuemax`, e `aria-valuenow` **só** quando há valor a
  reportar; uma barra indeterminada que afirmasse um número seria lida como
  progresso medido. Um patch `Update` reposiciona o preenchimento sem
  reconstruir o elemento, que é o caminho de toda barra que anda.

  A folha base (`client/theme.js`) desenha os dois e ganha os tokens das famílias
  de status que faltavam (`--tw-success`, `--tw-warning`, `--tw-info`,
  `--tw-neutral`), então um rebrand por token alcança as barras como alcança o
  resto. Sob `prefers-reduced-motion: reduce` a animação para e a barra
  indeterminada vira faixa estática.

  No SSR (`tempestweb.html.render_to_html`) a escolha é outra e está documentada:
  aquela saída não embarca folha de estilo nenhuma, só um reset, então os dois
  widgets saem com estilo inline autossuficiente — trilho translúcido,
  preenchimento em `currentColor` — e uma página estática mostra progresso sem
  depender de CSS do consumidor.

### Added

- Tokens `--tw-success`, `--tw-warning`, `--tw-info` e `--tw-neutral` na folha
  base, completando o vocabulário de `color_scheme` que o core já validava.

## [0.64.0] — 2026-08-15

Four reported defects, three of them silent and one of them the reason another
looked unexplainable.

### Added

- **`tempestweb.runtime.spawn` — hand long work out of a handler.** A session
  dispatches events **in series**, so a handler that takes its time takes the
  whole application with it for that user: no button responds, no field takes
  text, and even a "Cancel" queues behind the work it is meant to interrupt.
  `spawn(coro)` schedules the work as a task the session owns — held so the loop
  cannot collect it mid-flight, cancelled when the connection ends — and returns
  the handler immediately. Available in Mode A and Mode B. The serial behaviour
  was undocumented until now, which is what made it discoverable only by
  symptom; the handler guide says it plainly ("Trabalho longo: o dispatch é
  serial"). Part of #62.
- **`concurrent_dispatch=True` on `create_app`/`AppSession`.** Opt-in: each event
  becomes its own task, ordered per widget `key` (a per-key lock, so two quick
  edits of one field cannot land out of order) and overlapping across keys. A
  handler that raises is logged rather than ending the connection. Off by
  default — it allows concurrent state mutation, which an app must be written
  for. Closes #62.

### Fixed

- **`file.pick` settles when the dialog is dismissed.** Closing the picker with
  the X or Esc fires `cancel`, never `change`, and only `change` was handled: the
  promise stayed pending, so in Mode B the `native_call` never returned, the
  handler stayed parked on its `await`, and — dispatch being serial — the whole
  app went dead until a reload, with no browser error and no server log line.
  Each cancelled attempt also leaked an orphan `<input type="file">`. Both exits
  now settle and detach the input; the `change`-with-no-file branch stays for
  browsers older than the `cancel` event. Closes #61.
- **Component keys are derived from the caller's key.** `TextField` pinned its
  inner `Input` to `key="text-field-input"`, and the same literal pattern ran
  through `EmailField`, `PasswordField`, the shared label/error wrapper and both
  forms. Keys are how the event router finds the handler that fired, so two
  fields of the same kind on one screen were indistinguishable and an edit could
  apply to the wrong field — found on a 137-field screen of monetary values.
  Without a caller key the previously documented keys are unchanged. Closes #63.
- **The wheel ships `py.typed`.** The package is fully annotated but never
  declared it, so under PEP 561 mypy treated every symbol as `Any` in the
  consuming app — checking vanished exactly where apps err most, assembling the
  widget tree. Closes #64.

## [0.63.0] — 2026-08-15

### Added

- **`tempestweb.presets` — ready-made screens for panels and internal tools.**
  `admin_shell`, `dashboard_page`, `list_page`, `form_page`/`settings_page` and
  `auth_page`, each taking typed records (`NavItem`, `Kpi`, `Section`,
  `TableColumn`, `FormField`, `FormSection`) instead of an assembled widget
  tree. The dashboard example in this repo spends 716 lines building that chrome
  by hand; the same screens are now a description. New guide: "Telas prontas
  (presets)" / "Ready-made screens (presets)", and a runnable
  `examples/admin-console`.
- **`client/layouts.js` — the responsive stylesheet behind them.** Injected once
  at mount (right after the base theme), it supplies what inline `Style` cannot
  express at all: the sidebar collapsing to an overlay drawer with a scrim under
  1024px, KPI and section grids reflowing by available width, a table scrolling
  sideways under a sticky header with zebra rows, forms dropping to one column
  on a phone, a print mode without the chrome, and `prefers-reduced-motion`
  support. Until now the client fed no `MediaQueryData` and inline style has no
  media query, so **every** hand-built layout was fixed-width by construction.
  Presets tag their containers with `data-tw-layout` (a closed vocabulary in
  `presets/roles.py`, guarded against drift by tests) for the sheet to find.
  Tunable through `--tw-layout-*` custom properties; nothing uses `!important`,
  so an app's inline `Style` still wins.

### Fixed

- **The core's `attrs` escape hatch now works in the DOM renderer.** Every widget
  carries an `attrs` dict and the SSR renderer has always emitted it, but
  `client/dom.js` dropped it — the same tree gained `id`/`class`/`data-*` when
  server-rendered and lost them in Modes A, B and C. Attributes are applied on
  build and on update (keys removed from the dict are removed from the element),
  names are validated as in SSR but an invalid one is skipped with a warning
  rather than throwing mid-render, and the renderer's own attributes are never
  overwritten.

## [0.62.0] — 2026-08-15

Fallout from auditing the codebase after #60, whose shape — a bridge shipped but
never wired — repeated in the mirror mode.

### Fixed

- **Mode A: the native event channel is now wired.** `wasm_main.bootstrap()`
  built its `FFIBridge` from the single-shot dispatch alone and never received
  the streaming pair, so **every** `watch()`/`listen()` in Mode A raised
  `BrowserUnavailableError: mode A native event channel is not wired` —
  `geolocation.watch`, `network.watch`, `battery.watch`, `sensors.motion`,
  `sensors.orientation`, `speech.listen`, `nfc.scan`, `idle.watch`,
  `gamepad.watch`, `midi.messages`, `tabs.receive`, `visibility.watch`,
  `orientation.watch`, `sync.watch` — while the docs promised parity with Mode B
  and `installNativeBridge` had already put `__tempestweb_native_subscribe__` on
  the page. `bootstrap()` takes `subscribe`/`unsubscribe` and the generated
  `bootstrap.js` passes them. The glue **copies** the `emit` PyProxy before
  handing it to the browser and destroys the copy on unsubscribe: the proxy
  Pyodide passes into an async call is borrowed, so a subscription that emits
  later hit "This borrowed proxy was automatically destroyed" on its first
  event. An app built with an earlier version needs a rebuild — the wiring lives
  in the generated `bootstrap.js`.
- **`max_message_bytes` is enforced while the body is read.** The gate consulted
  `Content-Length` only, so a `POST /sse/{id}` sent with `Transfer-Encoding:
  chunked` — which declares no length — skipped the limit entirely and had its
  whole body read into memory. The cheap header pre-check remains; the running
  total is now checked per chunk and the read aborts at the limit.

- **`pushsubscriptionchange` no longer reports a failed re-POST as success.** The
  handler discarded the result of the POST that hands the server the fresh
  subscription, so the `PUSH_RESUBSCRIBED` message said `ok: true` even when the
  server rejected it or the network was down — leaving the server pushing to a
  dead endpoint while the page believed it was synced. The message now carries
  `synced` alongside `ok`: `ok` is "the browser gave us a subscription",
  `synced` is "the server accepted it".
- **Mode A patch batches can no longer be garbage-collected mid-flight.**
  `WasmRuntime._apply_patches` scheduled the async send with
  `asyncio.ensure_future` and kept no reference; the loop holds only a weak one,
  so a batch could be collected before it reached the client and the DOM would
  silently miss that update. Pending sends are retained until they settle, the
  pattern `runtime/session.py` already used.
- **The server artifact now ships the SSE client too.** `create_app` answers on
  `/ws` **and** `/sse` + `/sse/{id}`, but `tempestweb build --mode server` only
  copied `transport-ws.js` — infrastructure that blocks WebSocket had a live SSE
  endpoint and no client to reach it with, short of copying the file out of the
  installed package by hand. Both transports ship under `static/` now; the
  generated shell still mounts the WebSocket one, and swapping in an SSE shell
  is a documented four-line change (see "Deploy → Infra que bloqueia
  WebSocket?").
- **SSE: events raised before the stream opens are no longer lost.** The server
  materialises a session while handling the `GET /sse` that opens the stream, so
  any envelope POSTed before that — the router's initial `navigate`, or a click
  on a pre-rendered control — hit `POST /sse/<id>` on an unknown id and was
  answered `404`. In a routed app the server never learned the initial path.
  `sendEvent` now buffers until `open` (and again across a reconnect, since the
  browser's `EventSource` re-fires it), capped at 1000 envelopes with
  drop-oldest, mirroring the WebSocket outbox. `native_result` frames stay
  unbuffered: they can only follow a `native_call` on an already-open stream.
- **SSE: a rejected POST is logged instead of swallowed.** The client-to-server
  leg ignored the response entirely, so a `404` (unknown session), `401`
  (unauthorized) or `413` (oversized body) dropped the envelope with no trace on
  either side. It now warns on the console with the status.

### Added

- **`SecurityConfig.max_events_per_minute`** — a per-IP budget on *inbound
  envelopes*, counted across both legs: an SSE `POST /sse/{id}` over budget
  answers `429`, and a WebSocket frame over budget closes the socket with
  `1013`. Until now only *connections* were rate-limited, so one accepted
  connection could send without bound. A separate knob from
  `max_connections_per_minute` because the magnitudes differ by orders of
  magnitude: one connection per client, but one envelope per interaction.
  Defaults to `None` (unbounded), so no existing deployment changes behaviour.

## [0.61.2] — 2026-08-15

### Fixed

- **Mode B native capabilities now run — the transports wire their own bridge.**
  The Mode B shell mounted the transport with no `onNativeCall`, and both
  `transport-ws.js` and `transport-sse.js` refused every proxied `native_call`
  with `"no native handler"`. The whole native surface was dead in Mode B —
  `file.pick`, `file.save`, `clipboard.*`, `geolocation.get`, `http.*` — and
  silently so: the failure only ever surfaced inside the Python handler's
  `await`, never in the server log. Both transports now fall back to
  `dispatch()` from `native/index.js` — the same registry Mode A runs, and the
  one `native_subscribe` already used — so a plain shell inherits the whole
  native surface with no wiring. `onNativeCall` stays as an explicit override
  (mock in tests, gate behind a confirmation, route elsewhere). The
  `dispatch()` envelope is forwarded verbatim, so a Mode B failure now reports
  the same `error` code and `message` detail Mode A does instead of a
  stringified message. Fixes #60. Regression tests in
  `tests/client/transport-ws.test.js`, `tests/client/transport-sse.test.js` and
  `tests/unit/test_cli_build.py::test_server_artifact_wires_the_native_bridge`
  (the existing artifact test asserted the native files were shipped, which they
  were — unused).
- **`tempestweb gen api` no longer breaks `ruff check`.** Its summary `print()`
  in `cli/main.py` was 102 columns, failing the repo's own lint gate.

## [0.61.1] — 2026-07-19

### Fixed

- **Root `Replace` now re-tracks the mounted tree.** When a patch batch replaced
  the whole tree at path `[]` (e.g. swapping a login screen for a dashboard, or
  any view whose root widget/type changes), `mount()` kept its reference to the
  now-detached old root element. Every subsequent patch then resolved against the
  stale subtree and threw `RangeError: patch path out of range`, silently
  dropping all post-swap updates in Mode A. `mount()` now follows the root swap
  (`applyTreePatches`), so live in-place updates after a root replace apply
  correctly. Regression test in `tests/client/root-replace.test.js`.

## [0.61.0] — 2026-07-18

### Added

- **`tempestweb gen api` — generate a typed client from OpenAPI.** Reads an
  OpenAPI 3.x document (a FastAPI `/openapi.json` URL or a file) and emits, per
  route-group tag, a package with `@dataclass` models (`schemas.py`, each with a
  `from_dict`; enums become `Literal[...]` aliases) and a service class
  (`service.py`, one async method per route) that calls `native.http.request`,
  raising `ApiError` on non-2xx. A shared `_runtime.py` (`ApiError`,
  `encode_query`) and re-export `__init__.py`s complete the client. Models are
  dataclasses (not pydantic) so the client runs in all three modes, transpile
  included. The Python analog of `tempest-react-sdk`'s `tempest gen api`. See the
  new "Generate a client from OpenAPI" guide. Usage:
  `tempestweb gen api http://127.0.0.1:8000/openapi.json --out api`.

## [0.60.0] — 2026-07-17

### Added

- **`native.sync` capability.** Drive and observe read-side sync from a `view()`
  (like `native.network` for connectivity): `configure` a named source (endpoint
  + local table, convention `GET <url>?since=&cursor=` → `{rows, next_cursor,
  server_time}`), `now()` runs a single-flight replay-then-pull, `status()` /
  `watch()` read/stream the observable `SyncState`. Configuring a source
  auto-wires the SW bridge, so an `OFFLINE_PULL` posted after a background drain
  reconciles every configured source with the page's token. Wires the 0.58.0
  read-sync libs (pull / sync-status / sw-bridge) into a first-class surface; the
  write queue is shared with `native.offline`.
- **`pushsubscriptionchange` auto-resubscribe.** The service worker now handles
  subscription rotation/expiry: it re-subscribes with the old subscription's own
  `applicationServerKey` (or uses `event.newSubscription`) and re-POSTs to the
  server subscribe endpoint (default `/webpush/subscribe`), then pings clients —
  so a VAPID rotation no longer silently breaks push. No VAPID key needs to be
  stored or build-injected.

## [0.59.0] — 2026-07-17

### Added

Richer install UX, adopted from famachapp-pwa (completes the offline-first
adoption):

- **Install-method classification.** `InstallState.method` (`native` | `ios` |
  `manual`), surfaced through `native.install`, so a view shows a native prompt
  button on Chromium and a Share → "Add to Home" tutorial on iOS instead of a
  dead button. Adds `isIOS()` / `installMethod()`.
- **Decline cooldown.** `recordInstallDecline()` / `canPromptInstall()` (7-day
  default, localStorage-backed) so the install banner doesn't nag.
- **Post-install redirect.** `client/pwa/post-install-redirect.js`
  (`mountPostInstallRedirect`) — a full-screen overlay shown on `appinstalled`
  that best-effort closes the install tab; opt-in and a no-op when already
  standalone.

## [0.58.0] — 2026-07-17

### Added

Offline-first patterns adopted from the famachapp-pwa / tempest-react-sdk sync
engine, ported to the pure-JS client:

- **Read-side delta-sync (pull).** `client/offline/pull.js`: `createPull`
  (watermark + cursor pagination + single-flight) walks remote changes and
  advances the watermark only after a full drain; `createWatermark` (localStorage
  + in-memory fallback); `mergeRemoteInto` (last-write-wins with tombstone deletes
  and a guard that keeps a locally-pending newer edit). Closes the "no read path"
  gap — the queue could only push.
- **Sync-status store + controller.** `client/offline/sync-status.js`:
  `createSyncStatus` (observable phase/online/pending/lastSyncedAt/summary/error)
  + `createSyncController` (single-flight `syncNow` = replay then pull, flush on
  boot + reconnect).
- **SW→page bridge.** `client/offline/sw-bridge.js`: `installSyncBridge` routes
  service-worker messages (`OFFLINE_PULL`, `OFFLINE_QUEUE_DRAINED`,
  `REPLAY_OFFLINE_QUEUE`) to page handlers; the SW now also posts `OFFLINE_PULL`
  after a background drain so the page (which holds the token) reconciles reads.
- **Large-binary asset cache.** `client/offline/asset-cache.js`: `ensureCached`
  (download once, in-flight dedup, cache-first) + `syncAssets` (version-manifest
  refresh returning `{refreshed}` for the warmup/reset-session pattern) over a
  dedicated Cache Storage bucket — for ONNX models, wasm, datasets.
- **Push self-notification suppression.** `WebPushClient.subscribe()` records the
  active endpoint (`getActivePushEndpoint`); the offline queue stamps
  `X-Push-Endpoint` on every mutation so the server skips notifying the device
  that made the change.
- **Manifest `launch_handler` + `display_override`.** Both emitters default to
  `launch_handler: {client_mode: ["focus-existing","auto"]}` (reuse an open
  window) and `display_override: [display, "minimal-ui"]`.

## [0.57.0] — 2026-07-17

### Added

- **The connectivity banner is auto-mounted in every shell.** The offline/online
  banner shipped as a module in 0.56.0 but nothing mounted it; now the wasm,
  server and transpile index shells import and call `mountConnectivityBanner()`,
  copy the module into every artifact, and precache it (wasm + transpile). Built
  apps show the offline banner without any app code.

### Fixed

- **Connectivity banner is truly idempotent per document.** A second
  `mountConnectivityBanner()` on the same document is now a no-op (a per-document
  guard), and `render()` reads the DOM as the source of truth — so a double mount
  no longer attaches a second network watcher or produces a duplicate banner.
- **The WebSocket transport no longer replays stale connection-scoped frames.**
  Only user `event` envelopes are buffered while offline; `native_result`
  (call_id) and `native_event` (sub_id) frames are dropped rather than flushed
  onto the fresh post-reconnect connection, where their ids no longer exist.
- **WS reconnect hardened.** `scheduleReconnect` is a no-op when a reconnect is
  already pending (a stray extra `close` can't spawn two competing sockets), and
  `connect()` detaches the previous socket's listeners before opening the new one
  (a discarded socket can't re-fire `close`).

## [0.56.0] — 2026-07-17

### Added

- **WebSocket transport auto-reconnects (Mode B resilience).** A dropped
  connection no longer kills the app: the socket reconnects with exponential
  backoff + jitter, outbound envelopes are buffered while offline and flushed on
  reopen (capped, oldest dropped + logged), and an `onReconnect` hook fires on
  each resumed connection. `{reconnect: false}` restores the old single-shot
  behavior. `backoffDelay` is exported.
- **Offline queue dead-letter + conflict lanes.** A replay failure is now
  classified: a permanent client error (non-retryable `4xx`) is dead-lettered
  immediately, a transient failure retries to a ceiling then dead-letters, and a
  `409` moves to a conflict lane — so one poison message can no longer wedge the
  queue. New surface: `native.offline.failed()` / `native.offline.conflicts()`,
  and `ReplayResult.failed` / `ReplayResult.conflicts`.
- **Service worker drains the offline queue with the tab closed.** On `sync`
  (auto-registered) and `periodicsync` (app opt-in via `native.bgsync`), the
  worker drains IndexedDB directly, replaying every owner with the shared policy;
  it falls back to a client-replay message when the queue modules are
  unreachable.
- **Offline navigation fallback.** A navigation with no cached route falls back
  to the cached app shell (then a minimal offline document), so an offline SPA
  navigation boots and routes instead of showing the browser error page.
- **Connectivity banner.** A shell-level offline/online banner
  (`client/pwa/connectivity-banner.js`, `mountConnectivityBanner`) shows while
  offline and clears when connectivity returns, reflecting the core's
  `ConnectivityEvent`.

### Fixed

- **Service worker never caches error/opaque/`no-store` responses**, so a
  transient `404`/`500` can no longer poison the cache and be served as a valid
  asset for the cache's lifetime.
- **Runtime cache is capped** (insertion-order eviction) so
  stale-while-revalidate can't grow it without bound.
- **The offline queue requests durable storage** (`navigator.storage.persist()`)
  when it is built, so it is not evicted under disk pressure.

## [0.55.1] — 2026-07-12

### Fixed

- **`tempestweb dev` survives a transient rebuild IO error.** The rebuild
  callbacks caught only `BuildError`, so an `OSError` from the clean/copy could
  tear the whole watch loop down; they now keep the last good build serving.
- **`tempestweb deploy --replicas N` generates a runnable compose.** The nginx
  upstream listed `app1`, `app2`, … but the compose only defined `app`, so those
  hosts never resolved. The compose now defines one service per replica.
- **`render_initial_tree` wraps a `make_state()` crash** as `ProjectLoadError`
  (it ran outside the try before), matching its documented contract.
- `tempestweb sync` normalizes its framework-exclusion names; `tempestweb check`
  echoes the real resolved argv (e.g. `uv run ruff …`).

## [0.55.0] — 2026-07-12

### Added

- **Query and route params round-trip through the URL, in all three modes.**
  A `Route`'s `params` now serialize to the URL (`app.push(Route("/shop",
  params={"ref": "home"}))` → `/shop?ref=home`) and survive a reload or deep
  link; the query string arriving from the browser is parsed back into the top
  route's `params`. New `tempestweb.runtime.routing` helpers: `route_to_path`,
  `path_to_routes`, and `match_path("/users/:id", "/users/42")` for path-param
  extraction. Wired through the Mode A/B Python runtimes and mirrored in the
  Mode C transpile client (`nav.js`/`runtime.js`); `client/router.js` now reports
  `pathname + search`. Query/path values are strings (richer typing is the app's
  job). Closes the routing gaps flagged in the 0.54 audit.

## [0.54.0] — 2026-07-12

### Added

- **Computer-vision task classes (`tempestweb[vision]`).** `Classifier`,
  `Detector` and `Segmenter` with the same input/output contract as
  `ort-vision-sdk` and `tempest-fastapi-sdk`'s vision layer, but running the model
  over the `native.onnx` bridge (onnxruntime-web) so they work in the browser
  where the `onnxruntime` wheel does not exist. `await Task.create(model_url,
  labels=...)` then `await task.predict(image)` returns ort-vision-sdk's
  Ultralytics-style Results (`.boxes`/`.probs`/`.masks`); `to_detection_schemas` /
  `to_classification_schema` / `to_segmentation_schemas` map them to the same JSON
  wire shape a `tempest-fastapi-sdk` endpoint speaks. The extra pulls
  `ort-vision-sdk` + `numpy`.
- **`tempestweb new .`** scaffolds into the current directory (named after it)
  instead of a literal `"."` subdir, tolerating unrelated files but refusing to
  clobber existing scaffold files without `--force`.

### Changed

- **`dev`/`build`/`run` honor `[dev].mode` from `tempestweb.toml`** when `--mode`
  is omitted (the argparse default was hard-wired to `wasm`, so a `transpile`/pwa
  project silently built a wasm artifact). An explicit `--mode` still overrides.
- The mypy target is now 3.12 (numpy 2.x's stubs use 3.12 syntax); the package
  still runs on 3.11+.

### Fixed

- **Incomplete wasm service-worker precache** left eager-boot modules
  (`client/icons/*`, `push/web-push-client.js`, `pwa/install-prompt.js`, PWA
  icons) out of the precache, so an `--offline` build could fail to boot with no
  network. The wasm precache now mirrors the transpile one.

### Docs

- New pages: "Routing & navigation", "Computer vision (ONNX)", "Offline + backend
  sync". A transparent component catalog (tempestweb-native vs re-exported
  `tempest_core.components`, by group) with links to the `tempest-core` package.
  Plus consistency fixes (real command output, `sync`/`deploy` descriptions,
  version snippets).

## [0.53.2] — 2026-07-12

### Fixed

- **`tempestweb dev` no longer serves a stale cache.** The wasm/transpile PWA
  registers a cache-first service worker; after upgrading, a previously-installed
  worker kept serving old assets in the dev loop, so the browser 404'd on modules
  the fresh build actually ships (and required a manual "unregister service
  worker + clear site data" to recover). Dev builds now **skip the caching
  service worker** and inject a cache kill-switch that unregisters any existing
  worker, clears all caches, and reloads once if a worker was controlling the
  page — so every `dev` reload serves the freshly rebuilt bundle. Production
  builds (`run` / `build` / `deploy`) are unchanged and keep the caching service
  worker for fast repeat loads.

## [0.53.1] — 2026-07-12

### Fixed

- **Blank page in server (and wasm) mode — the app never mounted.** The client's
  `native/index.js` (imported by both the WebSocket transport and the wasm
  bootstrap) eagerly loads the whole native-capability tree, but the build's
  `_NATIVE_ASSETS` list had gone stale — it copied only 15 of the 43 modules
  `index.js` imports, and the **server** artifact never copied the native tree at
  all. The browser 404'd mid-module-load, so `mount()` never ran and `#app`
  stayed empty. Now every artifact ships the full native closure (native tree +
  offline queue + WebPush client + install prompt) under its client base
  (`client/` for wasm, `static/` for server), the asset list is complete and
  guarded by a test that checks it against `index.js`'s imports, and a new test
  asserts the built server artifact actually contains the closure on disk.
- **Noisy `/favicon.ico` 404** in server mode: the FastAPI host now answers the
  browser's default favicon probe with `204 No Content`.

## [0.53.0] — 2026-07-11

### Added

- **Seven code-quality CLI commands**, each shelling out to the project's own
  `ruff`/`mypy`/`pytest` (preferring the binary on `PATH`, falling back to
  `uv run <tool>`), scoped to the project via `--path`:
  - `tempestweb lint` — `ruff check` (report only).
  - `tempestweb fix` — `ruff check --fix` + `ruff format` (writes); `--unsafe`
    also applies ruff's unsafe autofixes.
  - `tempestweb format` — `ruff format` (writes).
  - `tempestweb fmt-check` — `ruff format --check` (read-only).
  - `tempestweb type` — `mypy`.
  - `tempestweb test` — `pytest`, filtered by `--path`.
  - `tempestweb check` — the full gate: `ruff check` → `ruff format --check` →
    `mypy` → `pytest`, stopping at the first error.
- **Configurable `[quality] typing_strictness`** in `tempestweb.toml`
  (`lenient` | `standard` | `strict`, default `standard`), overridable per
  invocation with `--strictness`. It is a layer of opinion **on top of** the
  user's own ruff/mypy config — it only adds rules, never loosens them:
  - `lenient` — no extra ANN rules, no extra mypy flag.
  - `standard` — ruff `--extend-select ANN001,ANN201,ANN202,ANN205,ANN206`; mypy
    `--ignore-missing-imports`.
  - `strict` — ruff `ANN001,ANN002,ANN003,ANN201,ANN202,ANN204,ANN205,ANN206`;
    mypy `--strict`.
  - **`ANN401` (ban `Any`) is never enabled** — `Any` is a valid annotation.
- **`tempestweb test` treats pytest exit code 5 ("no tests collected") as
  success**, so the gate does not break on a project without tests yet.
- **`tempestweb new` now scaffolds the `[quality] typing_strictness = "standard"`
  block** in the generated `tempestweb.toml`.
- **Code-quality documentation** — new "Code quality" section in the "Using the
  CLI" page (`docs/cli.md` + `docs/cli.en.md`) covering the seven commands, the
  three strictness levels, and the `tempestweb.toml [quality]` block; new rows in
  the installation CLI table; a README "Code quality" block.

## [0.52.0] — 2026-07-11

### Changed

- **`tempestweb dev` now serves all three modes with watch + reload**, becoming the
  single command for local development. Previously `dev` only served the static
  modes (`wasm`, `transpile`) while Mode B lived under `run`. Now:
  - `tempestweb dev --mode wasm` (default) — Mode A with browser live-reload.
  - `tempestweb dev --mode server` — Mode B (FastAPI + uvicorn), automatically
    rebuilding and restarting the server on every edit.
  - `tempestweb dev --mode transpile` — Mode C with live-reload.
- **`tempestweb run` is now the no-watcher serve command** (production-like): it
  builds once and serves the app as-is, across all three modes, without the dev
  watcher or livereload. It is what the generated deploy Dockerfile runs. Use `dev`
  while developing and `run` to serve as built — neither is deprecated.

### Added

- **Global `-V` / `--version` flag** on the CLI to print the installed version.
- **`--help` epilogue with worked examples** for every subcommand.
- **New "Using the CLI" documentation page** (`docs/cli.md` + `docs/cli.en.md`) —
  a tutorial-first walkthrough of `new`, `dev` (all three modes), `run`, `build`,
  `deploy`, `vapid`, and `sync`, ending with a subcommand reference table.

### Fixed

- **Reload storm in the dev watcher.** The watcher had no exclusion for the build
  output directory, so a rebuild writing into `dist/` retriggered the watcher in an
  endless rebuild/restart loop (one edit could fan out into dozens of restarts).
  `FileWatcher` now takes an `ignore` list and both dev loops exclude the artifact
  output dir, so one edit yields exactly one rebuild.

## [0.51.0] — 2026-07-11

### Added

- **`nfc.scan` — streaming NFC reads (closes the Track T gap).** The Web NFC
  `NDEFReader.scan()` is now exposed as a streaming capability on the event
  channel: `async for msg in nfc.scan(): ...` yields an `NdefMessage`
  (`serial_number` + decoded `records`) per tag read, and exiting the loop aborts
  the scan. Wired across all three surfaces (Python facade + `EVENT_HANDLERS`
  handler + Mode C `stream()` facade) with conformance + unit tests. Track T is
  now complete with no known capability gaps.

## [0.50.0] — 2026-07-11

### Added

- **Web-platform capability parity (Track T).** The `tempestweb.native` bridge now
  wraps the bulk of the modern Web Platform, grouped by tier the way the roadmap
  does:
  - **Tier 1 (universal):** `vibration`, `badge`, `wakelock`, `fullscreen`,
    `network` (+ `watch`), `visibility` (+ `watch`), `orientation` (+ `watch`),
    `quota`, rich `clipboard` (`read_image`/`write_image`), `battery` (`watch`),
    and `sensors` (`orientation`/`motion`).
  - **Tier 2 (widely used):** `speech` (TTS `speak`/`voices` + STT `listen`),
    `recorder` (audio/video/screen), `filesystem` (live handles), `bgsync`
    (Background + Periodic Sync), `tabs` (broadcast/receive + Web Locks), and
    `idle` (`watch`).
  - **Tier 3 (Chromium-only / secure-context):** `bluetooth`, `usb`, `serial`,
    `hid`, `nfc` (`write`), `contacts`, `payment`, `pip`, `eyedropper`,
    `pointerlock`, `gamepad` (state + `watch`), `midi` (send + `messages`), and
    `webaudio` (`tone`). Each ships `is_supported()` + graceful degradation.
- **Native event channel (T-EV) + streaming capabilities.** A typed Python←client
  stream exposed as an async iterator, consumed with `async for`. It extends
  `NativeBridge` with `subscribe`/`event`/`unsubscribe`; leaving the loop (end,
  `break`, cancellation) closes the subscription automatically. Twelve streaming
  capabilities ride it: `geolocation.watch`, `sensors.orientation`,
  `sensors.motion`, `network.watch`, `visibility.watch`, `orientation.watch`,
  `battery.watch`, `speech.listen`, `idle.watch`, `tabs.receive`, `gamepad.watch`,
  and `midi.messages`. See `docs/contract.md` ("Canal de eventos nativo").
- **`examples/device-panel`** — a Tier 1 showcase wiring `vibration`, `wakelock`,
  `fullscreen`, and `network` to buttons; the same `view` runs unchanged in
  Modes A/B.
- **Docs:** bilingual "Native capability reference" (tier-grouped catalog with a
  runnable snippet per group), "Native event channel" tutorial, and a "Device
  panel" gallery page.

### Changed

- **CI now runs with `--all-extras`** so the full native surface (and its optional
  dependencies) is import-tested and exercised in the gate.

### Known gaps

- **`nfc.scan`** (streaming tag reading) is not implemented yet — `nfc.write` and
  `nfc.is_supported()` are done. It is the one remaining Track T gap and will land
  over the event channel (T-EV) in a future release.

## [0.49.0] — 2026-07-11

### Added

- **Redis SSE session backend (Track S — S4 complete).** SSE can now scale
  across instances **without** sticky sessions: `create_app(..., sse_backend=...)`
  takes a `SessionRouter`. The default `InProcessRouter` keeps today's behavior;
  `RedisSessionRouter.from_url("redis://…")` publishes SSE inbound events to a
  per-session Redis channel, and the instance holding the stream (subscribed)
  feeds its transport — so a `POST` landing on any instance is delivered.
  WebSocket is self-contained and needs no backend. `tempestweb deploy
  --no-sticky` generates a round-robin (no `ip_hash`) nginx for a Redis-backed
  deploy. Requires the `[cache]` extra (redis) only when used; the SSE `POST`
  handler now returns `400` on malformed JSON. This closes S4.

## [0.48.0] — 2026-07-11

### Added

- **`tempestweb deploy` — generate deploy files (Track S — S5).** Scaffolds a
  tailored `nginx.conf` (upstream port from `tempestweb.toml`; WebSocket upgrade,
  `X-Forwarded-*`, long streaming timeouts, `ip_hash` stickiness; `--tls` adds a
  443 server block + HTTP→HTTPS redirect; `--replicas N` expands the upstream), a
  `Dockerfile` (with `HEALTHCHECK`), a `docker-compose.yml`, and a `DEPLOY.md`
  guide — into `deploy/` (or `--out`). Flags: `--path`, `--out`, `--server-name`,
  `--tls`, `--replicas`, `--force`. Public API: `render_deploy_files` /
  `scaffold_deploy` from `tempestweb.cli`. 10 tests.

## [0.47.0] — 2026-07-11

### Added

- **Dependabot (Track S — S7 complete).** `.github/dependabot.yml` opens weekly
  update PRs for pip, GitHub Actions and npm. With `SECURITY.md` + the CI
  `pip-audit` job, S7 is closed.

### Changed

- Roadmap: Track S production-readiness state marked **done** for the security +
  deploy core (S0/S1/S2/S3/S5/S6/S7/S11 ✅); the remaining 🔶 (S4 Redis backend,
  S8 OpenTelemetry, S9/S10 CI gates) are enhancements, not blockers — Mode B runs
  in a professional environment today behind the reference nginx with a
  `SecurityConfig`.

## [0.46.0] — 2026-07-11

### Added

- **Per-IP connection rate limiting (Track S — S2 complete).**
  `SecurityConfig.max_connections_per_minute` refuses a connection flood from one
  client IP (rolling 60s window; WS `1013` / SSE `429`), taking the IP from
  `X-Forwarded-For` (first hop) or the peer. New `RateLimiter` helper. This
  closes S2 (cap + payload + rate limit); a dead/half-open WS is already reaped
  by uvicorn's ping, and an app-level idle-timeout is intentionally not enforced
  (it would disconnect legitimately-idle users).

## [0.45.0] — 2026-07-11

### Added

- **Benchmarks (Track S — S9, partial).** `benchmarks/bench_reconcile.py` times
  the `build → diff` hot path (ops/s, µs/op) and confirms minimal patching (a
  single-row change yields 2 patches). A CI regression gate remains a follow-up.
- **Stability & support docs (Track S — S10, S11).** New `docs/stability.md`
  (PT+EN): the pre-1.0 public-surface + deprecation policy, a browser support
  matrix (A/B/C), the accessibility baseline, and the **Mode C subset contract**
  — the stable, fail-loud in/out list (S11), with components staying an open
  decision.

## [0.44.0] — 2026-07-11

### Added

- **Server metrics (Track S — S8, partial).** `create_app(..., metrics=True)`
  mounts `GET /metrics` in Prometheus text format: `tempestweb_sessions_live`
  (gauge), `tempestweb_sessions_opened_total` /
  `tempestweb_connections_rejected_total` (counters), and
  `tempestweb_sessions_max` when a cap is configured. Disabled by default.
  (OpenTelemetry tracing + patch-latency/throughput remain follow-ups.)

## [0.43.0] — 2026-07-11

### Added

- **Deploy & ops (Track S — S4 partial, S5, S7 partial).**
  - **S4** `GET /health` — unauthenticated liveness/readiness probe returning
    `{status, sessions, ready}`; `ready` flips to `false` at `max_connections`
    for load-balancer draining. Horizontal-scale guidance (sticky sessions).
  - **S5** `examples/deploy/` — a production `Dockerfile` (with `HEALTHCHECK`),
    `docker-compose.yml` (app + nginx/TLS) and `nginx.conf` (WebSocket upgrade,
    long streaming timeouts, `ip_hash` stickiness). New `docs/deploy.md` (PT+EN).
  - **S7** root `SECURITY.md` (private reporting + security model) and a
    `pip-audit` job in CI.

## [0.42.0] — 2026-07-11

### Added

- **Mode B limits & security headers (Track S — S2 partial, S6).** `SecurityConfig`
  gains:
  - **S2** `max_connections` — cap on concurrent WS+SSE sessions (a connection
    over the cap is refused: WS `1013` / SSE `503`), and `max_message_bytes` —
    an SSE `POST` body over the limit returns `413`. (Idle-session timeout, a WS
    message cap and per-IP rate limiting remain follow-ups.)
  - **S6** `security_headers` (adds `X-Content-Type-Options: nosniff`,
    `Referrer-Policy`, `X-Frame-Options: DENY`), `hsts`
    (`Strict-Transport-Security`), and `content_security_policy` — applied to
    every HTTP response by a middleware.
- **XSS audit (S6):** confirmed the JS client is safe by construction — zero
  `innerHTML`/HTML-injection sinks anywhere in `client/`; the DOM patcher only
  uses `textContent` + `setAttribute`. Documented in `docs/security.md`.

## [0.41.0] — 2026-07-11

### Added

- **Mode B server security (Track S — S0/S1/S3).** `create_app(...)` gains an
  opt-in `security=SecurityConfig(...)`:
  - **S0 auth gate** — an `authenticate` predicate (sync or async) runs on every
    WebSocket upgrade and SSE request *before* a session is created; a falsy
    return or a raised error rejects the connection (WS close `1008` / HTTP
    `401`). Builders: `token_authenticator(secret)` (shared secret, constant-time,
    empty = disabled) and `jwt_authenticator(key, ...)`.
  - **S1 origin allowlist** — `allowed_origins` installs `CORSMiddleware` for the
    HTTP/SSE surface *and* hard-checks the `Origin` header on the WS upgrade
    (which browser CORS does not guard); `["*"]` allows any origin.
  - **S3 server-side JWT** — `verify_jwt(token, key, ...)` validates signature +
    expiry (needs the `[auth]` extra / PyJWT; degrades to a clean rejection when
    absent), distinct from the client-side `decode_jwt`.

  The host stays fully open when no `SecurityConfig` is passed (dev). New
  `docs/security.md` (PT+EN) documents the surface.

## [0.40.0] — 2026-07-11

### Changed

- **Docs: three execution modes, front and center.** The landing page, the
  "running modes" tutorial and the transpile guide were reframed from two modes
  to three (A WASM · B server · C transpile/native-JS) in the tiangolo style —
  a three-card grid with a "which mode?" decision note, an updated
  "how it works" diagram including the Mode C transpile path, and Mode C
  positioned as a first-class guide in the nav. The README (PyPI front page) now
  presents all three modes consistently (diagram + capabilities + a Mode C
  scaffold pointer) and an accurate, non-stale status. No code changes — the
  package is unchanged; this release ships the corrected README/docs.

## [0.39.0] — 2026-07-11

### Added

- **`tempestweb new --template pwa`** — scaffold an installable, offline Mode C
  PWA in one command. The template pre-configures `tempestweb.toml` with
  `mode = "transpile"` + a `[pwa]` manifest block, and ships an `app.py` with a
  counter and an **Install** button (`native.install`). The default template
  (a two-mode counter) is unchanged; `render_files`/`scaffold_project`/
  `create_project` gain a `template` argument, and an unknown template fails
  loud (`UnknownTemplateError`). Verified: the scaffolded project renders
  through the real core and builds into a full PWA (manifest + service worker +
  transpiled install button).

## [0.38.0] — 2026-07-11

### Added

- **Stdlib method mapping in the transpiler.** Common Python methods now map to
  their JS idioms: string/list renames (`.upper()` → `.toUpperCase()`,
  `.lower`, `.strip`/`.lstrip`/`.rstrip`, `.startswith`/`.endswith`, `.append()`
  → `.push()`), dict views (`.items()` → `Object.entries(d)`, `.keys()`,
  `.values()`), and `sep.join(it)` → `it.join(sep)`. Methods on runtime/facade
  objects (`app.replace(route)`, `native.storage.get(...)`, `ctrl.forward()`)
  pass through unchanged — the map deliberately omits `.replace` and `.get` to
  avoid clashing with them (use subscript `d[k]` for a dict lookup).

## [0.37.0] — 2026-07-11

### Added

- **Wider expression + statement subset in the transpiler:**
  - **Sequence unpacking** — `a, b = pair` (array destructuring), `for k, v in
    items:` and comprehension tuple targets (`[f(k, v) for k, v in items]`).
  - **`enumerate(it)`** → `it.map((v, i) => [i, v])` and **`zip(a, b)`** → paired
    arrays, so tuple-target iteration works idiomatically.
  - **Operators `**` (power) and `//` (floor division → `Math.floor(a / b)`).**
  - **Slices** — `x[a:b]` / `x[a:]` / `x[:b]` → `x.slice(...)` (a step is
    rejected).
  - **`assert cond[, msg]`** → `if (!(cond)) throw` an `AssertionError`.
  - **Chained assignment** `a = b = x`.

  (Chained comparison `a < b < c` was already supported.)

## [0.36.0] — 2026-07-11

### Added

- **`raise` in the transpiler.** `raise Exc("msg")` / `raise Exc` throw an
  `Error` whose `message` is the first argument and whose `name` is the
  exception class — so it round-trips with the multiple-`except` dispatch
  (`except Exc` matches on `err.name`). A bare `raise` inside an `except`
  re-throws the caught error. `raise … from …` and a bare `raise` outside an
  `except` fail loud. This completes the raise/try/except loop in Mode C.

## [0.35.0] — 2026-07-11

### Added

- **Dataclass inheritance in the transpiler.** `@dataclass class B(A):` emits
  `class B extends A` (the base must be another `@dataclass` in the module);
  `super()` chains the base constructor, then the subclass's field defaults are
  assigned (overriding an inherited default when they clash). Multiple bases or
  an unknown base fail loud.
- **`with … as x`.** Transpiled via the context-manager protocol —
  `x = cm.__enter__()` then a `try/finally` whose `finally` calls
  `cm.__exit__(null, null, null)` (faithful for managers exposing those methods,
  e.g. a transpiled dataclass; `async with` awaits both). The `as` target is
  hoisted to a function-scoped `let`, mirroring Python's leak. A single context
  manager; `as` must bind a plain name.
- **Multiple `except` clauses.** A lone `except` still catches everything (type
  informational); multiple clauses dispatch by exception class name
  (`err.name === "ValueError"`, `["A","B"].includes(err.name)`), with a trailing
  broad/`Exception` clause as the `else` — or `throw` to re-raise when none
  matches (Python's selective semantics, preserved for A/B/C parity). Matching is
  by class **name**; a JS/browser error only matches when the names coincide.

### Fixed

- **Dataclass construction with field arguments.** A transpiled dataclass
  constructor now takes an options object and applies overrides
  (`Doubler(n=5)` → `new Doubler({ n: 5 })` sets `n = 5`), falling back to the
  field default when a key is absent — previously the constructor ignored all
  arguments and always used the defaults (a silent divergence from Python).

## [0.34.0] — 2026-07-11

### Added

- **Control-flow statements in the transpiler:** `while` loops, `break` /
  `continue`, and `try` / `except` / `finally` (a single `except`, binding the
  error to its name or `_err`). `while/else`, `try/else` and multiple `except`
  clauses still fail loud with a located `TranspileError`.

### Fixed

- **`const` vs `let` correctness.** The hoisting analysis now emits `let` for any
  name that is augmented (`+=`), re-bound, or assigned inside a block — only a
  name bound exactly once at the top level stays `const`. This fixes a latent JS
  bug where a `for`/`while` counter (`total = 0; total += x`) emitted
  `const total = 0` followed by `total += x` (assignment to a constant → a
  runtime `TypeError`).

## [0.33.0] — 2026-07-11

### Added

- **WebPush end-to-end (server path).** The last piece to make push work end to
  end:
  - `tempestweb.server.generate_vapid_keys() -> VapidKeys` — a P-256 VAPID
    keypair (base64url); requires the `[webpush]` extra.
  - `tempestweb vapid` CLI — prints a fresh keypair (`--env` prints
    `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` export lines).
  - `tempestweb.server.webpush_router(service, *, owner, prefix)` — a mountable
    FastAPI router exposing `GET /webpush/vapid-public-key`, `POST
    /webpush/subscribe`, `POST /webpush/unsubscribe`, `POST /webpush/send`.
  - `examples/webpush-server/server.py` — a runnable demo: VAPID (env or
    ephemeral dev keypair) + the router + a page and minimal push service worker.
    `uv run uvicorn server:app --app-dir examples/webpush-server`.

  With the client already able to `native.notifications.subscribe(public_key)`
  and POST the subscription, the full loop closes: subscribe → store → send →
  notification. The server path (keygen, router, send with a mocked sender) is
  unit-tested; the browser subscribe/permission + real push delivery are device/
  gesture dependent (manual). Verified live (Playwright): the demo page loads,
  the service worker registers + activates, `PushManager` is available and the
  VAPID public key is served.

## [0.32.0] — 2026-07-10

### Added

- **`native.notifications.push_state()`** — reports WebPush `{supported,
  permission}` WITHOUT prompting, so an app can decide whether to show an
  "enable notifications" button before the gesture-gated `subscribe`. New
  dispatch handler + Python `PushState` model, marked `mode_c`; JS + Python
  tested.
- **Offline-queue demo in `examples/transpile-tour`** — a visible "queue" button
  enqueues a mutation via `native.offline` and shows the live pending count.
  Verified live (Playwright): three clicks drive `queued=3` through real
  IndexedDB, entirely from the transpiled UI.

## [0.31.0] — 2026-07-10

### Added

- **WebPush subscribe/unsubscribe in Mode C (`native.notifications`).** The push
  subscription flow (already in the dispatch registry and Python surface) is now
  exposed on the Mode C facade and marked `mode_c`:
  `await native.notifications.subscribe(vapid_public_key)` runs the browser
  WebPush flow (permission + `pushManager.subscribe`) and returns the raw
  subscription JSON to POST to your own backend (e.g. via `native.http` or queued
  with `native.offline`); `unsubscribe()` cancels it. The framework owns neither
  the endpoint schema nor the push server — it hands back the raw subscription.
  The dispatch handler is already unit-tested; the contract conformance test
  enforces the facade coupling. Verified live (Playwright): in the built app the
  flow reaches `pushManager` (support detected, permission readable) — the
  grant/subscribe step is gesture + push-service dependent and left to manual
  verification. This closes the Mode C PWA capability set (install, offline
  queue, update prompt, push).

## [0.30.0] — 2026-07-10

### Added

- **"New version available" update prompt (Mode C PWA).** When a new service
  worker is deployed, the shell now surfaces an unobtrusive banner ("new version
  available → Reload"); confirming activates the waiting worker (skipWaiting) and
  reloads the page once. New pure-JS `client/pwa/update-prompt.js`
  (`createUpdateBanner` / `showUpdatePrompt`, idempotent, injectable document +
  skipWaiting) wired into the transpile shell via `registerServiceWorker`'s
  `onUpdate`. Lives in the shell (not the app view), so it needs no core App
  change and works without the app cooperating. Verified live (Playwright): in
  the built app the banner renders and its button invokes skipWaiting on the
  waiting registration. jsdom-tested (5 cases).

## [0.29.0] — 2026-07-10

### Added

- **Offline mutation queue in Mode C (`native.offline`).** A new native
  capability exposing the durable, replay-on-reconnect queue (the tested
  `client/offline/{store,sync}.js` over IndexedDB) end to end:
  `await native.offline.enqueue(method, url, body)` records a mutation with an
  idempotency key; `pending()` / `size()` inspect it; `replay()` drains it in
  FIFO order (also wired to the `online` event and Background Sync). The Python
  awaitable surface (`tempestweb.native.offline` — `enqueue`/`pending`/`size`/
  `replay`, `Mutation`/`ReplayResult` models) and the JS dispatch handlers
  (`offline.*`) are marked `mode_c`, and the offline client modules now ship in
  the wasm and transpile artifacts (and join the service-worker precache).
  Verified live (Playwright): in the built app, `enqueue` writes to real
  IndexedDB (FIFO, idempotency key), `size`/`pending` reflect the queue, and
  `replay` performs real `fetch` round-trips, preserving the queue on failure.

## [0.28.0] — 2026-07-10

### Added

- **PWA install prompt in Mode C (`native.install`).** The install capability
  (already present in the dispatch registry and Python surface) is now exposed on
  the Mode C native facade and marked `mode_c`: `await native.install.state()`
  returns `{can_install, installed}` and `await native.install.prompt()` fires the
  browser's stashed `beforeinstallprompt` after a user gesture, resolving to
  `"accepted"` / `"dismissed"` / `"unavailable"`. `examples/transpile-tour` gains
  an "install" button. Verified live (Playwright): the facade round-trips
  end-to-end in the browser (`install.state()` → `{can_install:false,
  installed:false}`; `beforeinstallprompt` captured and `prompt()` fired — the
  accept/dismiss step is gesture-dependent and not automatable).

## [0.27.0] — 2026-07-10

### Added

- **Mode C is a first-class PWA — installable and offline out of the box.**
  `tempestweb build --mode transpile` now emits the full PWA layer alongside the
  static bundle: `manifest.webmanifest`, a cache-first app-shell service worker
  (`sw.js`) whose precache covers the *entire* bundle (index, shared client,
  `client/transpile/*` incl. the generated `app.gen.js`, native tree, icons), its
  registration (`register.js`), and the icon set. The generated `index.html`
  links the manifest, sets `theme-color`/apple-touch-icon and registers the
  worker. Because Mode C is a zero-Python static bundle, it is the ideal PWA
  target. Verified live (Playwright): with the HTTP server killed, reloading the
  built tour still renders and navigates — the app runs fully offline.
- **`[pwa]` config section.** `tempestweb.toml` gains a `[pwa]` table to
  customize the generated manifest — `name`, `short_name`, `description`,
  `theme_color`, `background_color`, `display` (`standalone`/`fullscreen`/
  `minimal-ui`), `orientation`, `lang`, `categories`. All optional; names fall
  back to the project name. The `theme_color` is mirrored into the shell's
  `theme-color` meta. `examples/transpile-tour` now ships a `[pwa]` block.

### Changed

- The wasm (Mode A) `theme-color` meta now follows the `[pwa].theme_color`
  instead of a hard-coded value.

## [0.26.0] — 2026-07-10

### Added

- **More builtins in the transpiler.** `round(x[, n])`, `min`/`max` (variadic or
  over one iterable), `sum(it)`, and `range(...)` — the last materialized to a
  JS array so a comprehension's `.map`/`.filter` chain has something to iterate
  (JS has no lazy range). This closes a correctness gap: comprehensions over
  `range(...)` now actually run in the browser.
- **Richer f-string number formatting.** Beyond `.Nf`: thousands grouping
  (`{x:,}` → `toLocaleString`), grouped fixed-point (`{x:,.2f}`), percent
  (`{x:.1%}`) and integer (`{x:d}`, `{x:,d}`). Unsupported specs (alignment,
  sign, hex/bin, dynamic `{x:.{n}f}`, `!a`) still fail loud with a located
  `TranspileError`.

  Verified live (Playwright): a built app renders `total=1,234,567.89`,
  `ratio=12.6%`, and a `range(1, 5)` comprehension `squares=1,4,9,16 sum=30`,
  zero Python in the browser.

## [0.25.0] — 2026-07-10

### Added

- **Wider transpiler expression subset.** Mode C now transcribes more everyday
  Python:
  - `set` literals → `new Set([...])`; `tuple` literals → JS arrays (JS has no
    tuple type — immutability is not enforced).
  - dict comprehensions (`{k: v for x in it if c}`) →
    `Object.fromEntries(it.filter(...).map((x) => [k, v]))`.
  - f-string formatting: `{x:.2f}` → `(x).toFixed(2)`, `{x!s}` → `String(x)`,
    `{x!r}` → `JSON.stringify(x)`.

  Out-of-subset format specs (alignment `{x:>5}`, dynamic `{x:.{n}f}`, the `!a`
  conversion) and multi-loop/destructured comprehensions still fail loud with a
  located `TranspileError`. Verified live (Playwright): a built app renders
  `pi=3.14` and a dict-comp-derived `squares=9` with zero Python in the browser.

## [0.24.0] — 2026-07-10

### Added

- **Canonical Mode C tour example (`examples/transpile-tour`).** One app that
  exercises the whole app-layer surface at once — state with methods, navigation
  (routes + URL), i18n, theme + responsiveness, a validated form (native
  `validate_email`) and an imperative animation (`AnimationController`/`Tween`).
  Verified live (Playwright): navigation, form validation ("E-mail inválido"),
  theme/lang toggles and the animated box all work with zero Python in the
  browser. Documented as "O tour completo" in the transpile guide (PT + EN).

### Fixed

- **Function-scope hoisting in the transpiler.** A name assigned inside an
  `if`/`for` block (e.g. `body = Column(...)` in a branch) was emitted as a
  block-scoped `const` and became invisible to the rest of the function —
  a runtime `ReferenceError` in JS. Such names now hoist to a single
  function-top `let`; top-level-only names keep their `const`.
- **Fail-loud on out-of-subset constructs.** Variadic/keyword-only parameters,
  function decorators, non-dataclass class decorators and f-string format-specs
  were silently mis-transpiled. Each now raises a located `TranspileError`
  (`file:line`), matching the `mypy --strict` spirit. `field(default=…)` and
  `field(default_factory=list/dict/set)` are now honored.

## [0.23.0] — 2026-07-10

### Added

- **Imperative animation in Mode C (`AnimationController`/`Tween`/`Spring`).**
  Frame-driven animation now works in the transpile mode: `AnimationController`
  drives a normalized value (eased ramp or damped spring) on a
  `requestAnimationFrame` loop the runtime owns, and `Tween` maps it to a float/
  Color/Edge for a `Style`. `client/transpile/animation.js` is a faithful port of
  `tempest_core.animation` (curve math + ramp/spring integration + lerps); the App
  gains `register_animation`/`unregister_animation`/`has_animations`. Verified live
  (Playwright): a box animates width 100→340 over an ease-out ramp and settles.
  **This closes 100% of `tempest_core` coverage in Mode C.**

## [0.22.0] — 2026-07-10

### Added

- **Animation in Mode C (declarative transitions) — core coverage closed.** Give
  a widget's `Style` a `Transition` and the browser tweens it when a styled field
  changes (width/color/opacity) — no Python runtime, no frame driver.
  `client/transpile/motion.js` ports `tempest_core.style`'s `Transition` + `Curve`
  (linear/ease/ease-in/out/in-out/bounce/elastic); `Color` joins the Style-value
  helpers. Verified live (Playwright): a box animates width 120→320px over a
  400ms CSS transition. This closes `tempest_core` coverage in Mode C — widgets,
  layout components, native (10 capabilities), validators, navigation, i18n,
  theme + responsiveness, and animation. The imperative, frame-driven
  `AnimationController` remains the one advanced piece (declarative transitions
  cover the canonical case).

## [0.21.0] — 2026-07-10

### Added

- **Theme + responsiveness in Mode C.** The transpile mode exposes `app.theme`
  and `app.media` like Modes A/B: `app.theme.is_dark()` resolves light/dark
  (`SYSTEM` follows the OS), and `app.media` (width/height/platform_dark_mode/
  orientation) is kept in sync with the browser via matchMedia + resize, so the
  view re-renders responsively. `app.set_theme(Theme(...))` swaps the theme.
  `client/transpile/theme.js` ports `tempest_core.theme` (ThemeMode/Theme/
  MediaQueryData/Breakpoints); `client/transpile/media.js` reports the viewport.
  Verified live (Playwright): a resize flips narrow↔wide and a toggle flips
  light↔dark.

## [0.20.0] — 2026-07-10

### Added

- **i18n in Mode C (`translate`/`t` + `Locale`).** The core's localization works
  in the transpile mode: look a key up in a `{language: {key: template}}` table by
  the locale's language and interpolate `{name}`, mirroring `tempest_core.i18n`
  (including the miss/fallback rules). `client/transpile/i18n.js` ports it; the
  transpiler routes `from tempest_core import translate, t, Locale` to it.
  Verified live (Playwright): a language toggle flips PT → EN reactively.
- **Module-level constants in the subset.** A top-level `NAME = {...}` (e.g. a
  translations table) now transpiles to a `const`, so apps can define shared data
  outside `view`.

## [0.19.0] — 2026-07-10

### Added

- **Navigation in Mode C (routes + URL sync).** The transpile mode now speaks the
  core navigation API — `app.push(Route(...))`, `app.pop()`, `app.replace(...)`,
  `app.reset(...)`, and `app.nav.top` — synced with the browser URL. A push/pop
  `pushState`-s the new path; a deep link or back/forward resets the stack from
  the path (`routesFromPath`), so the same `view()` runs under Modes A/B/C.
  `client/transpile/nav.js` ports `tempest_core.navigation` (Route kept at strict
  parity, since the transpile build validates through the real core).
- **Transpiler: common builtins.** `len` → `.length`, and `str`/`int`/`float`/
  `bool`/`abs` map to their JS idioms; keyword-only class calls (e.g.
  `Route(name=...)`) emit `new`.

## [0.18.0] — 2026-07-10

### Added

- **More Mode C native capabilities.** `share`, `audio`, `file`, and
  `notifications` (notify + request_permission) join the Mode C facade, alongside
  http/storage/clipboard/geolocation/cookies. All route to the shared
  `client/native` glue; the capability contract marks them `mode_c` and the
  conformance test enforces the facade matches that subset.
- **`tempest_core.validators` in Mode C.** `client/transpile/validators.js` is a
  faithful port of the core's BR field validators (`validate_cpf`/`cnpj`/`email`/
  `phone`) — same algorithms and PT-BR messages. The transpiler routes
  `from tempest_core.validators import ...` to it, so a transpiled form validates
  client-side with no Python. Parity is locked by a core-derived fixture.

## [0.17.0] — 2026-07-10

### Added

- **Native-capability contract (single source of truth).**
  `tempestweb.native.contract` pins the set of native capabilities and which are
  exposed in Mode C. Conformance tests assert the three surfaces agree — the
  Python awaitables, the JS `HANDLERS` (`client/native/index.js`), and the Mode C
  facade (`client/transpile/native.js`) — so a capability added to one surface
  but not the others fails CI. It is the extraction candidate for a shared
  contract `tempestroid` (mobile) could mirror.

## [0.16.0] — 2026-07-10

### Added

- **Mode C `storage` is IndexedDB-backed.** The transpile-mode `storage`
  capability now persists over IndexedDB via a minimal async KV
  (`client/native/idb-kv.js`) injected as `deps.store`, falling back to
  localStorage only when IndexedDB is unavailable. Verified live (Playwright):
  values land in the `tempestweb/kv` object store, not localStorage.

## [0.15.0] — 2026-07-10

### Added

- **Native capabilities in Mode C (via the typed Python interface).** The same
  `tempestweb.native` API used by Modes A/B now works in the transpile mode:
  `http`/requests, `storage` (IndexedDB/localStorage), `clipboard`,
  `geolocation`, and the new `cookies`. A transpiled `await native.http.request(
  ...)` becomes an in-process JS call to the shared browser glue
  (`client/native/*.js`) through the `dispatch` registry — no Python, no bridge,
  no network. The `client/transpile/native.js` facade mirrors the Python API;
  `from tempestweb import native` is routed to it by the transpiler. Verified live
  (Playwright): a transpiled app round-trips a cookie and a storage value.
- **`async`/`await` in the transpile subset.** `async def` handlers and `await`
  expressions transpile (methods and nested defs too); the runtime tolerates an
  async handler (re-render on `set_state` after the await). Also added: dict
  literals → JS objects, and mixed positional+keyword calls → a trailing options
  object (e.g. `native.http.request("GET", url, json=body)`).
- **`cookies` native capability (all modes).** A new typed awaitable
  (`native.cookies.get/set/remove/all`) over `document.cookie`, served by
  `client/native/cookies.js` in every mode. Non-HttpOnly cookies only.

## [0.14.0] — 2026-07-10

### Added

- **Mode C — `tempestweb dev --mode transpile` (watch + livereload).** The dev
  loop now serves the transpile mode with browser livereload, completing the CLI
  story (`build` / `run` / `dev`) for Mode C. It builds the static bundle, serves
  it over the dev HTTP app, and rebuilds on every watched change before reloading
  the tab; a failing rebuild (syntax error or out-of-subset construct) is reported
  and skipped so the last good bundle keeps serving. Both static modes (wasm,
  transpile) share the devserver; Mode B still uses `run --mode server`.

## [0.13.0] — 2026-07-10

### Added

- **Mode C — the ergonomic layout components `HStack` / `VStack`.** The
  `tempest_core.components` layer is Python composition (each expands to a
  primitive widget tree at `build()` time), so it is not auto-portable to a
  Python-free runtime — except the pure layout aliases, which expand to a plain
  `Row` / `Column`. `HStack`/`VStack` are now available in Mode C
  (`client/transpile/components.js`): a `gap` as a spacing token (`"md"`,
  resolved via the core-derived `spacing.gen.js`) or a raw px, plus direct
  `align`/`justify`. Parity with the core is locked by a core-derived fixture
  (order-agnostic) and byte-match golden tests.

### Note

- The rest of `tempest_core.components` (Card, DataTable, Tabs, charts, form
  inputs) stays out of Mode C: their composition is data/loop-driven Python that
  a zero-Python runtime cannot reproduce without compiling the core's own
  composition source. Use Modes A/B for those, or compose from primitives.

## [0.12.0] — 2026-07-10

### Added

- **Mode C — every `tempest_core` widget is ported (experimental).** All ~64
  buildable core widgets now have native-JS IR builders, **generated by
  introspecting the real core** (`client/transpile/widgets.gen.js` +
  `tests/conformance/_transpile_widgets.py`) — no hand-written per-widget code.
  Layout (`Column`, `Row`, `Container`, `Stack`, `Wrap`, `ScrollView`,
  `SafeArea`, `Spacer`), display (`Text`, `Icon`, `Image`, `Svg`, `Spinner`,
  `Skeleton`, `ProgressBar`), input (`Button`, `Input`, `TextArea`, `Switch`,
  `Checkbox`, `Slider`, `RangeSlider`, `Dropdown`, `DatePicker`, `PinInput`, …),
  overlays (`Dialog`, `BottomSheet`, `Popover`, `Toast`, `Tooltip`), and gestures
  (`GestureDetector`, `Draggable`, `PanHandler`, …). Each builder writes the
  core's wire prop shape with real defaults; required props have no default.
- **Mode C — Material 3 styling for every styled widget.** The introspected
  style table now covers all 14 styled widgets across the axes each accepts
  (variant/field_variant × size × color_scheme, normalized with `"_"`), resolved
  the same way as the core.
- **Mode C — per-widget event binding.** Handlers are stashed in a non-wire
  `__handlers` map and bound to the DOM event the renderer emits for that widget:
  `on_click` → click; `on_change`/`on_toggle` → `input`/`change` on native form
  controls (`Input`/`Checkbox`) and → click on div-rendered toggles like
  `Switch`. Verified live (Playwright) with a multi-widget gallery.
- **Golden coverage.** Byte-match tests lock both generated modules
  (`widgets.gen.js`, `widget-styles.gen.js`) against the live core; a JS smoke
  test builds every widget. The Mode C tutorial (PT + EN) documents the full set.

### Note

- `tempest_core.components` (compositions like Card/DataTable/Tabs, layered above
  the widgets) and exotic events the client does not yet emit remain out of scope.

## [0.11.0] — 2026-07-09

### Added

- **Mode C — `tempestweb build --mode transpile` (experimental).** The transpile
  mode is now a real CLI target: `build --mode transpile <path>` (and
  `run --mode transpile`, which static-hosts the bundle like wasm) transcribes
  the project's `app.py` to `client/transpile/app.gen.js` and emits a **fully
  static** artifact — an `index.html` that mounts via `mountApp`, the shared JS
  client, and the native runtime (diff/widgets/runtime). Zero Python at runtime,
  servable by any CDN. An out-of-subset app fails with a clear `BuildError`.
- **Mode C — Button & Input Material 3 style fidelity.** A build-time generator
  introspects the real `tempest_core`, resolving each Button (variant × size ×
  color_scheme) and Input (field_variant × size × color_scheme) style into a
  native JS data module (`widget-styles.gen.js`); the widget builders look it up
  and merge an explicit `style` on top. Transpiled buttons/fields now render with
  their MD3 look — parity with Modes A/B, verified live (Playwright). A golden
  test byte-matches the table against the core. (`state_styles` hover/pressed is
  N/A: the IR carries no interaction state.)
- **Mode C — `Input` with reactive two-way binding.** The native runtime
  dispatches handlers by `"eventType:key"`, so `input`/`change` events reach an
  `Input`'s `on_change`; the shared `dom.js` renders the `<input>`. Typing drives
  `on_change → set_state → re-render` end-to-end with no Python — verified in the
  browser with a live `Hello, {name}!` form.
- **Mode C — wider Python subset.** The transpiler now handles arithmetic
  (`* / %`), comparisons, boolean/unary operators, ternary expressions, list
  comprehensions (`→ .filter().map()`), `in`/`not in`, subscript, expression
  lambdas, `if`/`elif`/`else`, `for … in`, assignment/`+=`, and **dataclass
  methods** (`self → this`). New `Container` widget (layout + `tag`/`attrs`
  escape hatch).
- **Bilingual Mode C tutorial docs.** A tiangolo-style page (PT-BR default +
  EN-US) in the docs nav, covering the first build, generated output, state
  methods, reactive forms, and the supported subset.

## [0.10.0] — 2026-07-09

### Added

- **Mode C — transpile (experimental, spike C0).** A third execution mode
  alongside **A (WASM)** and **B (server)**: the typed-Python *app layer* is
  transcribed to **native JavaScript** — zero Python runtime in the browser,
  static hosting, great first-paint/SEO. The "TypeScript story" for Python. It
  reuses the whole shared JS renderer (`client/dom.js`, `style.js`, `events.js`):
  only the app layer is compiled.
  - **Compiler** (`tempestweb.transpile`) — an `ast`-based codegen for a small,
    typed Python subset (`@dataclass` state, `view()`, handler closures,
    `setattr` mutations, f-strings, keyword-only widget calls). Out-of-subset
    constructs raise `TranspileError` with a `file:line` diagnostic.
  - **Native JS runtime** (`client/transpile/`) — `diff.js` (a faithful port of
    the core reconciler, locked against a core-derived golden covering all five
    patch kinds), `widgets.js` (IR builders), `runtime.js` (`State`/`App` + the
    render loop). A generated `counter.gen.js` runs the canonical counter.
  - Verified live in the browser (Playwright): the counter renders and updates
    with **granular Update patches** (no root re-render), zero Python at runtime.
  - **Experimental / spike.** Widget style fidelity (MD3 defaults), a
    `tempestweb build --mode transpile` CLI target, and a wider subset are the
    next phases (C1–C5). See `docs/modo-c-transpile.md`. The public API may
    change; not yet recommended for production apps.

### Changed

- **Pinned `tempest-core>=0.11.0`** (was `>=0.9.0`). The conformance goldens are
  regenerated from the new core; no wire-shape change beyond what 0.9.0 already
  carried (`Widget.tag` / `Widget.attrs`).

## [0.9.0] — 2026-07-04

### Added

- **Static SSR — a new leaf renderer (`tempestweb.html`).** The same typed widget
  tree that drives the interactive DOM client now renders to a **static HTML
  string** on the server, reusing `tempest_core.build()` — the "one tree, N
  renderers" thesis, with HTML as a render target alongside the DOM-JS client.
  - `render_to_html(widget) -> str` renders a widget tree to an HTML fragment.
  - `render_document(widget, *, title, lang="pt-BR", head="", htmx=False,
    css_reset=True) -> str` wraps a tree in a full `<!doctype html>` document
    (charset + viewport meta, escaped `<title>`, optional CSS reset, optional htmx
    script tag).
  - `style_to_css(style, widget_type=None) -> str` is a faithful Python port of
    the client's `client/style.js` (`styleToCss`) — **byte-identical** CSS output
    (same field order, enum maps, and JavaScript-style number formatting) so a
    server-rendered page and the DOM client agree with no hydration drift.
  - `escape_text` / `escape_attr` are the HTML-escaping choke points; every text
    node and attribute value passes through them, and the `attrs` escape hatch
    rejects invalid attribute names (`^[a-zA-Z][a-zA-Z0-9:_-]*$`) as an
    attribute-injection guard.
- **`tag` / `attrs` honoring.** The renderer reads the new (`tempest-core` 0.9.0)
  base `Widget.tag` (semantic HTML tag override) and `Widget.attrs` (arbitrary
  HTML attributes — `hx-*`, `id`, `class`, `data-*`, `aria-*`) so a typed tree can
  emit semantic, htmx-ready markup (`Container(tag="nav", attrs={...})`).

### Changed

- **Pinned `tempest-core>=0.9.0`** (was `>=0.8.2`) for the base `Widget.tag` /
  `Widget.attrs` fields the HTML renderer consumes.
- **The Mode B wire omits empty `tag` / `attrs`.** Since `tempest-core` 0.9.0 puts
  `tag=None` / `attrs={}` on every node's props, `runtime.serialize.node_to_wire`
  now drops them when falsy. This keeps the WebSocket/SSE payload byte-identical to
  the pre-0.9.0 wire for widgets that do not use them (no per-node bloat) — a
  widget that *does* set them still ships them. The conformance golden
  (`tests/fixtures/conformance_scenarios.json`, derived from `model_dump`) was
  regenerated to reflect the new base fields (purely additive).

## [0.8.1] — 2026-06-27

### Changed

- **`tempest-core` is now the single source of truth.** The whole example
  gallery and the test suite import the renderer-agnostic engine directly as
  `tempest_core` (`from tempest_core import App, Column, Style, …`) instead of
  going through the historical `tempestweb._core` path. Both execution modes were
  re-verified live in the browser (Playwright): the counter renders and updates in
  **Mode B** (FastAPI + WebSocket round-trip) and in **Mode A** (Pyodide,
  in-process, zero-network) with the shim gone.

### Removed

- **The `tempestweb._core` back-compat shim.** The vendored `tempestweb/_core/`
  copy was already extracted into the standalone `tempest-core` package; the shim
  that re-exported it under the old import path (and its `test_core_shim.py`) is
  deleted. The Mode A WASM bundler no longer packs a `_core` part — it ships the
  `tempest_core` package directly. Internal-only change: `_core` was always
  private, so no public API is affected.

## [0.8.0] — 2026-06-25

### Added

- **Two vendored icon sets — Material Symbols (Outlined) + Lucide.** A new
  `tempestweb.icons` façade (`material_icon`, `lucide_icon`, `custom_icon`,
  `register_icon`, `MaterialIcons`/`Icons` enums) builds the core `Icon` widget
  from either set. Both render client-side as **inline SVG** from path data
  vendored in `client/icons/{lucide,material}.js` — no icon font, no network,
  offline/PWA safe. The set is encoded as a `"set:"` prefix on the icon name
  (`"material:home"` / `"lucide:mail"`); a bare name stays Lucide for
  compatibility with the core `Icon` and the field icon slots. `custom_icon`
  ships a one-off SVG path over the wire (no registration); `register_icon` +
  the client `registerIcon` add a reused glyph to both sides.
- **`tempestweb build` bundles the icon assets** into the artifact, so installed
  PWAs draw every icon offline.
- **Docs:** bilingual "Icons (Material + Lucide)" guide (PT-BR + EN-US).

### Changed

- **Bumped tempest-core to `>=0.8.2`.** Picks up the clickable-`Rating` fix
  (stars render as bare glyphs, not filled pills).

### Fixed

- **The `core-profile-cards` example uses an interactive `Rating` again.** The
  0.7.0 display-only workaround is reverted now that tempest-core 0.8.2 renders
  clickable stars as bare glyphs.

## [0.7.0] — 2026-06-25

### Added

- **Canvas rendering on the web.** The DOM renderer now maps a `Canvas` widget to
  a real `<canvas>` and executes its draw-command list
  (`move_to`/`line_to`/`draw_rect`/`stroke`/`fill`/`draw_text`) onto the 2D
  context. Previously any unknown node type fell back to a `<div>`, so the core's
  Canvas-based components (charts, detection overlays, the sketch pad) rendered
  blank — they now draw in both modes.
- **The tempest-core component library, re-exported through
  `tempestweb.components`.** 54 Material 3 components (layout scaffolds, app bars,
  navigation, cards, lists, inputs, feedback, tables and `BarChart`/`LineChart`
  charts) plus the value models/helpers that drive them (`ChartSeries`,
  `TableRow`/`TableCell`, `DetectionBox`, `confidence_scheme`) are now importable
  from `tempestweb.components` — one import home for the native helpers and the
  core set. Each lowers to renderable primitives or a Canvas draw-command list,
  so the whole library works in Mode A and Mode B.

### Changed

- **Bumped tempest-core to `>=0.8.1`** and **delegated Material 3 styling to the
  core's native variant system.** The core now resolves each `Button`/`Input`
  variant's resting MD3 style inline (fill, border, shape, color), so tempestweb
  no longer reimplements it. The button helpers (`filled_button`, `tonal_button`,
  `outlined_button`, `text_button`, `elevated_button`) are now a thin MD3-named
  façade over the core variants; `client/theme.js` keeps only what inline Style
  cannot express (the `::before` state layer, focus ring, disabled state, surface
  fill and type ramp) and dropped the duplicated resting rules.
- **Behavior:** outlined/text buttons now paint the core's opaque surface fill
  (was transparent), and the `Input` focus indicator is the inset box-shadow ring
  (the core's inline border outranks a stylesheet `:focus` rule). Apps still get
  the MD3 look with zero CSS.

## [0.6.0] — 2026-06-13

### Added

- **Always-on Material 3 base stylesheet.** The web client now ships a small
  always-on MD3 base theme (`client/theme.js`), keyed off `data-tw-type`, so
  apps get sensible typography, spacing and accented controls out of the box —
  no per-widget styling required. Inline widget `Style` still overrides it.
- **`Style.shadow` renders as `box-shadow` on the web.** Elevation set on a
  widget's `Style` now emits a real CSS `box-shadow`, matching the native
  renderers.
- **MD3 field and button variants.** The pre-built components (`fields`,
  `buttons`) gained light Material 3 variants (filled/outlined/text buttons,
  themed text fields) so forms look finished without hand-styling.

### Fixed

- **Checkbox MD3 theming targets the nested input.** Following the Checkbox
  `<label><input>` structure (0.5.3), the base theme sizes/accents the nested
  `[data-tw-type="Checkbox"] > input` rather than the keyed `<label>` wrapper,
  so the box is styled without shrinking the whole caption row.

## [0.5.3] — 2026-06-13

### Fixed

- **`Checkbox` now renders its label as visible text on the web.** The DOM
  renderer mapped `Checkbox` to a bare `<input type=checkbox>` and put its
  `label` on `aria-label` only, so labelled checkboxes (todo items, settings
  toggles) showed as empty boxes. A `Checkbox` now renders as a `<label>`
  wrapping the real `<input>` plus a caption text node: the box and its caption
  lay out as one tidy row (the wrapper also gives the input its accessible name
  natively). The `<label>` is the keyed, path-addressed element; the nested
  input carries `checked` and fires `change`, which bubbles to the label for
  event delegation. An explicit widget `Style` still wins.

### Examples

- **Fixed three examples that passed `children=` to `Container`.** `Container`
  holds a single `child`, not a `children` list (that is `Column`/`Row`/`Stack`).
  Pydantic silently dropped the unknown kwarg, so the container rendered empty:
  `list_demo` lost its row text (1000-item list showed blank rows), `gesture_demo`
  lost its "swipe or tap me" hint, and `anim_demo` carried a no-op `children=[]`.

## [0.5.2] — 2026-06-13

### Changed

- **Friendly error when the `[server]` extra is missing for Mode A serving.**
  `tempestweb dev` and `tempestweb run --mode wasm` lazy-import the dev server
  (Starlette + uvicorn, shipped under the `[server]` extra). On an install
  without it the import surfaced a raw `ModuleNotFoundError`. Both commands now
  raise a `DevError`/`RunError` with an actionable hint
  (`uv add 'tempestweb[server]'`), printed cleanly by the CLI. The built wasm
  artifact still never embeds a server — this only affects local serving.

## [0.5.1] — 2026-06-13

### Fixed

- **`Row`/`Column` are now flex containers on the web by default.** The web
  renderer only emitted `display: flex` when a style set an explicit `direction`,
  so a `Row`/`Column` with just `gap`/`justify`/`align` rendered as a plain block
  and those properties were silently inert (children only flowed horizontally by
  accident when they were inline-block, e.g. buttons). `styleToCss` now takes the
  widget type and defaults `display: flex` + `flex-direction` (`row`/`column`,
  also `LazyRow`/`LazyColumn`) from it; an explicit `style.direction` still
  overrides the natural axis. This matches the widget docstrings and the native
  (Qt/Compose) behaviour. Non-flex types (`Container`, `Stack`) are unchanged.

## [0.5.0] — 2026-06-13

### Added

- **`tempestweb sync` command** — auto-fills `[wasm].modules` from the project's
  installed pure-Python dependencies. Reads `[project.dependencies]` from
  `pyproject.toml`, keeps the names that are installed **and** pure-Python
  (no `.so`/`.pyd`/`.dylib`), and writes their import names into `[wasm].modules`,
  preserving existing entries. Native packages (numpy, pillow) and the framework
  (`tempestweb`, `pydantic`, …) are skipped, as is anything already under
  `[wasm].packages`. Idempotent; `--dry-run` previews without writing. Pairs with
  the 0.4.0 site-packages resolution so a dependency you `uv add` reaches the wasm
  bundle with **zero manual bookkeeping**. Uses `tomlkit` (added to the `[cli]`
  extra) for a comment-preserving round-trip edit of `tempestweb.toml`.

## [0.4.0] — 2026-06-13

### Added

- **`[wasm].modules` resolves from the installed environment** — each entry is now
  resolved in two steps: a vendored copy beside `app.py`
  (`<project>/<module>/`) still wins, but when none exists the module is pulled
  straight from the project's `.venv` `site-packages` via `importlib`. A
  dependency you `uv add` no longer has to be cloned and committed at the repo
  root to make it into the wasm bundle — just list it in `modules`. A name that is
  neither vendored nor importable fails the build with a clear message.
  Backward compatible: existing vendored layouts build unchanged. A stale project
  directory holding only `__pycache__` (real source deleted, bytecode lingering)
  no longer shadows the installed package and silently bundles nothing — it falls
  through to the installed copy.

## [0.3.0] — 2026-06-13

### Added

- **`native.install` capability** — the PWA install flow in Python:
  `install.state()` → `InstallState(can_install, installed)` and
  `install.prompt()` → `"accepted" | "dismissed" | "unavailable"`. Wraps the soft
  controller in `client/pwa/install-prompt.js` (now copied into the wasm
  artifact) via `client/native/install.js`.

## [0.2.0] — 2026-06-13

Real-app capabilities, driven by building a full on-device vision PWA (FAMACHApp)
entirely on tempestweb. Backward compatible — existing apps build unchanged.

### Added

- **`native.onnx` capability** — run ONNX models in the browser via
  **onnxruntime-web**. `onnx.load(model_url) → OnnxModel` and
  `onnx.run(session_id, feeds) → {name: Tensor}`, bridged over the same
  `native_call` seam (`client/native/onnx.js`, wasm execution provider forced).
  numpy-free: tensors cross as base64 + shape + dtype. Unlocks in-browser
  inference even though `onnxruntime` has no Pyodide wheel.
- **`native.file` capability** — `file.save(name, bytes, mime)` shares
  (Web Share API) or downloads a generated blob; `file.pick(accept)` opens a file
  input and returns the chosen file as `PickedFile` (bytes the FilePicker widget's
  uri-only event can't carry). `client/native/file.js`.
- **`[wasm]` project config** (`tempestweb.toml`): `packages` (extra Pyodide
  packages to `loadPackage`, e.g. numpy/pillow), `modules` (project Python
  packages bundled next to `app.py`), `assets` (static files copied verbatim +
  precached, e.g. `.onnx` models), `scripts` (`<script>` tags injected before the
  bootstrap, e.g. onnxruntime-web). Threaded through `tempestweb build`.

### Fixed

- `load_app` now puts the project root on `sys.path`, so a multi-module project's
  `app.py` can import the sibling packages it ships (previously failed the build's
  render check with `ModuleNotFoundError`).

## [0.1.0] — 2026-06-11

First public release. Build web apps in typed Python — one declarative tree, a
pure-JS DOM renderer, two execution modes (WASM in the browser via Pyodide, or a
FastAPI server over WebSocket/SSE).

### Added

- **Two execution modes, one `view()`.** Mode A (WASM/Pyodide) runs Python in the
  browser; Mode B (server) runs it on FastAPI over WebSocket + SSE. The app never
  names a transport.
- **`tempestweb` CLI** — `new` (scaffold), `dev` (watch + reload), `build`
  (`--mode wasm|server`), `run`. The wasm build emits a static bundle (Pyodide +
  the `tempest_core`/`tempestweb` payload + `app.py`); the server build emits a
  FastAPI host.
- **Pure-JS client** (no TypeScript, no framework, no build step): DOM patcher,
  `Style`→CSS, delegated events, the three transports (wasm/ws/sse).
- **Trilho E parity** (live in Mode A): URL routing (deep links + back/forward +
  pushState), virtualized lists with a proportional scrollbar, overlays
  (dialogs/sheets), CSS transitions, pointer gestures (tap/swipe/long-press),
  real form controls (Input/Checkbox/Image), and a11y (semantics→ARIA) / i18n /
  theme.
- **Native capabilities** wired in both modes (geolocation, clipboard, http,
  share, camera, audio, storage, notifications) — in-process FFI in Mode A,
  proxied over the transport in Mode B.
- **PWA layer**: installable manifest + icons + a service worker with an injected
  app-shell precache (offline second load).
- **Observability**: telemetry, logger, error boundary, feature flags, auth —
  adapter pattern.
- **`tempestweb.components`**: ready-to-use validated fields (EmailField,
  PasswordField, PhoneField, CPFField, CNPJField, AddressField, TextField) and
  forms (LoginForm, SignupForm).
- **Bilingual docs** (PT-BR + EN) built with MkDocs Material.

### Depends on

- [`tempest-core`](https://pypi.org/project/tempest-core/) `>=0.1.0` — the
  renderer-agnostic UI engine (IR/reconciler/state/style/widgets).

### Known follow-ups

- Mode B `view→URL` (pushState) needs a server→client nav envelope (Mode A is
  bidirectional today).
- WebPush tab-closed delivery and real camera/geo need on-device verification.
