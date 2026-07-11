# Referência de capacidades nativas 📇

Esta página cataloga **todos** os grupos de capacidade da ponte `tempestweb.native`
— um por seção, com uma frase de motivação e um trecho completo e executável. É a
referência de bolso do **Trilho T** (paridade com a plataforma web); para a
introdução didática ("uma API, três caminhos"), comece por
[Capacidades](capabilities.md).

!!! info "Uma importação para tudo"
    Todo exemplo abaixo começa com a mesma linha:

    ```python
    from tempestweb import native
    ```

    A partir daí você chama `native.<grupo>.<verbo>(...)`. A **assinatura é a
    mesma** nos Modos A (WASM), B (servidor) e C (transpile) — o `--mode` escolhe
    só como a chamada chega na Web API.

## `await` vs `async for` — dois formatos

Há **dois** formatos de capacidade, e você sabe qual é pela forma como consome:

=== "Single-shot — `await`"

    Um pedido, um resultado. A grande maioria das capacidades. Você `await` e
    recebe o valor tipado de volta.

    ```python
    from tempestweb import native

    online = await native.network.state()   # → NetworkState
    ```

=== "Streaming — `async for`"

    Uma assinatura, **muitos** eventos ao longo do tempo. Consumida com `async for`;
    sair do laço (fim, `break`, cancelamento) fecha a assinatura automaticamente.

    ```python
    from tempestweb import native

    async for pos in native.geolocation.watch():   # T-EV
        app.set_state(lambda s: setattr(s, "here", pos))
    ```

    As capacidades de stream correm sobre o **canal de eventos nativo (T-EV)** —
    veja o [tutorial do canal de eventos](native-events.md).

!!! warning "Contexto seguro e só-Chromium"
    Muitas capacidades exigem **HTTPS** (ou `localhost`) e algumas só existem no
    **Chromium** (Chrome/Edge). Cada grupo de risco expõe um `is_supported()` para
    você degradar com elegância — trate "não suportado" como fluxo normal, nunca
    como crash.

---

## Tier 1 — universal, barato, alto valor

Suporte amplo em todos os navegadores modernos. São a base da paridade PWA.

### `vibration` — vibrar o dispositivo

Dê um retorno tátil (buzz) em um toque ou em um padrão on/off.

```python
from tempestweb import native

async def on_success() -> None:
    await native.vibration.vibrate([100, 50, 100])   # ms: vibra, pausa, vibra
```

### `badge` — contador no ícone do PWA

Marque o ícone do app instalado com um número de não-lidos (ou um ponto genérico).

```python
from tempestweb import native

async def sync_badge(unread: int) -> None:
    if unread:
        await native.badge.set_badge(unread)   # 0 ou None também limpa
    else:
        await native.badge.clear()
```

### `wakelock` — manter a tela acesa

Impeça o desligamento da tela durante uma leitura, receita ou vídeo. Guarde o id
que `request()` devolve para liberar depois.

```python
from tempestweb import native

async def start_reading() -> str:
    lock_id = await native.wakelock.request()
    return lock_id

async def stop_reading(lock_id: str) -> None:
    await native.wakelock.release(lock_id)
```

### `fullscreen` — modo tela cheia

Entre e saia da tela cheia; leia o estado atual. Cada chamada devolve se a tela
cheia está ativa depois.

```python
from tempestweb import native

async def toggle_fullscreen() -> bool:
    if await native.fullscreen.state():
        await native.fullscreen.exit()
        return False
    return await native.fullscreen.enter()
```

### `network` — condições de conexão

Leia (`state`) ou observe (`watch`, streaming) `onLine`, `effectiveType`,
`downlink`, `rtt` e `saveData` — ideal para adaptar a UI a redes lentas.

```python
from tempestweb import native

async def read_network() -> None:
    net = await native.network.state()   # → NetworkState
    print(net.online, net.effective_type, net.save_data)

async def follow_network() -> None:
    async for net in native.network.watch():   # streaming (T-EV)
        app.set_state(lambda s: setattr(s, "online", net.online))
```

