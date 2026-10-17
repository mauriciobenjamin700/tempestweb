# Boot e cache do Modo A

!!! abstract "O que você vai aprender"
    O que acontece entre o usuário abrir a URL e o seu `view()` aparecer no Modo A
    (WASM/Pyodide), como deixar esse tempo **visível** com a tela de carregamento,
    e como um servidor usa o `immutable.json` para não baixar de novo o que não
    mudou.

No Modo A o Python roda **dentro do browser**. Antes da primeira tela, a página
precisa de: o runtime Pyodide (~6 MB), as wheels do `pydantic`, o pacote Python do
tempestweb + o seu `app.py`, e o cliente JS que desenha o DOM. Num celular com
4G isso leva segundos — e, até a 0.140, a página ficava **em branco** o tempo
todo. 😬

## O que o build gera

```bash
tempestweb build --mode wasm
```

```text
dist/wasm/
├── index.html                          ← revalidado (no-cache)
├── bootstrap.js                        ← revalidado
├── app.py                              ← revalidado
├── immutable.json                      ← o contrato de cache (abaixo)
├── client-3f9c0a1b2c4d5e6f/
│   └── tempestweb-wasm.js              ← o cliente inteiro, um arquivo, imutável
├── tempestweb-pkg.8c1d0e2f3a4b5c6d.zip ← o payload Python, imutável
├── manifest.webmanifest, sw.js, icons/ ← camada PWA
└── client/offline/{store,sync}.js      ← só com o service worker ligado
```

Três coisas mudaram em relação ao layout antigo, e cada uma ataca um pedaço do
tempo de boot.

### 1. O cliente é **um** arquivo

Antes, o `bootstrap.js` importava estaticamente uma árvore de **81 módulos**
(~600 KB) e o browser precisava resolver a árvore inteira antes de executar uma
linha — só então o Pyodide começava a baixar. Agora o build copia um bundle
único, `tempestweb-wasm.js` (~190 KB, ~60 KB com gzip), gerado na hora do
release.

!!! info "Detalhes técnicos — de onde vem o bundle"
    O bundle é gerado por `scripts/bundle-client.mjs` (esbuild, uma
    devDependency npm **fixada**) e commitado em `client/bundle/`. O `tempestweb
    build` só copia o arquivo: o esbuild nunca entra nas dependências do pacote
    Python. Os módulos em `client/` continuam sendo JavaScript puro, sem etapa de
    build — o Modo B, o Modo C e os testes leem os fontes direto.

    O `tempestweb dev` usa os fontes (`client/wasm-entry.js`), não o bundle:
    editar um módulo do cliente aparece no próximo reload sem rebundlar.

### 2. Tudo baixa ao mesmo tempo

O `bootstrap.js` não tem mais `import` estático. Antes do primeiro `await` ele
dispara, em paralelo:

- o Pyodide (`pyodide.mjs` → `.wasm` + stdlib);
- as wheels que o `loadPackage` vai pedir (lidas do mesmo `pyodide-lock.json`,
  pela mesma URL, então o `loadPackage` as encontra no cache HTTP);
- o payload Python e o `app.py`;
- o bundle do cliente.

E o `index.html` já nomeia tudo isso em `<link rel="preload">` /
`<link rel="modulepreload">`, então os downloads começam enquanto o HTML ainda
está sendo lido. Depois, o boot consome cada promessa na mesma ordem de sempre —
o lado Python não mudou.

### 3. Nomes com hash de conteúdo

O bundle mora em `client-<hash>/` e o payload se chama
`tempestweb-pkg.<hash>.zip`, onde `<hash>` são os 16 primeiros dígitos hex do
SHA-256 **do próprio arquivo**. O nome muda exatamente quando o conteúdo muda —
então o servidor pode mandar o browser guardá-los por um ano sem nunca
perguntar de novo.

!!! note "Por que hash de conteúdo, e não a versão do tempestweb?"
    O bundle só muda com a versão, mas o payload não: ele carrega os
    `[wasm] modules` do seu app e o que o empacotamento decide incluir. Hash do
    conteúdo serve para os dois e nunca mente.

## O contrato `immutable.json`

O build escreve na raiz do artefato:

```json
{
  "immutable": [
    "client-3f9c0a1b2c4d5e6f/**",
    "tempestweb-pkg.8c1d0e2f3a4b5c6d.zip"
  ],
  "generator": "tempestweb 0.141.0"
}
```

