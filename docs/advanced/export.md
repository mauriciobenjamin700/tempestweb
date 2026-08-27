# Exportar CSV e XLSX (`tempestweb.export`)

!!! tip "O que você vai aprender"
    A transformar as linhas que já estão na sua tela num arquivo que o usuário
    baixa — CSV ou XLSX — sem escrever encoder na mão e sem instalar nada. 🚀

Sua app mostra uma `DataTable`. O usuário quer um botão **"Exportar"**. Você já
tem [`native.file.save`](native-reference.md), que entrega bytes ao usuário —
mas quem **produz** esses bytes?

Até aqui, você. E encoder escrito na mão erra sempre nos mesmos lugares.

## O problema, em quatro linhas

```python
# ❌ Não faça isso
linhas = ["id,nome,cidade"]
for row in rows:
    linhas.append(f"{row['id']},{row['name']},{row['city']}")
csv = "\n".join(linhas).encode("utf-8")
```

Funciona até a primeira linha de dado real:

| O dado | O que quebra |
| --- | --- |
| `Recife, PE` | a vírgula vira separador: a linha ganha uma coluna |
| `Ana "A" Silva` | as aspas quebram o parser de quem for ler |
| `João` | sem BOM, o Excel abre como `JoÃ£o` |
| `27/08/2026` num XLSX | vira o número `46265`, porque Excel não tem tipo data |

O `tempestweb.export` embrulha exatamente esses quatro.

## O primeiro export

Um programa completo, que roda:

```python
from tempestweb import native
from tempestweb.export import CSV_MIME_TYPE, Column, to_csv

COLUMNS = [
    Column("id", "ID"),
    Column("name", "Nome"),
    Column("city", "Cidade"),
]

ROWS = [
    {"id": 1, "name": 'Ana "A" Silva', "city": "Recife, PE"},
    {"id": 2, "name": "João", "city": "Olinda"},
]


async def exportar() -> None:
    """Gera o CSV e entrega ao usuário."""
    await native.file.save(
        "usuarios.csv",
        to_csv(ROWS, COLUMNS),
        mime_type=CSV_MIME_TYPE,
    )
```

O arquivo que sai, byte a byte:

```text
﻿ID,Nome,Cidade
1,"Ana ""A"" Silva","Recife, PE"
2,João,Olinda
```

Repare no que você **não** escreveu: a vírgula de `Recife, PE` foi para dentro
de aspas, as aspas de `"A"` foram dobradas, e o `﻿` na frente é o BOM que
faz o Excel ler `João` certo.

!!! warning "Modo A e Modo B — o Modo C recusa"
    Gerar bytes é Python puro: nada aqui toca o browser, e `to_csv`/`to_xlsx`
    funcionam igual no Modo A (WASM) e no Modo B (servidor). Só a entrega, o
    `file.save`, é capacidade nativa.

    O **Modo C** é outra história. Ele transcreve o Python da sua app para
    JavaScript e serve um conjunto fechado de módulos — `tempest_core`,
    `tempestweb.components` e `tempestweb.native`. Importar este pacote numa app
    Modo C é **recusado no build**, com erro nomeado:

    ```text
    app.py:5: import from 'tempestweb.export' is not supported
    (only tempest_core, `tempestweb.components` and `tempestweb.native`)
    ```

    App Modo C que precisa exportar pede o arquivo ao servidor, que gera com
    este mesmo módulo e responde os bytes.

## `Column`: de onde vem, o que diz, como aparece

Uma coluna carrega três coisas:

```python
Column("created_at", "Criado em", format=lambda v: v.strftime("%d/%m/%Y"))
#      ^ o campo      ^ o cabeçalho  ^ como o valor vira texto (opcional)
```

O campo é lido da linha **seja ela um dict ou um objeto** — a mesma lista de
colunas serve para o `dict` que veio da API e para a `@dataclass` do seu estado:

```python
from dataclasses import dataclass

from tempestweb.export import Column, to_csv


@dataclass(frozen=True)
class Usuario:
    """Uma linha da tabela."""

    id: int
    name: str


COLUMNS = [Column("id", "ID"), Column("name", "Nome")]

print(to_csv([{"id": 1, "name": "Ana"}], COLUMNS, bom=False))
print(to_csv([Usuario(1, "Ana")], COLUMNS, bom=False))
# b'ID,Nome\r\n1,Ana\r\n' nos dois casos
```

!!! warning "Um campo que não existe **levanta**, não exporta em branco"
    `Column("nmae", "Nome")` não gera uma coluna vazia: levanta
    `ColumnFieldError` dizendo qual campo faltou e quais existem. Uma coluna de
    brancos só é descoberta por quem abre a planilha — muito depois, e muito
    mais caro.

## O separador do Excel em pt-BR

