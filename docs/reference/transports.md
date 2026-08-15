# `tempestweb.transports`

A **única** costura que separa o Modo A do Modo B. O `PatchTransport` é o Protocol que os dois implementam; acima dele o `view()` do app é idêntico, abaixo o cliente JS é o mesmo. Você raramente importa daqui — a não ser para escrever um transporte seu.

Guia com exemplos: [Arquitetura](../architecture.md) · [Contrato de fronteira](../advanced/wire-contract.md).

::: tempestweb.transports