### `visibility` — aba em foco ou oculta

Saiba se a página está `"visible"` ou `"hidden"` — pause animações/polling quando
o usuário troca de aba.

```python
from tempestweb import native

async def pause_when_hidden() -> None:
    async for vis in native.visibility.watch():   # streaming (T-EV)
        app.set_state(lambda s: setattr(s, "playing", vis == "visible"))
```

### `orientation` — orientação da tela

Trave/destrave a orientação e leia o tipo/ângulo atuais; observe rotações em stream.

```python
from tempestweb import native

async def lock_landscape() -> bool:
    return await native.orientation.lock("landscape")   # requer fullscreen

async def follow_rotation() -> None:
    async for o in native.orientation.watch():   # streaming (T-EV)
        app.set_state(lambda s: setattr(s, "angle", o.angle))
```

### `quota` — uso e persistência de armazenamento

Estime uso/quota do origin e peça armazenamento **persistente** (isento de
despejo sob pressão). Pareia com [`storage`/`offline`](pwa.md).

```python
from tempestweb import native

async def ensure_durable() -> None:
    est = await native.quota.estimate()   # → StorageEstimate(usage, quota)
    if not await native.quota.persisted():
        await native.quota.persist()
```

### `clipboard` (imagem) — copiar/colar imagens

Além de `read`/`write` de texto, agora lê e escreve **imagens** (base64 + MIME).

```python
from tempestweb import native

async def paste_image() -> None:
    img = await native.clipboard.read_image()   # → ClipboardImage
    app.set_state(lambda s: setattr(s, "png_b64", img.data_base64))

async def copy_image(png_b64: str) -> None:
    await native.clipboard.write_image(png_b64, mime_type="image/png")
```

### `battery` — nível e carga (streaming)

Observe nível, estado de carga e tempos estimados. Só streaming — cada mudança
emite um `BatteryStatus` fresco.

```python
from tempestweb import native

async def follow_battery() -> None:
    async for b in native.battery.watch():   # streaming (T-EV)
        app.set_state(lambda s: setattr(s, "battery", b.level))
```

### `sensors` — orientação e movimento (streaming)

Leituras contínuas do acelerômetro/giroscópio via Device Orientation / Motion.

```python
from tempestweb import native

async def follow_tilt() -> None:
    async for o in native.sensors.orientation():   # streaming (T-EV)
        app.set_state(lambda s: setattr(s, "beta", o.beta))

async def follow_motion() -> None:
    async for m in native.sensors.motion():   # streaming (T-EV)
        app.set_state(lambda s: setattr(s, "accel", m.acceleration))
```

!!! warning "Permissão em iOS"
    Em Safari iOS, `deviceorientation`/`devicemotion` exigem permissão explícita
    concedida por um gesto do usuário. A assinatura levanta `NativeError`
    (`permission_denied`) quando negada — trate como fluxo normal.

---

## Tier 2 — muito usados

Bem suportados na maioria dos navegadores; alguns pedem permissão.

### `speech` — síntese (TTS) e reconhecimento (STT)

Fale texto em voz alta (single-shot) e liste vozes; reconheça fala em stream.

```python
from tempestweb import native

async def announce(text: str) -> None:
    await native.speech.speak(text, lang="pt-BR", rate=1.0)

async def dictate() -> None:
    async for r in native.speech.listen(lang="pt-BR"):   # streaming (T-EV)
        if r.is_final:
            app.set_state(lambda s: setattr(s, "said", r.transcript))
```

### `recorder` — gravar áudio, vídeo ou tela

Comece a gravar do microfone ou da tela; `stop` devolve os bytes em base64.

```python
from tempestweb import native

async def record_clip() -> None:
    rec_id = await native.recorder.start(source="microphone")
    # … usuário fala …
    recording = await native.recorder.stop(rec_id)   # → Recording
    app.set_state(lambda s: setattr(s, "clip_b64", recording.data_base64))
```

### `filesystem` — ler e gravar arquivos com handles vivos

Abra arquivos pelo seletor do sistema (com handle reutilizável para regravar) ou
crie um novo arquivo com o seletor de salvar.

