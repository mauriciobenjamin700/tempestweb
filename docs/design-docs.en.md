# Roadmap & design docs

tempestweb keeps a set of **living design documents** versioned next to the code.
This page is their index — it links the originals on GitHub, which are the source
of truth.

!!! info "Why these docs live in the repository"
    They use relative links to the code and the fixtures, and change every phase.
    Keeping them in the repo (and not rebuilt here) guarantees they stay in sync
    with what was implemented.

## The documents

<div class="grid cards" markdown>

-   :material-file-document-outline: __[Design plan](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/plan.md)__

    ---

    The complete design: the "one tree, multiple renderers" idea, the three modes,
    and tracks N (capabilities), O (observability) and P (PWA).

-   :material-map-outline: __[Phase-by-phase roadmap](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/roadmap.md)__

    ---

    The order of phases with a testable "done when" for each.

-   :material-vector-link: __[Wire contract](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/contract.md)__

    ---

    The Python↔client wire format, pinned by golden fixtures. The didactic summary
    is in [Wire contract](wire-contract.md).

-   :material-floor-plan: __[Architecture](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/arquitetura.md)__

    ---

    The canonical layers document. The didactic overview is in
    [Architecture](architecture.md).

</div>

## What's coming

The big blocks of work, all shared by the three modes:

| Track | Theme | Pages here |
|---|---|---|
| **C** | Mode C — transpile (Python → native JS) | [Mode C — transpile](transpile.md) |
| **N** | `native/` capabilities (typed Web APIs) | [Capabilities](capabilities.md) |
| **O** | Observability / production (adapter pattern) | [Observability](observability.md) |
| **P** | PWA / offline-first / WebPush | [PWA & offline](pwa.md) |
| **B5** | SSE transport (alternative to WebSocket) | [Wire contract](wire-contract.md) |

!!! tip "Documentation follows the code"
    As each track ships phases, the corresponding pages here move from "under
    construction" to complete, tested examples. The
    [roadmap](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/roadmap.md)
    is the place to track each phase's "done when".

## Recap

- The design docs are **living** and live in the repository (source of truth).
- This documentation links the originals and offers **didactic summaries** of the
  stable parts.
- Tracks N/O/P have dedicated pages here, updated as they ship.

Want to start using it? Head to the [Installation](installation.md) and do the
[Tutorial](tutorial/index.md). 🚀
