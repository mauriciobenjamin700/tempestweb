# `tempestweb.runtime`

A cola entre o core e cada modo de execução: `AppSession` é o ciclo de vida por conexão do Modo B, `WasmRuntime` conduz o loop de rebuild no Modo A, e os helpers de serialização baixam a IR para o formato de fronteira. `spawn` mora aqui — é como um handler tira trabalho longo de cima da sessão.

Guia com exemplos: [Contrato de fronteira](../advanced/wire-contract.md) · [Boas práticas](../tutorial/best-practices.md).

::: tempestweb.runtime
