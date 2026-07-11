# Galeria de Exemplos 🎨

Bem-vindo à galeria do **tempestweb**! 🚀 Aqui você encontra apps completos e
prontos para rodar, cada um focado em **um conceito** — estado, formulários,
listas, navegação, tema, i18n, canvas, capacidades nativas e muito mais.

!!! tip "Os três modos, o mesmo código"
    Cada exemplo é um módulo `view(app) -> Widget` em Python tipado. O **mesmo**
    `app.py` roda sem mudar uma linha:

    - **Modo A (WASM/Pyodide)** — Python direto no browser.
    - **Modo B (servidor)** — Python no servidor FastAPI + cliente fino por WebSocket.
    - **Modo C (transpile)** — o app transcrito para JS nativo, bundle estático.

    A árvore de view nunca nomeia um transporte. Você escreve a lógica uma vez e
    escolhe o modo na hora de servir.

!!! info "Os selos de modo"
    Cada linha traz um selo: **[A/B]** roda nos modos interativos (WASM e servidor);
    **[A/B/C]** roda **também** transpilado para JS nativo. A maioria dos exemplos
    usa componentes prontos ou o formato Python de evento (`event.value`), por isso
    vive em **A/B**. O **Modo C** roda o subconjunto de **widgets puros** — o
    exemplo-vitrine é o [Tour do Modo C](transpile-tour.md).

!!! note "Como ler cada página"
    Toda página segue o padrão do tutorial: o que você vai construir → o código
    completo → explicação peça por peça → um **Recap** no final. Comece pelo
    [**Contador**](../tutorial/index.md) e pela [**Lista de tarefas**](todo.md) se
    for novo por aqui.

---

## Fundamentos

Os blocos básicos — o ponto de partida para todo mundo.

- [**Contador**](../tutorial/index.md) — o "olá mundo" reativo: estado + handler + patch. **[A/B/C]**
- [**Lista de tarefas**](todo.md) — `Input` controlado, `LazyColumn` virtualizado e `Checkbox` por item. **[A/B]**
- [**Formulário**](form.md) — `Form` + `FormField` + validadores tipados que espelham erros no estado. **[A/B]**
- [**Fetch assíncrono**](fetch.md) — transição `idle → loading → loaded/error` com handler `async`. **[A/B]**

---

## Estado e dados

Gerencie tempo, conversões, tabelas e gráficos de forma 100% determinística.

- [**Cronômetro**](stopwatch.md) — Start/Stop/Lap/Reset com tempo guardado como inteiro de décimos de segundo. **[A/B]**
- [**Conversor de temperatura**](temperature-converter.md) — dois campos controlados (Celsius/Fahrenheit) sincronizados via _two-way binding_. **[A/B]**
- [**Tabela de dados**](data-table.md) — busca ao vivo + ordenação por coluna (ASC/DESC), dirigida pelo estado. **[A/B]**
- [**Grade de dados**](data-grid.md) — grade densa com colunas tipadas e formatação por célula. **[A/B]**
- [**Dashboard de gráficos**](charts-dashboard.md) — cards de métricas + gráficos desenhados a partir do estado. **[A/B]**

---

## Formulários e fluxos

Da validação simples ao wizard de múltiplos passos.

- [**Formulário de login**](login-form.md) — `EmailInput`/`PasswordInput`, validação em três camadas e `Banner` de erro. **[A/B]**
- [**Wizard de cadastro**](signup-wizard.md) — três passos (Conta/Perfil/Revisão) com validadores que liberam o "Próximo". **[A/B]**
- [**Cadastro brasileiro**](br-cadastro.md) — PF/PJ com máscaras de CPF/CNPJ/telefone/endereço e validadores BR em tempo real. **[A/B]**
- [**Quiz com pontuação**](quiz-app.md) — 5 perguntas com `RadioGroup`, `ProgressBar` e tela final de resultado. **[A/B]**

---

## Componentes prontos (core)

