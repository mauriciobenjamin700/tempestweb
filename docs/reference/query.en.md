# `tempestweb.query`

The **read** side of remote data: a cache with hierarchical keys, prefix invalidation, single-flight, both pagination shapes, and optimistic mutation with an exact rollback. Modes A and B (Mode C refuses the import at build time). It does not replace [`native.sync`](../advanced/offline-sync.md), which is still the way to reconcile a large collection.

Tutorial with examples: [Reading remote data](../tutorial/query.md).

::: tempestweb.query
