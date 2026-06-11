# Galeria de Exemplos 🎨

Bem-vindo à galeria do **tempestweb**! 🚀 Aqui você encontra apps completos e
prontos para rodar, cada um focado em **um conceito** — estado, formulários,
listas, navegação, tema, i18n, canvas e muito mais.

!!! tip "Os dois modos, o mesmo código"
    Cada exemplo é um módulo `view(app) -> Widget` em Python tipado. O **mesmo**
    `app.py` roda nos dois modos sem mudar uma linha:

    - **Modo A (WASM/Pyodide)** — Python direto no browser.
    - **Modo B (servidor)** — Python no servidor FastAPI + cliente fino por WebSocket.

    A árvore de view nunca nomeia um transporte. Você escreve a lógica uma vez e
    escolhe o modo na hora de servir.

!!! note "Como ler cada página"
    Toda página segue o padrão do tutorial: o que você vai construir → o código
    mínimo → explicação peça por peça → um **Recap** no final. Comece por
    [**Contador**](../tutorial/index.md) e [**Lista de tarefas**](#fundamentos)
    se for novo por aqui.

---

## Fundamentos

Os blocos básicos — o ponto de partida para todo mundo. Esses quatro já fazem
parte do [Tutorial](../tutorial/index.md).

- [**Contador**](../tutorial/index.md) — o "olá mundo" reativo: estado + handler + patch.
- [**Lista de tarefas**](../tutorial/state.md) — `Input` controlado, lista virtualizada e checkboxes por item.
- [**Formulário**](../tutorial/state.md) — `Form` + `FormField` + validadores que espelham erros no estado.
- [**Fetch assíncrono**](../tutorial/state.md) — transição `idle → loading → loaded` com handler `async`.

---

## Estado e dados

Gerencie tempo, conversões e tabelas de forma 100% determinística.

- [**Cronômetro**](stopwatch.md) — Start/Stop/Lap/Reset com tempo guardado como inteiro de décimos de segundo (sem relógio de parede).
- [**Conversor de temperatura**](temperature-converter.md) — dois campos controlados (Celsius/Fahrenheit) sincronizados via _two-way binding_.
- [**Tabela de dados**](data-table.md) — busca ao vivo + ordenação por coluna (ASC/DESC), tudo dirigido pelo estado em Python.

---

## Formulários e fluxos

Da validação simples ao wizard de múltiplos passos.

- [**Formulário de login**](login-form.md) — `EmailInput`/`PasswordInput`, validação em três camadas e `Banner` de erro.
- [**Wizard de cadastro**](signup-wizard.md) — três passos (Conta/Perfil/Revisão) com validadores que liberam o "Próximo".
- [**Cadastro brasileiro**](br-cadastro.md) — PF/PJ com máscaras de CPF/CNPJ/telefone/endereço e validadores BR em tempo real.
- [**Quiz com pontuação**](quiz-app.md) — 5 perguntas com `RadioGroup`, `ProgressBar` e tela final de resultado.

---

## Layout e navegação

Cascas de app, abas, drawers e rotas.

- [**Perfil com abas**](tabs-profile.md) — `TabView` + `RouteChangeEvent` com três seções e `Switch` nas configurações.
- [**Dashboard app shell**](dashboard-shell.md) — `Scaffold` + `AppBar` + `Sidebar` + `NavBar` com quatro seções alternáveis.
- [**Drawer de navegação e rotas**](router-drawer.md) — `RouteDrawer` deslizante, push/pop de rotas em 2 níveis e `Breadcrumb`.
- [**Onboarding carousel**](onboarding-carousel.md) — `PageView` com `PageChangeEvent`, indicador de pontos e tela de conclusão.

---

## Listas, mídia e entrada

Listas virtualizadas, galerias, chat, busca e drag-and-drop.

- [**Galeria de imagens**](image-gallery.md) — `LazyGrid` virtualizado de 12 fotos + `Dialog` lightbox com Prev/Next/Close.
- [**Chat UI**](chat-ui.md) — `LazyColumn` virtualizado, `Input` two-way e `Button` de envio com aviso de mensagem vazia.
- [**Busca com autocomplete**](search-autocomplete.md) — filtragem ao vivo via `Autocomplete` + filtro de categoria por `Chip`.
- [**Kanban board**](kanban-board.md) — três colunas com cards `Draggable` e `DragTarget` para mover/excluir.

---

## Componentes de seleção e feedback

Controles, disclosure e estados de feedback.

- [**Painel de configurações**](settings-panel.md) — `Switch`, `Checkbox`, `Slider`, `RadioGroup` e `SegmentedControl` ligados ao estado.
- [**Avaliação e review**](rating-review.md) — estrelas `Rating` + `Chip` tags + `TextArea` num formulário validado.
- [**FAQ accordion**](faq-accordion.md) — `Accordion` com política de "um aberto por vez" e filtro de busca ao vivo.
- [**Central de notificações**](notification-center.md) — `Banner`, `Badge` de não-lidas e `EmptyState` na caixa vazia.

---

## Tema, i18n e canvas

Personalização visual, internacionalização e desenho.

- [**Alternador de tema**](theme-switcher.md) — `Theme`/`ThemeMode` com `App.set_theme`, `Theme.is_dark` e simulação de OS via `MediaQueryData`.
- [**Saudação internacionalizada**](i18n-greeting.md) — `Locale` + `translate()`/`t()` com inglês, português e árabe (RTL).
- [**Sketch pad (canvas)**](sketch-canvas.md) — strokes como listas de comandos de desenho (`MoveTo`/`LineTo`), presets, undo e clear.

---

!!! check "Pronto para começar?"
    Escolha um exemplo que se pareça com o que você quer construir, copie o
    `app.py`, e rode nos dois modos. Todos passam no _gate_ verde (build, ruff,
    mypy `--strict`). Bom código! 💡
