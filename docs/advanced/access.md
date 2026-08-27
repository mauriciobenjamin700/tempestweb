# Permissões na view (`tempestweb.access`)

!!! tip "O que você vai aprender"
    A decidir **o que a tela desenha** a partir das permissões que o usuário
    carrega — sem espalhar `if state.role == "admin"` pela `view` e sem ler o
    JWT com `json.loads` num canto qualquer. 🚀

!!! danger "Antes de tudo: esconder um botão **não é** controle de acesso"
    Tudo nesta página roda onde o usuário pode mexer. Uma tela que não desenha o
    botão "Excluir" continua na frente de um endpoint que exclui, e chegar nesse
    endpoint precisa de um terminal, não de um exploit.

    | Onde | Decide | Com o quê |
    | --- | --- | --- |
    | **Servidor** (`tempest-fastapi-sdk`) | se a requisição **pode** acontecer | a chave de assinatura |
    | **Aqui** | se o botão **é desenhado** | claims que ninguém verificou |

    Se o servidor não impede, **não está impedido**. Isto aqui é experiência de
    uso: não mostrar ao usuário uma ação que ele receberia 403 ao tentar.

## O problema

```python
# ❌ A condição espalhada pela view
if app.state.role == "admin":
    children.append(Button(label="Excluir", key="del", on_click=delete))
...
if app.state.role == "admin":
    children.append(audit_panel(app))
```

No dia em que existir um segundo papel privilegiado, você precisa achar todos os
`if`. E na primeira vez que alguém quiser "admin pode tudo em usuários", nasce um
`startswith("users:")` — escrito de um jeito num arquivo e de outro no seguinte.

## O mapa, num lugar só

```python
from tempestweb.access import AccessControl

ACCESS = AccessControl(
    roles={
        "admin": ["users:*", "audit:read"],
        "viewer": ["users:read"],
    }
)
```

E a `view` pergunta:

```python
from tempest_core import App, Button, Column, Widget

from tempestweb.access import AccessControl

ACCESS = AccessControl(
    roles={"admin": ["users:*", "audit:read"], "viewer": ["users:read"]}
)


def view(app: App[State]) -> Widget:
    """Desenha a lista, com Excluir só para quem pode excluir."""
    access = ACCESS.for_roles(app.state.roles)
    children: list[Widget] = [user_list(app)]
    if access.can("users:delete"):
        children.append(Button(label="Excluir", key="del", on_click=delete))
    return Column(key="body", children=children)
```

## O curinga

Um separador (`:`) e um curinga **no fim**. Nada de glob.

| Concedido | Pedido | Resultado |
| --- | --- | --- |
| `users:*` | `users:delete` | ✅ |
| `users:*` | `users:a:b` | ✅ |
| `users:*` | `audit:read` | ❌ outro prefixo |
| `users:*` | `users` | ❌ é outra permissão, não uma mais rasa |
| `users:read` | `users:*` | ❌ ler não é poder tudo |
| `*` | qualquer coisa | ✅ o papel de superusuário |

Três perguntas, além do `can`:

```python
access.can("users:delete")                      # uma
access.can_any("users:delete", "audit:read")    # pelo menos uma
access.can_all("users:read", "audit:read")      # todas
```

!!! note "`can_all()` sem argumento é `True`; `can_any()` sem argumento é `False`"
    Uma tela que declara `requires = []` precisa renderizar. Uma tela que
    pergunta "pode alguma de []" não pode ganhar nada. As duas respostas são o
    contrário uma da outra, e as duas estão certas.

## Lendo o token

```python
from tempestweb.access import unverified_access_from_token

claims = unverified_access_from_token(token)
claims.roles         # ('admin',)
claims.permissions   # ('audit:read',)  — inclui os scopes de OAuth
claims.is_expired(now=time.time())
```

E o passo que junta os dois — papéis expandidos **mais** as permissões diretas:

```python
access = ACCESS.for_token(unverified_access_from_token(token))
```

### O nome diz `unverified` de propósito