```python
from tempestweb import native

async def open_and_edit() -> None:
    files = await native.filesystem.open_file(accept=".txt", multiple=False)
    if files:
        handle = files[0]                       # → FileHandle
        await native.filesystem.write_file(handle.id, handle.data_base64)

async def save_new(data_b64: str) -> None:
    await native.filesystem.save_file("export.bin", data_b64)
```

### `bgsync` — Background Sync + Periodic Sync

Registre trabalho que o service worker reexecuta quando a conexão volta (ou em um
intervalo periódico) — o motor por trás do replay real da fila offline.

```python
from tempestweb import native

async def queue_sync() -> None:
    await native.bgsync.register("outbox")
    await native.bgsync.register_periodic("refresh", min_interval_ms=3_600_000)
```

### `tabs` — sincronizar entre abas

Transmita mensagens entre abas (BroadcastChannel) e coordene com locks nomeados
(Web Locks). Receber mensagens é streaming.

```python
from tempestweb import native

async def broadcast_theme(theme: str) -> None:
    await native.tabs.broadcast("prefs", {"theme": theme})

async def follow_prefs() -> None:
    async for msg in native.tabs.receive("prefs"):   # streaming (T-EV)
        app.set_state(lambda s: setattr(s, "theme", msg["theme"]))
```

### `idle` — detecção de inatividade (streaming)

Saiba quando o usuário fica inativo ou a tela é bloqueada.

```python
from tempestweb import native

async def follow_idle() -> None:
    async for state in native.idle.watch(threshold_seconds=120):   # streaming (T-EV)
        app.set_state(lambda s: setattr(s, "away", state.user == "idle"))
```

---

## Tier 3 — nicho, secure-context, maioria só Chromium

Poderosas mas de suporte restrito. **Sempre** cheque `is_supported()` primeiro e
tenha um fallback.

!!! warning "Só Chromium + contexto seguro"
    Os grupos abaixo (com raras exceções) só existem no Chromium (Chrome/Edge),
    exigem **HTTPS** e a maioria abre um seletor do sistema que precisa de um
    gesto do usuário. Firefox/Safari costumam retornar `is_supported() == False`.

### `bluetooth` — Web Bluetooth (GATT)

Pareie um dispositivo BLE e leia/escreva características GATT.

```python
from tempestweb import native

async def read_heart_rate() -> str:
    if not await native.bluetooth.is_supported():
        return ""
    device = await native.bluetooth.request(
        optional_services=["heart_rate"],
    )                                            # → BluetoothDevice
    return await native.bluetooth.read(device.id, "heart_rate", "heart_rate_measurement")
```

### `usb` — WebUSB

Peça acesso a um dispositivo USB pelo seletor do navegador.

```python
from tempestweb import native

async def pick_usb() -> None:
    if await native.usb.is_supported():
        device = await native.usb.request(filters=[{"vendorId": 0x2341}])
        print(device.product_name, device.vendor_id)
```

### `serial` — Web Serial

Abra uma porta serial (Arduino, leitores, etc.); devolve um id opaco de porta.

```python
from tempestweb import native

async def pick_serial() -> str:
    if not await native.serial.is_supported():
        return ""
    return await native.serial.request(filters=[])
```

### `hid` — WebHID

Peça acesso a dispositivos HID (gamepads exóticos, teclados especiais).

```python
from tempestweb import native

async def pick_hid() -> list[dict[str, object]]:
    if not await native.hid.is_supported():
        return []
    return await native.hid.request(filters=[])
```

### `nfc` — Web NFC (escrita)

Grave registros NDEF em uma tag NFC próxima.

```python
from tempestweb import native

async def write_tag(url: str) -> None:
    if await native.nfc.is_supported():
        await native.nfc.write([{"recordType": "url", "data": url}])
```

