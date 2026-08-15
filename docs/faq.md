# Perguntas frequentes

!!! abstract "O que está aqui"
    Perguntas de **decisão** — as que aparecem antes de escrever código, ou na
    hora de escolher um caminho. Cada resposta é curta e aponta para a página que
    desenvolve o assunto. Se o seu problema é uma **mensagem de erro**, o lugar é
    [Quando dá errado](troubleshooting.md).

## Qual modo eu escolho?

Você não decide isso no código — a mesma `view()` roda nos três. Decide no
`build --mode`:

- **Site ou PWA público**, que precisa de SEO e first-paint rápido, sem servidor
  → **Modo C (transpile)**.
- **Lógica ou estado no servidor** — dados ao vivo, segredos, banco → **Modo B**.
- **Python vivo no browser**, para prototipar ou rodar bibliotecas Python do lado
  do cliente → **Modo A (WASM)**.

Painel interno e app logado quase sempre são **Modo B**. Veja
[Rodando os modos](tutorial/modes.md).

## Preciso saber CSS ou front-end?

Não, se a sua tela for um arquétipo. As
[telas prontas (presets)](tutorial/presets.md) montam painel, dashboard,
listagem, formulário e login a partir de dados tipados, e já saem responsivas.
Um painel completo sai em ~260 linhas sem um `Style` escrito à mão — o
[Console Administrativo](examples/admin-console.md) é o exemplo inteiro.

Para telas específicas do seu produto, aí sim você monta com widgets, e o estilo
é um objeto `Style` tipado — não uma folha CSS com cascata.

## Posso usar qualquer biblioteca Python?

Depende do modo:

- **Modo B** — sim. É Python no servidor: use o que quiser, do SQLAlchemy ao
  pandas.
- **Modo A** — o que o Pyodide conseguir instalar. Pacotes Python puro
  costumam ir; pacotes com extensão C precisam de build para WASM.
- **Modo C** — não. Só `tempest_core` e `tempestweb.native` atravessam o
  transpilador; a camada de app vira JavaScript.

## Por que meu app não transpila para o Modo C?

Porque ele usa algo fora do subconjunto suportado, e o compilador diz o quê e
onde, com `file:line`. Os motivos mais comuns são um `import` de fora de
`tempest_core`/`tempestweb.native` (o que inclui `presets` e `components`),
`*args`/`**kwargs`, e decoradores de função. A lista completa e o que fazer em
cada caso estão em [Modo C — transpile](advanced/transpile.md).

## Preciso de sticky session no Modo B?

Para **WebSocket**, não: a conexão é uma só e carrega a sessão inteira. Para
**SSE**, sim por padrão — o stream sai por uma conexão e os eventos entram por
outra (`POST /sse/{id}`), e as duas precisam cair na mesma réplica. Se isso for
um problema na sua infraestrutura, o `RedisSessionRouter` roteia o inbound por
pub/sub e dispensa a afinidade. Veja
[Escala horizontal](advanced/deploy.md#escala-horizontal-s4).

## Dá para usar uma folha CSS minha?

O estilo do framework é **inline tipado** (`Style`), não uma cascata — foi uma
decisão de projeto, para que a mesma árvore renderize no DOM e em telas nativas.
Mas nada impede uma folha sua: os presets emitem marcadores `data-tw-layout` e
todo widget aceita `attrs`, então você tem seletores estáveis para mirar. Veja
[Tema](tutorial/theming.md).

## Como isso se compara a Streamlit, Reflex ou PyScript?

Em uma frase cada:

- **Streamlit** reexecuta o script inteiro a cada interação e é ótimo para data
  apps; o tempestweb tem árvore declarativa com reconciliação, então o estado e
  o foco sobrevivem à interação.
- **Reflex** compila para React e traz o ecossistema React junto; o tempestweb
  não tem framework JS nenhum — o cliente é JavaScript puro, sem passo de build.
- **PyScript** é o parente mais próximo do **Modo A**, mas é só esse modo; aqui
  o mesmo app também roda no servidor e também vira bundle estático.

O que nenhum dos três oferece é a mesma `view()` valendo nos três modos sem
alterar uma linha.

## Serve para um site público, com SEO?

Sim, no **Modo C**: o app vira JavaScript nativo e um bundle estático que
qualquer CDN serve, com first-paint bom. Para conteúdo indexável já no HTML, há
[SSR estático](advanced/ssr.md).

O Modo A não é para isso — carregar o Pyodide custa caro no primeiro acesso.

## Está pronto para produção?

Os três modos funcionam e o gate cobre todos. Ainda é `0.x`, então uma minor
pode trazer mudança de comportamento — documentada no CHANGELOG. O que é público
e o que é privado está definido em [Estabilidade](stability.md).

## Recapitulando

- O **modo** é escolha de build, não de código.
- **Presets** cobrem o caminho de quem não é front-end.
- **Modo C** é o mais restrito e o mais rápido; **Modo B** é o mais livre.
- Erro na tela? [Quando dá errado](troubleshooting.md).