É o formato que o `make_web_app_router` do
[tempest-fastapi-sdk](https://pypi.org/project/tempest-fastapi-sdk/) lê:

| Regra | Valor |
| --- | --- |
| Arquivo | `immutable.json`, na raiz do build |
| `immutable` | lista de globs relativos à raiz |
| `**` | atravessa diretórios |
| `*`, `?` | casam dentro de um segmento (não atravessam `/`) |
| O que casa | `Cache-Control: public, max-age=31536000, immutable` |
| O resto | `no-cache` (revalidado por ETag) |
| Outras chaves | ignoradas (`generator` é só para quem lê à mão) |

O servidor **nunca** marca como imutável `index.html`, `bootstrap.js`, `sw.js`,
`register.js`, `manifest.webmanifest` nem o próprio `immutable.json`, mesmo que
casem com um glob. Eles têm nome fixo e apontam para os nomes com hash — por isso
continuam revalidados, e um deploy novo aparece no próximo acesso.

!!! tip "Servindo sem o SDK"
    Qualquer servidor serve: leia o `immutable.json` uma vez no boot e aplique o
    header por caminho. No nginx, uma `location ~ ^/client-[0-9a-f]{16}/` e uma
    `location ~ ^/tempestweb-pkg\.[0-9a-f]{16}\.zip$` com
    `add_header Cache-Control "public, max-age=31536000, immutable";` fazem o
    mesmo.

## A tela de carregamento

O `index.html` gerado já abre com uma tela de carregamento em **HTML e CSS
puros** — pintada no primeiro frame, antes de qualquer script, WASM ou fonte.
Ela segue o `prefers-color-scheme` (claro/escuro), desacelera o spinner com
`prefers-reduced-motion` e anda por três estágios:

| Estágio | Quando | Texto padrão |
| --- | --- | --- |
| `runtime` | baixando o Pyodide | `Downloading the runtime…` |
| `python` | Python subindo, wheels e payload carregando | `Starting Python…` |
| `app` | importando o `app.py` e montando a primeira tela | `Building the app…` |

Quando o app monta, a tela some. Se o boot falha, ela **fica**, para de girar e
mostra o erro — em vez de uma página em branco ou um spinner eterno.

Personalize em `tempestweb.toml`:

```toml
[loading]
title = "Meu Painel"                  # padrão: [pwa] name, depois o nome do projeto
runtime_text = "Baixando o runtime…"
python_text = "Iniciando o Python…"
app_text = "Montando o app…"
error_text = "O app não conseguiu iniciar."
background = "#0b1220"                # opcional: vale nos dois esquemas
foreground = "#e6e8eb"
accent = "#4f8cff"                    # cor do spinner e dos pontos
```

Ou desligue:

```toml
[loading]
enabled = false
```

!!! warning "Chave errada é erro, não silêncio"
    Uma chave que a tela não conhece (`enable = false`, sem o `d`) derruba o
    build com `ConfigError` listando as chaves válidas. Uma cor com `;`, chave,
    aspas ou `<` também — ela é escrita dentro de um `<style>`.

## Quanto isso ganha

Medido no painel do tempest-webtunnel, celular 390×844, Fast 4G, CPU 4× mais
lenta, Pyodide v314 do jsDelivr, servidor respondendo `no-cache`:

| | Antes (0.139.0) | Depois |
| --- | --- | --- |
| Requisições | 95 (85 da própria origem) | 22 (6 da própria origem) |
| JS do cliente | 81 módulos, ~600 KB | 1 arquivo, ~190 KB |
| Início do download do Pyodide | 2,9 s | 0,2 s |
| App montado — frio | 34,8 s | 33,4 s |
| App montado — quente (3 execuções) | 26,1–27,3 s | 23,3–23,9 s |
| Primeiro pixel | página em branco até montar | tela de carregamento no 1º frame |

!!! note "Leia os números com honestidade"
    O ganho de tempo total é de alguns segundos, não dezenas: o boot frio é
    dominado por **CPU** — compilar o WASM do Pyodide (~17 s nessa máquina) e
    importar o app em Python. O que esta página resolve é o tempo de **rede e de
    espera em série**, mais o fato de a espera agora ser visível. A medição foi
    feita numa máquina compartilhada; os valores variam entre execuções, então
    as comparações acima são pares medidos lado a lado.

## Recap

- O cliente do Modo A é **um** arquivo, gerado no release e copiado pelo build.
- O `bootstrap.js` dispara **todos** os downloads antes do primeiro `await`, e o
  `index.html` os antecipa com preload.
- Nomes com hash de conteúdo + `immutable.json` deixam o servidor cachear o
  pesado por um ano, enquanto `index.html`/`bootstrap.js`/`app.py` seguem
  revalidados.
- A tela de carregamento aparece no primeiro frame, mostra o estágio, mostra o
  erro quando falha e se configura em `[loading]`. 🚀
