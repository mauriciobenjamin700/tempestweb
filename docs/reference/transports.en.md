# `tempestweb.transports`

The **only** seam separating Mode A from Mode B. `PatchTransport` is the Protocol both implement; above it the app's `view()` is identical, below it the JS client is the same. You rarely import from here — unless you are writing a transport of your own.

Guide with examples: [Architecture](../architecture.md) · [Wire contract](../advanced/wire-contract.md).

::: tempestweb.transports