Os componentes de alto nível do `tempest_core` — cascas, cards e feedback prontos.

- [**App shell do core**](core-app-shell.md) — `Scaffold` + `AppBar` + `NavBar` montados em poucas linhas. **[A/B]**
- [**Configurações com abas**](core-tabbed-settings.md) — `TabView` com seções de preferências. **[A/B]**
- [**Feedback e status**](core-feedback.md) — `Banner`, `Badge`, `EmptyState` e `Spinner` em seus estados. **[A/B]**
- [**Cards de perfil**](core-profile-cards.md) — `Card` + `Avatar` + `Chip` compondo um grid de perfis. **[A/B]**

---

## Layout e navegação

Cascas de app, abas, drawers e rotas.

- [**Perfil com abas**](tabs-profile.md) — `TabView` + `RouteChangeEvent` com três seções e um `Switch`. **[A/B]**
- [**Dashboard app shell**](dashboard-shell.md) — `Scaffold` + `AppBar` + `Sidebar` + `NavBar` com seções alternáveis. **[A/B]**
- [**Drawer de navegação e rotas**](router-drawer.md) — `RouteDrawer` deslizante, push/pop em 2 níveis e `Breadcrumb`. **[A/B]**
- [**Onboarding carousel**](onboarding-carousel.md) — `PageView` com `PageChangeEvent`, indicador de pontos e tela de conclusão. **[A/B]**

---

## Listas, mídia e entrada

Listas virtualizadas, galerias, chat, busca e drag-and-drop.

- [**Galeria de imagens**](image-gallery.md) — `LazyGrid` virtualizado de 12 fotos + `Dialog` lightbox. **[A/B]**
- [**Chat UI**](chat-ui.md) — `LazyColumn` virtualizado, `Input` two-way e `Button` de envio. **[A/B]**
- [**Busca com autocomplete**](search-autocomplete.md) — filtragem ao vivo via `Autocomplete` + filtro de categoria por `Chip`. **[A/B]**
- [**Kanban board**](kanban-board.md) — três colunas com cards `Draggable` e `DragTarget` para mover/excluir. **[A/B]**

---

## Seleção e feedback

Controles, disclosure e estados de feedback.

- [**Painel de configurações**](settings-panel.md) — `Switch`, `Checkbox`, `Slider`, `RadioGroup` e `SegmentedControl` ligados ao estado. **[A/B]**
- [**Avaliação e review**](rating-review.md) — estrelas `Rating` + `Chip` tags + `TextArea` num formulário validado. **[A/B]**
- [**FAQ accordion**](faq-accordion.md) — `Accordion` com política de "um aberto por vez" e filtro de busca. **[A/B]**
- [**Central de notificações**](notification-center.md) — `Banner`, `Badge` de não-lidas e `EmptyState` na caixa vazia. **[A/B]**

---

## Tema, i18n e canvas

Personalização visual, internacionalização e desenho.

- [**Alternador de tema**](theme-switcher.md) — `Theme`/`ThemeMode` com `App.set_theme`, `Theme.is_dark` e simulação de OS. **[A/B]**
- [**Saudação internacionalizada**](i18n-greeting.md) — `Locale` + `translate()`/`t()` com inglês, português e árabe (RTL). **[A/B]**
- [**Sketch pad (canvas)**](sketch-canvas.md) — strokes como listas de comandos de desenho (`MoveTo`/`LineTo`), presets, undo e clear. **[A/B]**

---

## Capacidades nativas

A ponte nativa (`tempestweb.native`) dá acesso a geolocalização, HTTP, câmera,
área de transferência, compartilhamento e armazenamento — sempre via _callables_
injetáveis, então cada exemplo roda determinístico nos testes com um `FakeBridge`.

