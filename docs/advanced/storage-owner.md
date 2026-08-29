# Escopo do storage por dono

Duas pessoas podem usar o seu app **no mesmo navegador**. Um device de família,
um computador de recepção, um tablet compartilhado no balcão — ou só você, com
duas contas.

Quando isso acontece, o `native.storage` precisa saber de quem é cada chave.
Esta página mostra como dizer, o que acontece com o dado que já está gravado, e
por que a resposta não é automática.

## O problema, em três linhas

```python
# a Alice entra e salva um rascunho
await native.storage.put("rascunho", "minhas anotações")

# ela sai, o Bob entra no mesmo navegador
await native.storage.put("rascunho", "as anotações do Bob")

# a Alice volta
await native.storage.get("rascunho")   # "as anotações do Bob"
```

Sem escopo, a chave é só o nome. O `put` do Bob passou por cima do valor da
Alice, o `list_keys()` de cada um devolve as chaves dos dois, e o `remove` de um
alcança o dado do outro.

!!! danger "E não é só a chave que você escolhe"
    O cache persistido do [`query`](../tutorial/query.md) guarda respostas de API
    pelo mesmo caminho. Sem escopo, o boot do Bob enchia o `QueryCache` com
    **respostas que a Alice tinha persistido** — dado de servidor, aparecendo na
    tela de quem não pediu. Escopar o storage fecha isso sem uma linha de código
    no `query`.

## A correção: diga quem é o dono

```python
from tempestweb import native


async def ao_entrar(user_id: str) -> None:
    """Aponta o storage para o keyspace deste usuário."""
    await native.storage.configure(owner=user_id)
    await native.storage.put("rascunho", "minhas anotações")
```

Depois dessa chamada, todo `put`, `get`, `remove` e `list_keys` fica dentro do
keyspace daquele dono. O Bob não lê, não sobrescreve e não lista nada da Alice.

O `list_keys()` devolve o nome **como você escreveu**, sem o prefixo:

```python
await native.storage.configure(owner="alice")
await native.storage.put("rascunho", "a")
await native.storage.put("enviados", "b")

await native.storage.list_keys()   # ["enviados", "rascunho"]
```

!!! tip "Configure no boot, antes da primeira chamada"
    O dono é estado do módulo JS da aba. Ele sobrevive a uma reconexão de socket
    no Modo B, mas **não** a um reload de página — a app tem que reconfigurar no
    boot. Um `put` feito antes do `configure` grava no keyspace default, sem
    aviso, porque o framework não tem como saber que você "já devia" ter
    configurado.

## Por que você precisa passar o `owner`

Seria mais confortável se o framework descobrisse sozinho. Ele não pode:

- o **Modo A** roda inteiro no browser. Não há sessão, não há login do lado do
  servidor, não há nada de onde tirar uma identidade;
- o **Modo B** tem `session_id`, mas isso identifica um **transporte**, não uma
  pessoa: ele muda a cada reconexão. Keyar o storage por ele orfanaria o dado no
  primeiro socket que cair.

Quem sabe quem está logado é a sua app, depois do login. Por isso o `owner` é um
parâmetro, e não mágica.

## O dado que já está gravado

O dono default é a string vazia, e ele grava a chave **crua** — byte a byte o que
uma versão sem escopo gravava. Isso é deliberado, e tem uma consequência boa e
uma que exige atenção.

!!! check "A boa: nada quebra"
    Nada é reescrito, nada é migrado, nenhuma versão de banco se move. App que
    nunca chama `configure(owner=...)` não vê diferença nenhuma, e o dado que já
    está no disco continua exatamente onde está.

!!! warning "A que exige atenção: ligar o escopo abre um keyspace vazio"
    O dado antigo **não vem junto**. Ele continua legível pelo dono default, mas
    o `owner="alice"` começa do zero — porque só a sua app sabe de quem aquele
    dado era.

    Se você quer levar o legado para um dono, faça explicitamente:

    ```python
    from tempestweb import native


    async def adotar_legado(user_id: str) -> None:
        """Move o dado do keyspace default para o do usuário."""
        await native.storage.configure()
        legado = {
            nome: await native.storage.get(nome)
            for nome in await native.storage.list_keys()
        }
        await native.storage.configure(owner=user_id)
        for nome, conteudo in legado.items():
            await native.storage.put(nome, conteudo)
    ```

!!! danger "Não adote num device onde duas pessoas já usaram"
    Ali o keyspace default tem o dado das duas **misturado**, sem registro de
    quem é o quê — o store guarda `chave → valor`, e nada mais. Adotar entregaria
    o dado de uma para a outra.

    Pior: onde as duas escreveram a mesma chave, existe **um** valor, o de quem
    escreveu por último. O da primeira sumiu no dia em que foi sobrescrito, e
    nada aqui recupera isso — nem antes, nem depois desta mudança.

    Nesse caso, comece vazio.

## `configure` acerta os dois knobs

`configure` é a mesma função que escolhe o [codec de
compressão](storage-codec.md), e ela **sempre** define os dois:

```python
await native.storage.configure(codec="deflate", owner="alice")

await native.storage.configure(codec="deflate")   # ⚠️ o owner volta a ""
```

Uma regra só para a função inteira, igual ao que o codec já fazia. O custo é o
pé-na-jaca acima — reconfigurar um derruba o outro —, então **passe os dois
juntos**.

## Outra aba pode estar atualizando o app

Se outra aba estiver no meio de uma troca de versão do banco, uma chamada de
storage pode falhar com o código `blocked`:

```python
from tempestweb.native import NativeError


async def salvar(conteudo: str) -> None:
    """Salva, avisando se outra aba está atualizando o app."""
    try:
        await native.storage.put("rascunho", conteudo)
    except NativeError as erro:
        if erro.code == "blocked":
            print("Outra aba está atualizando o app. Tente de novo.")
        else:
            raise
```

Isso é diferente de um erro de escrita: o banco está lá e saudável, e a operação
volta a funcionar quando a outra aba fechar. Antes desta versão a chamada
simplesmente **nunca respondia**.

!!! info "E o código `stale`, que é o oposto"
    `blocked` diz "espere". `stale` diz **"recarregue"**: outra aba já subiu a
    versão do banco e esta página está rodando o build antigo. Tentar de novo não
    resolve — só carregar o código novo.

    Hoje ele é inalcançável (a versão do banco é `1` e nunca subiu). Ele existe
    para o dia do bump, e é o que impede aquele dia de fazer as abas antigas
    caírem para o `localStorage` em silêncio, partindo o dado do app entre dois
    backends.

## Recapitulando

- `configure(owner=...)` dá a cada pessoa o seu keyspace: sem leitura cruzada,
  sem sobrescrita, sem listar o dado alheio.
- O dono vem da sua app porque nem o Modo A nem o Modo B têm identidade de
  pessoa para oferecer.
- O default (`""`) grava chave crua, então **nada muda** para quem não usa.
- Ligar o escopo começa vazio de propósito; adotar o legado é uma decisão da app,
  e **não** se faz em device compartilhado.
- `configure()` define codec **e** dono — passe os dois juntos.
- `blocked` significa "outra aba está atualizando", não "a escrita falhou";
  `stale` significa "recarregue, este build está velho".
