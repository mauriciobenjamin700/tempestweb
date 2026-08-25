# Estabilidade & suporte

!!! abstract "O que você vai encontrar"
    O contrato de estabilidade rumo ao 1.0 (S10) e o **contrato do subset do
    Modo C** (S11): o que é público e estável, o que muda, quais browsers são
    suportados e onde está o baseline de acessibilidade.

## Versionamento (rumo a 1.0)

tempestweb é **pré-1.0** (`0.x`). Enquanto isso:

- **Superfície pública** = o que é importável de `tempestweb` e seus subpacotes
  documentados (`tempestweb.server`, `tempestweb.native`, `tempestweb.transpile`,
  `tempestweb.html`, `tempestweb.pwa`, `tempestweb.cli`) + o **wire-contract**
  ([`docs/contract.md`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/contract.md)). Nomes com `_` são privados.
- **Compatibilidade:** minor `0.x` pode conter mudanças de comportamento
  documentadas no [CHANGELOG](https://github.com/mauriciobenjamin700/tempestweb/blob/main/CHANGELOG.md).
  Fixe a versão em produção.
- **Depreciação (a partir do 1.0):** um recurso a ser removido ganha um aviso por
  pelo menos um minor antes de sair; removidos só em major.

## Matriz de browsers

| Browser | Modo A (WASM) | Modo B (servidor) | Modo C (transpile) |
|---|---|---|---|
| Chrome/Edge ≥ 111 | ✅ | ✅ | ✅ |
| Firefox ≥ 110 | ✅ | ✅ | ✅ |
| Safari ≥ 16.4 | ✅¹ | ✅ | ✅ |

Requisitos: ES modules + `fetch` + WebSocket/EventSource. PWA instalável precisa
de HTTPS; push no iOS exige o app **instalado** (Safari ≥ 16.4). ¹O boot do
Pyodide (Modo A) é mais pesado no Safari/mobile — prefira B ou C para
first-paint/SEO.

## Acessibilidade

O cliente emite HTML semântico com roles/aria a partir de `Widget.semantics`
(`aria-label`/`role`/`aria-description`), `tabindex` por `focus_order`, e usa
controles nativos (`<input>`/`<button>`) onde possível.

**O baseline é medido, não declarado.** O job `a11y` do CI roda **axe-core** sobre
o DOM que o renderizador de verdade constrói, para cenas geradas dos apps que este
repo entrega (`tests/conformance/_a11y_scenes.py` → `scripts/a11y-gate.mjs`), e
**trava o merge** em violação `serious` ou `critical`:

| O que o gate pega | O que ele não pega |
|---|---|
| controle sem nome acessível, imagem sem `alt`, `role` inválido, interativo aninhado, rótulo sem campo, `id` duplicado | contraste de cor e instalabilidade — precisam de layout real, e ficam na camada Lighthouse (`pwa.yml`) |

As cenas são **geradas**, não escritas à mão: a galeria de componentes do Modo C,
o painel de controles, uma lista com campo de texto, um formulário, uma casca de
navegação com gaveta e uma tela de imagens. Auditar markup escrito à mão provaria
que o exemplo do teste é acessível, não que o renderizador é.

A cobertura se mede por **tipo de widget e por componente**, e o segundo eixo tinha
um buraco: nove cenas e nenhuma usava os campos que são deste repo
(`TextField`/`EmailField`/`PasswordField` e os dois formulários). A cena
`login-form` parece usar e não usa — ela monta `EmailInput`/`PasswordInput` do core
dentro de um `FormField`, que o renderizador nomeia. Resultado: o `PasswordField`
entregou um controle anônimo (`label`, crítico) com o gate verde até a 0.113.0.
`login_demo` fecha esse eixo.

Regra que só pode ser afrouxada por escrito: uma regra do axe que não se aplica a
uma cena entra em `KNOWN_EXCEPTIONS` **com o motivo** (hoje: as quatro regras de
documento inteiro — `landmark-one-main`, `page-has-heading-one`, `region` — e
`color-contrast`, que é da camada Lighthouse). Silenciar sem motivo escrito é o que
transformou "baseline de a11y" em declaração vazia antes.

## O wire-contract é congelado

O wire-contract ([`docs/contract.md`](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/contract.md))
é parte da superfície estável, então ele tem **versão própria** — independente da
versão do pacote — em `tempestweb.contract`:

```python
from tempestweb.contract import WIRE_CONTRACT_VERSION, WIRE_SHAPE_DIGEST
```

As golden fixtures já travavam drift acidental, mas são **regeneráveis do core**:
elas não distinguem "regenerei porque o core mudou" de "mudei o contrato". O
`WIRE_SHAPE_DIGEST` distingue — ele é o hash da **forma** do fio (cada chave e seu
tipo, nunca o valor), então:

| Mudança | Digest | Versão | O que mais |
|---|---|---|---|
| fixture regenerada com valores novos | igual | igual | nada |
| chave opcional nova, `kind` de envelope novo, `type` de evento novo | muda | **igual** | entrada no CHANGELOG |
| chave renomeada/removida/retipada, semântica de patch alterada | muda | **bump** | nota de migração |

`tests/unit/test_wire_contract_freeze.py` reprova a mudança de forma e diz, na
mensagem, qual das duas escolhas o autor deve. Cliente de terceiro pinam
`WIRE_CONTRACT_VERSION` e sabem com o que estão falando.

## Contrato do subset do Modo C (S11)

O transpilador aceita um **subset tipado** de Python — estável e fail-loud
(`arquivo:linha` para o que estiver fora). Ver a lista completa no
[guia do Modo C](advanced/transpile.md#o-subset-suportado).

**Dentro (estável):** dataclasses (com herança/métodos/kwargs), `view()` +
closures de handler, aritmética completa, comparação encadeada, comprehensions
(lista/dict, com alvo em tupla), literais, slices, f-strings formatadas,
builtins comuns, métodos stdlib de string/list/dict, `if/for/while/break/
continue/try-except-finally/with/raise/assert`, unpacking, atribuição encadeada,
navegação/i18n/tema/animação/validators e todas as capacidades `native/`.

**Fora (por decisão):** `global`, `yield`/geradores, `del`, walrus (`:=`),
`raise ... from`, unpacking com estrela, decorators arbitrários (só
`@dataclass`), e a maior parte de `tempest_core.components` (composição Python
que expande via `build()` — use Modos A/B, ou primitivos/HStack/VStack no C). A
decisão de portar os components (camada de resolvers em JS) segue no
[roadmap](https://github.com/mauriciobenjamin700/tempestweb/blob/main/docs/roadmap.md) — S11.

!!! tip "Portabilidade A/B/C"
    Um `view()` no subset roda **idêntico** nos três modos. O `build --mode
    transpile` valida isso renderizando pelo core real — uma API só-do-Modo-C
    quebraria o build.

## Recap

- Pré-1.0: superfície pública documentada + wire-contract; fixe a versão.
- Browsers modernos (Chrome/Edge/Firefox/Safari recentes) nos três modos.
- a11y por semantics/roles; gate axe é follow-up.
- Subset do Modo C é um contrato estável e fail-loud; components ficam em A/B.
