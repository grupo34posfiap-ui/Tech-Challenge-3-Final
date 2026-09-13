"""
Normalização de schema das pesquisas State of Data Brasil.

Os CSVs do Data Hackers vêm com cabeçalhos que são *tuplas serializadas como
texto*, no formato ``"('P2_h ', 'Faixa salarial')"`` — o primeiro elemento é o
código da pergunta no questionário e o segundo é o enunciado. Isso é péssimo
como nome de coluna: tem parêntese, aspas, espaço, acento e vírgula, o que
quebra Parquet, Athena e SQL em geral.

Este módulo converte esses cabeçalhos em identificadores snake_case estáveis
(``p2_h_faixa_salarial``), preservando o código da pergunta como prefixo para
que a rastreabilidade com o questionário original não se perca.

É puro Python (sem Spark e sem pandas) justamente para poder ser importado
tanto pelo Glue Job quanto pela execução local.
"""
from __future__ import annotations

import ast
import re
import unicodedata

# Colunas que, depois de normalizadas, ainda assim não interessam a nenhuma
# camada — texto livre longo e identificadores internos do formulário.
DROP_PATTERNS = (
    r"^unnamed",
    r"^_c\d+$",
)


def strip_accents(text: str) -> str:
    """Remove acentos preservando as letras base (ação -> acao)."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def slugify(text: str) -> str:
    """Converte texto livre em um identificador snake_case seguro para SQL."""
    text = strip_accents(str(text)).lower()
    # Guarda separadores semânticos antes de matar a pontuação
    text = text.replace("/", " ").replace("-", " ").replace("+", " mais ")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


# Formato plano usado a partir da edição 2024: "1.a_idade", "2.h_faixa_salarial",
# "4.d.1_sql". O código da pergunta é o mesmo do formato antigo — só mudou a
# grafia (P1_a virou 1.a).
CODIGO_PLANO = re.compile(r"^(\d+(?:\.[A-Za-z0-9]+)*)[_\s](.+)$")


def normalizar_codigo_pergunta(codigo: str) -> str:
    """
    Reduz as duas grafias de código de pergunta a uma forma única.

    As edições 2023 e 2024+ referenciam a MESMA pergunta com códigos escritos
    de formas diferentes — ``P1_a`` e ``1.a``. Convergir os dois para
    ``p1_a`` é o que permite que um único padrão no dicionário canônico
    encontre a coluna em qualquer edição.

    >>> normalizar_codigo_pergunta("P1_a ")
    'p1_a'
    >>> normalizar_codigo_pergunta("1.a")
    'p1_a'
    >>> normalizar_codigo_pergunta("4.d.1")
    'p4_d_1'
    """
    codigo = str(codigo).strip().lower()
    codigo = codigo.replace(".", "_")
    codigo = re.sub(r"[^a-z0-9_]+", "_", codigo).strip("_")
    # O formato novo não traz o "p" inicial; o antigo traz.
    if codigo and codigo[0].isdigit():
        codigo = f"p{codigo}"
    return codigo


def parse_header(raw: str) -> tuple[str | None, str]:
    """
    Separa um cabeçalho bruto em ``(codigo_pergunta, enunciado)``.

    Cobre os dois formatos que o Data Hackers já usou:

      * tupla serializada (edição 2023): ``"('P2_h ', 'Faixa salarial')"``
      * plano com código pontuado (2024+): ``"2.h_faixa_salarial"``

    >>> parse_header("('P2_h ', 'Faixa salarial')")
    ('P2_h', 'Faixa salarial')
    >>> parse_header("2.h_faixa_salarial")
    ('2.h', 'faixa_salarial')
    >>> parse_header("Idade")
    (None, 'Idade')
    """
    raw = str(raw).strip()

    if raw.startswith("(") and raw.endswith(")"):
        try:
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, tuple) and len(parsed) >= 2:
                codigo = str(parsed[0]).strip()
                enunciado = str(parsed[1]).strip()
                return (codigo or None, enunciado)
        except (ValueError, SyntaxError):
            # Cabeçalho com aspas desbalanceadas — cai no tratamento textual
            inner = raw[1:-1]
            partes = [p.strip().strip("'\"") for p in inner.split("',")]
            if len(partes) >= 2:
                return (partes[0].strip("'\" ") or None, partes[1])

    plano = CODIGO_PLANO.match(raw)
    if plano:
        return (plano.group(1), plano.group(2))

    return (None, raw)


def normalize_column(raw: str) -> str:
    """
    Gera o nome final da coluna a partir do cabeçalho bruto.

    O código da pergunta vira prefixo, o enunciado vira o corpo do nome:
    ``"('P4_d_1 ', 'SQL')"`` -> ``p4_d_1_sql``.
    """
    codigo, enunciado = parse_header(raw)
    corpo = slugify(enunciado)

    if codigo:
        prefixo = normalizar_codigo_pergunta(codigo)
        # Evita p1_a_p1_a_idade quando o enunciado já repete o código
        if corpo.startswith(prefixo + "_") or corpo == prefixo:
            return corpo or prefixo
        nome = f"{prefixo}_{corpo}" if corpo else prefixo
    else:
        nome = corpo

    # Nome de coluna não pode começar com dígito no Athena/Parquet
    if nome and nome[0].isdigit():
        nome = f"c_{nome}"

    return nome or "coluna_sem_nome"


def normalize_columns(raw_columns: list[str]) -> list[str]:
    """
    Normaliza uma lista inteira de cabeçalhos, garantindo unicidade.

    Colisões recebem sufixo numérico (``_2``, ``_3``, ...) em vez de serem
    descartadas silenciosamente — perder coluna sem aviso é pior do que ter
    um nome feio.
    """
    vistos: dict[str, int] = {}
    saida: list[str] = []

    for raw in raw_columns:
        nome = normalize_column(raw)
        if nome in vistos:
            vistos[nome] += 1
            nome = f"{nome}_{vistos[nome]}"
        else:
            vistos[nome] = 1
        saida.append(nome)

    return saida


def is_droppable(column: str) -> bool:
    """True para colunas-lixo geradas por exportação (índices anônimos)."""
    return any(re.match(p, column) for p in DROP_PATTERNS)