!!! tip "Leitura de NFC (`scan`) — streaming (T-EV)"
    Além da escrita, o **scan** de tags é um stream contínuo pelo canal de eventos:

    ```python
    async for msg in native.nfc.scan():
        print(msg.serial_number, msg.records)
    ```

    Cada `NdefMessage` traz `serial_number` + `records` decodificados; sair do laço
    aborta o scan. Ver [Canal de eventos nativo](native-events.md).

### `contacts` — Contact Picker

Deixe o usuário escolher contatos pelo seletor do sistema (Android/Chrome).

```python
from tempestweb import native

async def pick_contact() -> list[dict[str, object]]:
    if not await native.contacts.is_supported():
        return []
    return await native.contacts.select(properties=["name", "tel"], multiple=False)
```

### `payment` — Payment Request API

Mostre a folha de pagamento nativa do navegador.

```python
from tempestweb import native

async def checkout() -> dict[str, object]:
    if not await native.payment.is_supported():
        return {}
    return await native.payment.request(
        methods=[{"supportedMethods": "https://example.com/pay"}],
        details={"total": {"label": "Total", "amount": {"currency": "BRL", "value": "9.90"}}},
    )
```

### `pip` — Picture-in-Picture

Solte um `<video>` numa janelinha flutuante.

```python
from tempestweb import native

async def pop_video() -> bool:
    return await native.pip.request(selector="video#player")

async def close_pip() -> None:
    await native.pip.exit()
```

### `eyedropper` — conta-gotas de cor

Deixe o usuário pegar uma cor de qualquer ponto da tela.

```python
from tempestweb import native

async def pick_color() -> str:
    return await native.eyedropper.open()   # → "#3366ff" (ou "" se cancelado)
```

### `pointerlock` — travar o ponteiro

Capture o mouse (jogos, visualizadores 3D), escondendo o cursor.

```python
from tempestweb import native

async def start_game() -> None:
    await native.pointerlock.request(selector="#canvas")

async def end_game() -> None:
    await native.pointerlock.exit()
```

### `gamepad` — Gamepad API

Leia um snapshot (`state`) ou observe os controles em stream (`watch`).

```python
from tempestweb import native

async def read_pads() -> list[dict[str, object]]:
    return await native.gamepad.state()

async def follow_pads() -> None:
    async for pads in native.gamepad.watch():   # streaming (T-EV)
        app.set_state(lambda s: setattr(s, "pads", pads))
```

### `midi` — Web MIDI

Enumere portas, envie mensagens e escute mensagens de entrada em stream.

```python
from tempestweb import native

async def play_note() -> None:
    if not await native.midi.is_supported():
        return
    ports = await native.midi.request_access()   # → MidiPorts
    if ports.outputs:
        await native.midi.send(ports.outputs[0]["id"], [0x90, 60, 0x7F])

async def follow_midi() -> None:
    async for msg in native.midi.messages():   # streaming (T-EV)
        app.set_state(lambda s: s.notes.append(msg.data))
```

### `webaudio` — tom sintetizado

Toque um "beep" sem precisar de um asset de áudio (diferente de `audio.play`).

```python
from tempestweb import native

async def beep() -> None:
    await native.webaudio.tone(frequency=880.0, duration_ms=150, type="sine")
```

---

## Recap

- **Uma importação** (`from tempestweb import native`) e a mesma assinatura nos
  três modos.
- **Dois formatos:** single-shot com `await`, streaming com `async for` (sobre o
  [canal de eventos T-EV](native-events.md)).
- **Tier 1** é universal; **Tier 2** é muito usado; **Tier 3** é só-Chromium/
  secure-context e sempre traz `is_supported()` + fallback.
- Streams (`geolocation.watch`, `sensors.*`, `network.watch`, `visibility.watch`,
  `orientation.watch`, `battery.watch`, `speech.listen`, `idle.watch`,
  `tabs.receive`, `gamepad.watch`, `midi.messages`, `nfc.scan`) fecham a assinatura
  ao sair do laço.
- O Trilho T está **completo**, sem lacunas de capacidade conhecidas.

Veja a ponte em ação no [Painel do dispositivo](examples/device-panel.md) e o
formato de wire das chamadas em
[`docs/contract.md`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/contract.md). 🚀