- [**Clima (HTTP + geolocalização)**](weather-native.md) — handler `async` encadeado combinando `geolocation.get_position` e `http.request`. **[A/B]**
- [**Copiar e compartilhar**](clipboard-share.md) — `clipboard.write` + `share.share` injetados, dirigindo dois handlers `async`. **[A/B]**
- [**Captura de câmera**](photo-capture.md) — ciclo `IDLE → CAPTURING → CAPTURED/ERROR` com `camera.capture` e preview por _data URI_. **[A/B]**
- [**Notas no armazenamento do dispositivo**](file-storage.md) — CRUD de notas sobre `storage.put/get/list_keys/remove`. **[A/B]**

---

## PWA e offline

Instalação como app, escritas duráveis e notificações push no browser.

- [**Instalação PWA + WebPush**](pwa-webpush.md) — fluxo de consentimento em 7 fases + script `build_pwa.py` que emite manifesto e ícones instaláveis. **[A/B]**
- [**Fila offline**](offline-queue.md) — escritas duráveis via `native.offline` (enqueue → size → replay) que sobrevivem a estar offline. **[A/B]**
- [**WebPush ponta a ponta (servidor)**](webpush-server.md) — assinatura + entrega de push VAPID reais a partir de um servidor FastAPI. **[B]**

---

## Observabilidade

Telemetria, _feature flags_, fronteiras de erro e autenticação — os blocos que
deixam um app pronto para produção.

- [**Feature flags**](feature-flags.md) — `FeatureFlagsProvider` + `InMemoryFeatureFlagsAdapter`: duas flags trocam variantes de widget ao vivo. **[A/B]**
- [**Error boundary + telemetria**](error-boundary.md) — `ErrorBoundary` envolvendo um filho explosivo, com `on_error` ligado a `Logger` + `TelemetryProvider`. **[A/B]**
- [**Gate de autenticação JWT**](auth-jwt.md) — `AuthStore` + `route_guard`, JWTs decodificados offline e trilha de auditoria via `Logger`. **[A/B]**

---

## Modos de execução

O mesmo `view` rodando no servidor ou transpilado, sem mudar uma linha.

- [**Rodando o Modo B (servidor)**](server-mode.md) — o exemplo do contador rodando _unchanged_ em um servidor FastAPI por WebSocket via `TestClient`. **[B]**
- [**Tour do Modo C (transpile)**](transpile-tour.md) — um app com estado+métodos, navegação, i18n, tema, formulário e animação transcrito para JS nativo. **[A/B/C]**

---

## Demos mínimos

Cada um isola **uma única capacidade** no menor código possível — ótimos para ler
de uma sentada. Não têm página dedicada; rode qualquer um com:

```bash
tempestweb run --path examples/<dir>
```

Todos rodam nos **Modos A/B**.

- **`a11y_demo`** — a11y (`Semantics` → ARIA) + i18n (`translate`) + cor de tema num único botão.
- **`anim_demo`** — transições CSS implícitas: um `Style` com `Transition` faz o browser tweenar a mudança.
- **`async_demo`** — um handler `async` que `await`a um timer e atualiza a UI sem travar a aba.
- **`geo_demo`** — a capacidade nativa de geolocalização (`native.get_position`) resolvida em-processo (Modo A) ou por proxy (Modo B).
- **`gesture_demo`** — `GestureDetector` roteando `on_swipe`/`on_tap` (gestos de ponteiro) para handlers Python.
- **`list_demo`** — um `LazyColumn` declarando 1000 itens mas materializando só a janela visível ao rolar.
- **`login_demo`** — a tela de login pronta via o componente `LoginForm`, sem layout manual.
- **`overlay_demo`** — a camada de overlay flutuante: um `Dialog` acima da árvore, dispensável por id.
- **`router_demo`** — navegação dirigida por URL: `view` renderiza a tela do topo de `app.nav`.

---

!!! check "Pronto para começar?"
    Escolha um exemplo que se pareça com o que você quer construir, copie o
    `app.py`, e rode nos modos que fizerem sentido. Todos passam no _gate_ verde
    (build, ruff, mypy `--strict`). Bom código! 💡
