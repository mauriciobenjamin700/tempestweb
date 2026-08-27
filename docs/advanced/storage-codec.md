# Comprimir o que fica no store (`native.storage.configure`)

!!! tip "O que você vai aprender"
    A decidir — **com número, não por reflexo** — se vale comprimir o que a sua
    app guarda no browser, e como ligar isso sem apagar o que já está no
    aparelho de quem usa. 📏

!!! danger "Meça a sua carga antes de ligar isso"
    Esta página existe porque a resposta intuitiva está errada. O ganho **não** é
    o que a taxa de compressão sugere, porque **o IndexedDB já comprime o que
    guarda**. Ligar o codec por reflexo troca CPU por bem menos disco do que
    parece.

!!! warning "Migração: o que a ≤0.122.0 gravou ficou no `localStorage`"
    Até a **0.122.0** o `native.storage` dos Modos A e B caía no `localStorage` —
    era o defeito que a 0.123.0 corrigiu. Da **0.123.0** em diante a leitura vai
    ao IndexedDB, então esse conteúdo antigo fica **órfão**: não é apagado, mas
    ninguém mais o lê, e a sua app volta a ver um store vazio.

    App nova não faz nada. App já publicada migra **uma vez**, na página do
    artefato, antes do boot — lendo o `localStorage` e reescrevendo por
    `storage.put`:

    ```html
    <script type="module">
      import { dispatch } from "./client/native/index.js";

      const MARCA = "tw.storage.migrated.v1";
      const LEGADO = ["notes", "draft", "cache"];  // as chaves da SUA app

      if (!localStorage.getItem(MARCA)) {
        let tudo_ok = true;
        for (const name of LEGADO) {
          const content = localStorage.getItem(name);
          if (content === null) continue;
          const escrita = await dispatch({
            kind: "native_call",
            call_id: `migrate-${name}`,
            capability: "storage.put",
            args: { name, content },
          });
          tudo_ok = tudo_ok && escrita.ok;
        }
        if (tudo_ok) localStorage.setItem(MARCA, "1");
      }
    </script>
    ```

    Liste as chaves **da sua app**: `Object.keys(localStorage)` varre também o que
    não é seu. E **não apague o original** — num perfil onde o IndexedDB não abre a
    capacidade continua gravando no próprio `localStorage`, o `put` reescreve a
    mesma chave, e um `removeItem` depois apagaria o dado que você acabou de
    salvar. A marca é o que evita reprocessar a cada boot.

## O que foi medido

Chrome 150 real, dirigido por Playwright, origem virgem, `CompressionStream("deflate")`.
Cada payload foi escrito duas vezes em bases separadas — uma como string, outra
como bytes deflatados — com `navigator.storage.estimate()` lido antes e depois,
esperando o valor assentar.

| Payload | Em memória | Deflate | **No disco, sem codec** | O IDB comprimiu sozinho |
| --- | --- | --- | --- | --- |
| catálogo, 5.000 itens | 976,9 KB | 120,6 KB | **222,1 KB** | **4,4×** |
| histórico repetitivo | 539,1 KB | 21,4 KB | **64,1 KB** | **8,4×** |
| ruído (base64 aleatório) | 143,6 KB | 93,6 KB | **126,5 KB** | 1,1× |

O codec não compete com texto cru: compete com o LevelDB por baixo do
IndexedDB. Então a economia real é o que sobra:

| Payload | Sem codec | Com codec | **Economia real** |
| --- | --- | --- | --- |
| catálogo, 5.000 itens | 222,1 KB | 122,1 KB | **−45,0%** |
| histórico repetitivo | 64,1 KB | 22,6 KB | **−64,8%** |
| ruído (base64) | 126,5 KB | 95,0 KB | **−24,9%** |

E o que custa, com a **CPU throttlada 6×** para aproximar um aparelho fraco. As
colunas são o que o codec **acrescenta** ao caminho que já existia:

