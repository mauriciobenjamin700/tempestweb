# O canal de eventos nativo 📡

Algumas capacidades não respondem **uma** vez — elas emitem um **fluxo** de valores
ao longo do tempo. Esta página mostra como consumir esse fluxo com `async for`, como
ele mapeia no wire (subscribe → event → unsubscribe), e por que sair do laço é o que
cancela a assinatura. 🚀

## Single-shot não basta

A maioria das capacidades é **single-shot**: um pedido, um resultado. Você `await`
e segue a vida:

```python
from tempestweb import native

pos = await native.geolocation.get()   # um fix, e acabou
```

Mas "onde eu **estou** agora" é diferente de "para onde eu **estou indo**". Um app
de corrida, um mapa que segue o usuário, um velocímetro — todos precisam de leituras
**contínuas**. O mesmo vale para o nível de bateria, a orientação do dispositivo, o
estado da rede, a transcrição de fala. Fazer polling com `await` num laço seria
desperdício e perderia eventos entre uma chamada e outra.

Para isso existe o **canal de eventos nativo** (a fase **T-EV** do roadmap): um
fluxo tipado do cliente para o Python, exposto como um **async iterator**.

## O padrão `async for`

Toda capacidade de stream é um método que você percorre com `async for`. Cada
volta do laço entrega o próximo valor tipado:

```python
from tempestweb import native
from tempest_core import App


async def follow_me(app: App[object]) -> None:
    """Siga a posição do dispositivo até o app parar de consumir."""
    async for pos in native.geolocation.watch():
        app.set_state(lambda s: setattr(s, "here", (pos.latitude, pos.longitude)))
```

Leia devagar:

- `native.geolocation.watch()` **abre uma assinatura** e devolve um async iterator.
- Cada `pos` é um `Position` tipado — o **mesmo** tipo que `geolocation.get()`
  devolve no formato single-shot.
- O laço roda **enquanto houver eventos**. Ele não "termina" sozinho: você o
  encerra com `break`, deixando a função retornar, ou cancelando a task.

!!! tip "Streaming reaproveita os tipos single-shot"
    `watch()` entrega o **mesmo** modelo tipado da versão `get()`/`state()`. Você
    aprende o tipo uma vez e usa nos dois formatos.

As capacidades de stream de hoje:

| Capacidade | Percorre |
|---|---|
| `geolocation.watch()` | `Position` conforme o dispositivo se move |
| `sensors.orientation()` / `sensors.motion()` | leituras de giroscópio/acelerômetro |
| `network.watch()` | `NetworkState` a cada mudança de conexão |
| `visibility.watch()` | `"visible"`/`"hidden"` ao trocar de aba |
| `orientation.watch()` | `OrientationState` ao girar a tela |
| `battery.watch()` | `BatteryStatus` a cada mudança de carga |
| `speech.listen()` | `SpeechResult` (STT), interim e final |
| `idle.watch()` | `IdleState` quando o usuário fica inativo |
| `tabs.receive()` | mensagens transmitidas por outras abas |
| `gamepad.watch()` | snapshots dos controles conectados |
| `midi.messages()` | `MidiMessage` de qualquer porta de entrada |

## Como ele viaja no wire

Por baixo, o async iterator conversa três mensagens com o cliente. No **Modo B**
(servidor) elas atravessam o WebSocket/SSE; no **Modo A** (WASM) o `FFIBridge`
resolve em-processo com exatamente a mesma forma:

```json
// abre a assinatura
{ "kind": "native_subscribe", "sub_id": "s1", "capability": "geolocation.watch", "args": {"high_accuracy": true} }

// cada evento da assinatura (repete)
{ "kind": "native_event", "sub_id": "s1", "event": { "latitude": -23.5, "longitude": -46.6, "accuracy": 5.0 } }

// falha terminal, OU fim normal
{ "kind": "native_event", "sub_id": "s1", "error": "permission_denied", "message": "…" }
{ "kind": "native_event", "sub_id": "s1", "done": true }

// cancela a assinatura
{ "kind": "native_unsubscribe", "sub_id": "s1" }
```

O que o `async for` faz com cada uma:

- **`native_subscribe`** — emitido quando você entra no laço. O `sub_id` correlaciona
  a assinatura e todos os seus eventos (várias podem estar em voo ao mesmo tempo).
- **`native_event` com `event`** — vira o próximo valor entregue pelo `async for`.
- **`native_event` com `error`** — levanta um `NativeError` **dentro** do seu laço,
  encerrando a assinatura. Trate com `try/except`.
- **`native_event` com `done: true`** — encerra o laço normalmente (o iterator se
  esgota).
- **`native_unsubscribe`** — emitido **automaticamente** quando você sai do laço.

O formato canônico de cada campo está em
[`docs/contract.md`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/contract.md),
seção "Canal de eventos nativo (streaming, T-EV)" — e o cruzamento single-shot
irmão está no [contrato de fronteira](wire-contract.md#a-chamada-nativa-modo-b-proxy).

## Sair do laço cancela a assinatura

Este é o ponto mais importante — e o mais elegante. **Você nunca chama
`unsubscribe` à mão.** Sair do `async for` faz isso por você:

```python
from tempestweb import native
from tempest_core import App


async def follow_until_far(app: App[object]) -> None:
    """Para de seguir assim que o fix ficar preciso o bastante."""
    async for pos in native.geolocation.watch():
        app.set_state(lambda s: setattr(s, "here", pos))
        if pos.accuracy < 10.0:
            break   # ← isso dispara o native_unsubscribe; a assinatura fecha
```

O `native_events()` por trás dos `watch()` embrulha o laço em um `try/finally`: seja
qual for o motivo da saída — `break`, retorno da função, um `raise`, ou a task ser
**cancelada** —, o `finally` envia o `native_unsubscribe`. Sem assinaturas
vazadas, sem callbacks pendurados no browser.

!!! check "Cancelamento é limpeza"
    Se você guarda a task (`task = asyncio.create_task(follow_me(app))`) e depois
    `task.cancel()`, o `async for` levanta `CancelledError` no ponto do `await`, o
    `finally` roda, e a assinatura é fechada. Cancelar a task **é** a forma de parar
    o stream.

## Um stream precisa de alguém consumindo

Um `async for` só progride enquanto **alguém o percorre**. Abrir a corrotina e nunca
`await`-la (nem agendá-la como task) não assina coisa nenhuma — o gerador fica
parado.

!!! warning "Rode o stream numa task, não no meio de um `view()`"
    Nunca coloque um `async for` de stream **dentro** de `view()`: `view()` precisa
    retornar a árvore rápido e é chamado a cada render. Em vez disso, **inicie a
    consumção uma vez** (num handler, ou no bootstrap do app) e deixe-a rodar em uma
    task dedicada:

    ```python
    import asyncio

    from tempestweb import native
    from tempest_core import App


    async def start_following(app: App[object]) -> asyncio.Task[None]:
        """Inicie o stream de posição em uma task de fundo e guarde-a."""

        async def _loop() -> None:
            async for pos in native.geolocation.watch():
                app.set_state(lambda s: setattr(s, "here", pos))

        return asyncio.create_task(_loop())
    ```

    Guarde a `Task` no estado para poder `cancel()`-á-la quando a tela sair —
    fechando a assinatura de forma limpa.

## Recap

- Capacidades de **stream** entregam **muitos** eventos por assinatura; você as
  consome com `async for`, não com `await`.
- Cada `watch()`/`listen()`/`messages()`/`receive()` devolve um **async iterator
  tipado** que reaproveita os tipos do formato single-shot.
- No wire, o laço vira **subscribe → event\* → (error|done)**, com `sub_id`
  correlacionando tudo — idêntico no Modo A (in-process) e no Modo B (WS/SSE).
- **Sair do laço** (`break`, retorno, `raise`, cancelamento) dispara o
  `native_unsubscribe` automaticamente — você nunca limpa à mão.
- Um stream **precisa de um consumidor**: rode-o em uma task dedicada, fora do
  `view()`, e cancele a task para parar.

Veja a lista completa de streams na
[Referência de capacidades nativas](native-reference.md) e uma vitrine ao vivo no
[Painel do dispositivo](examples/device-panel.md). 🚀