!!! danger "Vírgula + Excel pt-BR = tudo numa coluna só"
    O Excel usa o **separador de lista do sistema**. Num Windows configurado em
    português, isso é `;` — e um arquivo separado por vírgula abre com todas as
    colunas empilhadas numa só. O BOM não resolve isso: são problemas
    diferentes.

    ```python
    to_csv(rows, COLUMNS, delimiter=";")   # abre certo no Excel pt-BR
    ```

    Se o destino é outro sistema (um import, um script, um `pandas.read_csv`),
    mantenha a vírgula — que é o default e o que a RFC 4180 diz.

## XLSX: a data é o detalhe que importa

```python
from datetime import date

from tempestweb import native
from tempestweb.export import XLSX_MIME_TYPE, Column, to_xlsx

COLUMNS = [
    Column("name", "Nome"),
    Column("created_at", "Criado em"),
]

ROWS = [{"name": "Ana", "created_at": date(2026, 8, 27)}]


async def exportar() -> None:
    """Gera a planilha e entrega ao usuário."""
    await native.file.save(
        "usuarios.xlsx",
        to_xlsx(ROWS, COLUMNS, sheet="Usuários"),
        mime_type=XLSX_MIME_TYPE,
    )
```

Abra o arquivo: a coluna **Criado em** mostra `27/08/2026`, e a célula é uma
**data de verdade** — dá para ordenar, filtrar por período e somar dias.

??? info "Detalhes técnicos — por que isso é difícil"
    O Excel **não tem tipo data**. Uma célula de data é um **número** — dias
    desde 1899-12-30 — que ganha aparência de data por um *number format*
    guardado à parte, no `styles.xml`.

    Encoder escrito na mão acerta o número e esquece o formato. O resultado é
    uma planilha válida que mostra `46265` onde o leitor esperava a data, e o
    bug só aparece quando alguém abre o arquivo.

    Por isso o `tempestweb.export` carrega um `styles.xml` com dois `numFmt`
    (`dd/mm/yyyy` e `dd/mm/yyyy hh:mm`) e por isso o teste do repo **abre a
    planilha de volta** — descompacta o zip, resolve os relacionamentos e
    confere que a célula é data, não número parecido com data.

    O epoch de 1899-12-30, e não 1900-01-01, absorve o bug deliberado do Excel
    que considera 1900 um ano bissexto — mantido desde o Lotus 1-2-3.

Os tipos que a planilha entende, sem você pedir:

| Valor em Python | Célula no Excel |
| --- | --- |
| `str` | texto |
| `int`, `float`, `Decimal` | número |
| `bool` | booleano (`VERDADEIRO`/`FALSO`), não o número 1 |
| `date` | data, formatada `dd/mm/yyyy` |
| `datetime` | data e hora, formatada `dd/mm/yyyy hh:mm` |
| `None` | célula vazia |

!!! note "Passar `format=` transforma a célula em texto"
    `Column("created_at", "Criado em", format=lambda v: v.strftime("%d/%m/%Y"))`
    produz uma **string**, e strings viram células de texto — que não ordenam
    como data. Para XLSX, deixe a data passar crua e deixe o formato numérico
    fazer o trabalho. O `format=` é para o CSV, ou para quando você quer texto
    mesmo.

## Nomes de aba que o Excel recusa

```python
to_xlsx(rows, COLUMNS, sheet="Vendas/2026")   # SheetNameError
```

O Excel limita o nome da aba a 31 caracteres e proíbe `[ ] : * ? / \`,
apóstrofo no começo ou no fim, e o nome reservado `History`. Uma pasta com nome
inválido abre como "conteúdo ilegível", sem dizer qual parte está errada — então
o `to_xlsx` recusa antes, nomeando o motivo.

## Zero dependência

O XLSX é um zip de XMLs, e o subconjunto que uma exportação precisa é pequeno:
uma planilha, um cabeçalho, e células de texto, número, booleano e data.
`zipfile` e `xml.etree` da biblioteca padrão cobrem tudo isso.

!!! info "Por que não `openpyxl`"
    A superfície do `openpyxl` é enorme perto do punhado de partes usadas aqui,
    e num pacote publicado os bounds dele propagam para **todo** consumidor do
    tempestweb. A regra do projeto é implementar antes de depender quando o
    valor da lib é pequeno em relação ao que ela restringe — e este é o caso.

## Recap

- `Column(campo, cabeçalho, format=...)` diz de onde vem, o que aparece e como.
- `to_csv(rows, columns)` devolve **bytes** com BOM ligado por default; use
  `delimiter=";"` quando o destino é Excel em pt-BR.
- `to_xlsx(rows, columns, sheet=...)` devolve **bytes** de uma planilha real,
  com data que é data.
- Os dois são Python puro: rodam no Modo A e no Modo B, e não instalam nada.
  O Modo C recusa o import no build — nele, o servidor gera e responde.
- Entregue com
  [`native.file.save(nome, dados, mime_type=...)`](native-reference.md).
- Campo inexistente e nome de aba inválido **levantam** — em vez de exportar
  algo silenciosamente errado.
