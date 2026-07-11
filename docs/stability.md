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
  ([`docs/contract.md`](contract.md)). Nomes com `_` são privados.
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
controles nativos (`<input>`/`<button>`) onde possível. Um **gate axe-core no CI**
é follow-up do Trilho S (S10).

## Contrato do subset do Modo C (S11)

O transpilador aceita um **subset tipado** de Python — estável e fail-loud
(`arquivo:linha` para o que estiver fora). Ver a lista completa no
[guia do Modo C](transpile.md#o-subset-suportado).

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
[roadmap](roadmap.md) — S11.

!!! tip "Portabilidade A/B/C"
    Um `view()` no subset roda **idêntico** nos três modos. O `build --mode
    transpile` valida isso renderizando pelo core real — uma API só-do-Modo-C
    quebraria o build.

## Recap

- Pré-1.0: superfície pública documentada + wire-contract; fixe a versão.
- Browsers modernos (Chrome/Edge/Firefox/Safari recentes) nos três modos.
- a11y por semantics/roles; gate axe é follow-up.
- Subset do Modo C é um contrato estável e fail-loud; components ficam em A/B.
