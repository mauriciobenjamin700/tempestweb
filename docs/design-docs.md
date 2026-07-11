# Roadmap e docs de design

O tempestweb mantém um conjunto de **documentos de design vivos** versionados
junto ao código. Esta página é o índice deles — ela linka os originais no GitHub,
que são a fonte da verdade.

!!! info "Por que estes docs vivem no repositório"
    Eles usam links relativos para o código e para as fixtures, e mudam a cada
    fase. Mantê-los no repositório (e não rebuildados aqui) garante que estão
    sempre sincronizados com o que foi implementado.

## Os documentos

<div class="grid cards" markdown>

-   :material-file-document-outline: __[Plano de design](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/plan.md)__

    ---

    O design completo: a ideia de "uma árvore, múltiplos renderizadores", os três
    modos, e os trilhos N (capacidades), O (observabilidade) e P (PWA).

-   :material-map-outline: __[Roadmap fase-a-fase](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/roadmap.md)__

    ---

    A ordem das fases com "feito quando" testável em cada uma.

-   :material-vector-link: __[Contrato de fronteira](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/contract.md)__

    ---

    O wire format Python↔cliente, pinado por golden fixtures. O resumo didático
    está em [Contrato de fronteira](wire-contract.md).

-   :material-floor-plan: __[Arquitetura](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/arquitetura.md)__

    ---

    O documento canônico das camadas. A visão geral didática está em
    [Arquitetura](architecture.md).

</div>

## O que vem por aí

Os grandes blocos de trabalho, todos compartilhados pelos três modos:

| Trilho | Tema | Páginas aqui |
|---|---|---|
| **C** | Modo C — transpile (Python → JS nativo) | [Modo C — transpile](transpile.md) |
| **N** | Capacidades `native/` (Web APIs tipadas) | [Capacidades](capabilities.md) |
| **O** | Observabilidade / produção (adapter pattern) | [Observabilidade](observability.md) |
| **P** | PWA / offline-first / WebPush | [PWA e offline](pwa.md) |
| **B5** | Transporte SSE (alternativa ao WebSocket) | [Contrato de fronteira](wire-contract.md) |

!!! tip "A documentação acompanha o código"
    Conforme cada trilho entrega fases, as páginas correspondentes aqui saem de
    "em construção" para exemplos completos e testados. O
    [roadmap](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/roadmap.md)
    é o lugar para acompanhar o "feito quando" de cada fase.

## Recap

- Os docs de design são **vivos** e vivem no repositório (fonte da verdade).
- Esta documentação linka os originais e oferece **resumos didáticos** das partes
  estáveis.
- Os trilhos N/O/P têm páginas dedicadas aqui, atualizadas conforme entregam.

Quer começar a usar? Vá para a [Instalação](installation.md) e faça o
[Tutorial](tutorial/index.md). 🚀