!!! danger "A assinatura **não** é verificada, e isso é o desenho"
    No Modo A a app roda no browser: a chave de assinatura estaria no browser
    junto. Não há com o que verificar. Quem verifica é o servidor, com o
    `tempest-fastapi-sdk`, antes de a requisição chegar em qualquer lugar.

    Um token com assinatura forjada **decodifica normalmente** aqui — de
    propósito. Recusar alguns tokens sugeriria que os aceitos foram conferidos.
    Não foram: qualquer pessoa entrega ao próprio browser um token dizendo
    `roles: ["admin"]`. A única coisa que essa decisão muda é qual botão a tela
    pinta.

    O `unverified_` no nome existe para aparecer em toda chamada, onde quem
    revisa o código vê.

Isso está fixado por teste (`test_a_forged_signature_still_decodes_on_purpose`):
no dia em que alguém "consertar" adicionando verificação, o teste reprova e
explica por quê.

### Token expirado reporta, não levanta

```python
if claims.is_expired(now=time.time()):
    await refresh()
```

Expirar é estado comum, tratado com refresh — não é exceção. E um token **sem**
`exp` não expira: `is_expired` devolve `False`.

!!! info "`now` é parâmetro, não relógio escondido"
    `is_expired(now=...)` recebe o tempo em vez de ler `time.time()` por dentro:
    quem chama é dono da fonte de tempo, e um teste fixa a expiração sem congelar
    relógio nenhum.

### Servidor que nomeia os claims de outro jeito

```python
from tempestweb.access import ClaimNames, unverified_access_from_token

claims = unverified_access_from_token(
    token, claims=ClaimNames(roles="grupos", permissions="escopos")
)
```

O claim `scope` do OAuth 2.0 é sempre lido junto, separado por espaço, como
manda a especificação.

## Quando o claim vem torto

Um claim com forma inesperada — número onde deveria ter lista, objeto aninhado,
`null` — **não derruba a tela**: contribui nada. O pior caso é um botão a menos,
que o usuário resolve recarregando; uma exceção na `view` é uma tela branca.

O mesmo vale para papel desconhecido:

```python
ACCESS.for_roles(["papel-que-o-servidor-inventou-ontem"]).can("users:read")
# False, sem levantar
```

O servidor pode ganhar um papel antes de a app modelá-lo, e app que quebra com
papel novo é pior que app que esconde um botão. Quem quiser notar tem
`ACCESS.known_roles`.

## Deslogado

```python
from tempestweb.access import NO_ACCESS

access = ACCESS.for_token(claims) if app.state.token else NO_ACCESS
```

`NO_ACCESS` responde `False` a tudo. É melhor default que `None`, que
levantaria `AttributeError` na primeira `view` que esquecesse de checar.

## Modos A e B

!!! warning "O Modo C recusa este import"
    O Modo C transcreve o Python da sua app para JavaScript e serve um conjunto
    fechado de módulos — `tempest_core`, `tempestweb.components` e
    `tempestweb.native`. Uma app Modo C que importe `tempestweb.access` é
    **recusada no build**, com erro nomeado:

    ```text
    app.py:5: import from 'tempestweb.access' is not supported
    (only tempest_core, `tempestweb.components` and `tempestweb.native`)
    ```

    Numa app Modo C, o servidor manda junto o que a tela pode desenhar — o que,
    aliás, é a forma mais honesta: a decisão vem de quem tem a chave.

## Fora de escopo

- **Verificar assinatura de JWT no cliente.** No Modo A o segredo estaria no
  browser. Quem valida é o servidor.
- **Papel dinâmico vindo de serviço externo.** Isso é feature flag, e já existe
  em [`tempestweb.observability`](observability.md).

## Recap

- `AccessControl(roles={...})` guarda o mapa papel → permissão **uma vez**.
- `for_roles` / `for_permissions` / `for_token` resolvem; `for_token` é a que a
  app usa, porque une papéis expandidos com permissões diretas.
- `access.can(...)`, `can_any(...)`, `can_all(...)` são o que a `view` pergunta.
- `users:*` cobre `users:delete`, não cobre `audit:read` nem `users`.
- `unverified_access_from_token` **não** verifica assinatura, e o nome diz isso
  em toda chamada.
- Nada disto é autorização. O servidor decide; isto desenha.
- Modo A e Modo B. O Modo C recusa o import no build.