| Payload | leitura + (1×) | leitura + (6×) | escrita + (1×) | escrita + (6×) |
| --- | --- | --- | --- | --- |
| fila de mutações (28 KB) | +0,3 ms | +2,8 ms | +0,8 ms | +4,8 ms |
| catálogo (~1 MB) | +2,1 ms | **+12,4 ms** | +13,0 ms | **+75,8 ms** |
| catálogo (~4 MB) | +6,1 ms | **+33,8 ms** | +49,7 ms | **+295,1 ms** |

## A conclusão, em uma linha

**Leitura é barata; escrita é que dói.** +12 ms por leitura para economizar 45%
de 1 MB é uma boa troca. 295 ms para escrever 4 MB num aparelho fraco é um frame
perdido que dá para ver.

| Ligue se | Não ligue se |
| --- | --- |
| a app guarda **dezenas de MB** de coleção repetitiva | a app guarda rascunho, fila e preferência |
| a escrita é rara (sincronizar catálogo uma vez por dia) | a escrita é quente (toda interação grava) |
| você mediu a **sua** carga e o número fechou | você está ligando "porque comprimir é bom" |

## Ligando

```python
from tempestweb import native
from tempestweb.native.storage import CODEC_DEFLATE


async def preparar_store() -> None:
    """Liga o codec e registra o que o browser conseguiu fazer."""
    resultado = await native.storage.configure(codec=CODEC_DEFLATE)
    print(resultado.requested, resultado.active, resultado.supported)
```

`configure` **nunca levanta** por falta de suporte. Ele responde três campos:

| Campo | O que diz |
| --- | --- |
| `requested` | o que você pediu |
| `active` | o que as próximas escritas vão usar de verdade |
| `supported` | se este browser consegue rodar o codec pedido |

!!! warning "Safari abaixo de 16.4 não tem `CompressionStream`"
    Nesse aparelho, `configure(codec="deflate")` responde
    `active="json", supported=False` e o store segue funcionando com texto. Um
    store que não comprime ainda é um store; uma exceção aqui seria uma tela
    morta num device real que a sua app precisa atender.

## Ligar e desligar não apaga nada

O ponto que torna a opção segura: **decodificar está sempre ligado; só codificar
é opt-in.** Um valor guardado carrega o nome do codec que o escreveu, então o
leitor nunca consulta a configuração atual.

| Situação | O que acontece |
| --- | --- |
| Registro escrito **antes** de ligar o codec | continua legível depois de ligar |
| Registro escrito **com** o codec, lido depois de desligar | continua legível |
| Envelope de um codec que este browser não lê | vira **cache miss** (`None`), não exceção |
| Bytes corrompidos | vira cache miss, não exceção |

As duas primeiras linhas foram medidas em Chrome real, escrevendo um catálogo de
565 KB:

```text
escrito com codec json      → guardado como string
escrito com codec deflate   → guardado como {$twcodec, bytes}, 21,6 KB
lê o registro antigo com o codec LIGADO      → intacto ✅
lê o registro comprimido com o codec DESLIGADO → intacto ✅
```

Sem essas duas, ligar a opção apagaria o cache de todo mundo que já está em
campo — em silêncio.

## O que fica de fora

- **A fila de mutações não é comprimida.** Ela é pequena, quente e crítica: não é
  onde a cota dói, e é onde a latência de escrita mais aparece. O codec vale para
  o `native.storage`, que é onde a coleção grande mora — inclusive o que o
  [`tempestweb.query`](../tutorial/query.md) persiste.
- **O `localStorage` de fallback não comprime.** Ele guarda string e não guarda
  bytes; onde o IndexedDB não existe, `active` volta `"json"`.
- **O esquema do store não muda.** Isto é codec, não migração.

## Recap

- O IndexedDB **já comprime**: o codec economiza 45–65% do que sobra, não 87%.
- Leitura custa pouco (+12 ms/MB num aparelho fraco); escrita custa muito
  (+76 ms/MB, +295 ms a 4 MB).
- Default `"json"`, opt-in por `native.storage.configure(codec="deflate")`.
- Codec sem suporte **cai para `"json"` e reporta**, nunca levanta.
- Ligar e desligar é seguro nos dois sentidos, porque decodificar está sempre
  ligado.
