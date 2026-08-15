# `tempestweb.runtime`

The glue between the core and each execution mode: `AppSession` is Mode B's per-connection lifecycle, `WasmRuntime` drives Mode A's rebuild loop, and the serialization helpers lower the IR to the wire format. `spawn` lives here — it is how a handler moves long work off the session.

Guide with examples: [Wire contract](../advanced/wire-contract.md) · [Best practices](../tutorial/best-practices.md).

::: tempestweb.runtime
