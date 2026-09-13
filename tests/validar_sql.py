"""
Valida as consultas de sql/02_consultas_analiticas.sql.

O Athena roda Trino, e não temos Trino local. Mas a esmagadora maioria das
consultas usa apenas construções que o Spark SQL também entende
(``approx_percentile``, funções de janela, ``NULLIF``, CTEs). Rodá-las contra
o Data Lake local pega a classe de erro que realmente importa: referência a
coluna inexistente, erro de agregação e erro de sintaxe.

As poucas construções exclusivas do Trino são traduzidas antes da execução, e
o relatório diz explicitamente quais foram adaptadas — elas continuam
precisando de uma passada no console do Athena.

Este validador faz assertions de conteúdo, não só "a consulta rodou sem
erro": 0 linhas devolvidas ou uma coluna inteira nula também contam como
falha (ver ``checar_conteudo``). Contra o fixture de
``gerar_dados_sinteticos.py`` isso vai acusar falha em consultas que dependem
de campos fora do escopo do fixture (região, setor, satisfação, o texto
exato da pergunta de uso de IA) — o fixture só simula as 3 divergências
documentadas no cabeçalho dele, não o questionário inteiro. Falha nessas
consultas específicas é esperado contra o fixture; o que importa é que
nenhuma falha apareça ao rodar contra os dados reais (``data/gold``,
``data/silver``).

Uso:
    python tests/validar_sql.py --gold /caminho/gold --silver /caminho/silver
"""
from __future__ import annotations

import argparse
import re
import tempfile
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

RAIZ = Path(__file__).resolve().parents[1]
ARQUIVO_SQL = RAIZ / "sql" / "02_consultas_analiticas.sql"

# Construções Trino -> Spark. Cada entrada é (regex, substituto, rótulo).
TRADUCOES: list[tuple[str, str, str]] = [
    (
        r"CROSS JOIN UNNEST\((\w+)\) AS t \((\w+)\)",
        r"LATERAL VIEW explode(\1) t AS \2",
        "UNNEST -> LATERAL VIEW explode",
    ),
]


def extrair_consultas(texto: str) -> list[tuple[str, str]]:
    """Separa o arquivo em consultas, guardando o rótulo do comentário acima."""
    # Remove comentários de bloco decorativos (###) mas guarda os rótulos "-- N.N —"
    consultas: list[tuple[str, str]] = []
    rotulo = "sem rótulo"

    buffer: list[str] = []
    for linha in texto.splitlines():
        despida = linha.strip()

        m = re.match(r"^--\s*(\d+\.\d+)\s*[—-]\s*(.+)$", despida)
        if m:
            rotulo = f"{m.group(1)} {m.group(2)}"

        if despida.startswith("--") or not despida:
            continue

        buffer.append(linha)
        if despida.endswith(";"):
            sql = "\n".join(buffer).rstrip().rstrip(";")
            consultas.append((rotulo, sql))
            buffer = []

    return consultas


def traduzir(sql: str) -> tuple[str, list[str]]:
    """Aplica as traduções Trino -> Spark, devolvendo quais foram usadas."""
    aplicadas: list[str] = []
    for padrao, substituto, nome in TRADUCOES:
        novo = re.sub(padrao, substituto, sql, flags=re.IGNORECASE)
        if novo != sql:
            aplicadas.append(nome)
            sql = novo
    return sql, aplicadas


def checar_conteudo(df) -> tuple[int, list[str]]:
    """
    Assertions de conteúdo — não basta a consulta executar sem erro.

    Um validador que só olha "levantou exceção?" aceita como sucesso uma
    consulta que roda limpa e devolve 0 linhas, ou que devolve linhas mas com
    uma coluna inteira nula (join errado, filtro que não bate com o dado
    sintético, nome de coluna que existe mas nunca foi preenchido). Os dois
    casos passam para o Athena como "consulta OK" e só explodem na hora de
    montar o slide.
    """
    n = df.count()
    problemas: list[str] = []

    if n == 0:
        problemas.append("0 linhas devolvidas")
        return n, problemas

    # amostra para não rodar um COUNT por coluna em tabelas grandes
    amostra = df.limit(2000)
    nulos = amostra.select(
        [F.count(F.when(F.col(c).isNotNull(), c)).alias(c) for c in df.columns]
    ).first()
    colunas_totalmente_nulas = [c for c in df.columns if nulos[c] == 0]
    if colunas_totalmente_nulas:
        problemas.append(
            f"coluna(s) totalmente nula(s): {', '.join(colunas_totalmente_nulas)}"
        )

    return n, problemas


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", required=True)
    parser.add_argument("--silver", required=True)
    args = parser.parse_args()

    # Diretório único por execução, não um caminho fixo em /tmp: um caminho
    # fixo (ex.: /tmp/tc3-warehouse) sobrevive entre execuções, mas o
    # metastore Hive local (metastore_db/, na raiz do repo, recriado a cada
    # rodada) não — rodar duas vezes sem apagar o warehouse na mão faz a
    # segunda execução achar um diretório state_of_data.db físico que o
    # metastore fresco desconhece, e o CREATE TABLE explode com
    # LOCATION_ALREADY_EXISTS. Um diretório novo a cada rodada elimina a
    # possibilidade de colisão — não precisa apagar depois, fica em /tmp.
    warehouse_dir = tempfile.mkdtemp(prefix="tc3-warehouse-")
    spark = (
        SparkSession.builder.appName("tc3-validar-sql")
        .master("local[*]")
        .config("spark.sql.warehouse.dir", warehouse_dir)
        .enableHiveSupport()
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")

    # DROP ... CASCADE + CREATE com localização explícita, em vez de CREATE
    # DATABASE IF NOT EXISTS: se o metastore_db/ local (Derby, gitignored)
    # sobreviver de uma execução anterior, "IF NOT EXISTS" seria um no-op e
    # o banco continuaria apontando para o warehouse.dir da rodada anterior
    # — não para o diretório novo desta rodada. O DROP CASCADE zera esse
    # registro (e o conteúdo físico que ele conhece) antes de recriar o
    # banco já apontando para o warehouse_dir atual.
    spark.sql("DROP DATABASE IF EXISTS state_of_data CASCADE")
    spark.sql(
        f"CREATE DATABASE state_of_data LOCATION "
        f"'{Path(warehouse_dir, 'state_of_data.db').as_posix()}'"
    )
    spark.read.parquet(args.silver).createOrReplaceTempView("_silver")
    spark.sql("DROP TABLE IF EXISTS state_of_data.silver")
    spark.sql(
        "CREATE TABLE state_of_data.silver AS SELECT * FROM _silver"
    )

    for caminho in sorted(Path(args.gold).iterdir()):
        if not caminho.is_dir():
            continue
        nome = caminho.name
        spark.read.parquet(str(caminho)).createOrReplaceTempView(f"_{nome}")
        spark.sql(f"DROP TABLE IF EXISTS state_of_data.{nome}")
        spark.sql(
            f"CREATE TABLE state_of_data.{nome} AS SELECT * FROM _{nome}"
        )

    consultas = extrair_consultas(ARQUIVO_SQL.read_text(encoding="utf-8"))
    print(f"\n{len(consultas)} consultas encontradas em {ARQUIVO_SQL.name}\n")

    ok, falhas, adaptadas = 0, [], []
    for rotulo, sql in consultas:
        # DDL/utilitários não são consultas analíticas
        if re.match(r"^\s*(CREATE|MSCK|SHOW|DROP)", sql, re.IGNORECASE):
            continue

        sql_spark, traducoes = traduzir(sql)
        try:
            df = spark.sql(sql_spark)
            n, problemas = checar_conteudo(df)
            if problemas:
                print(f"  [FALHA] {rotulo}  ({n} linhas)")
                for p in problemas:
                    print(f"          {p}")
                falhas.append((rotulo, "; ".join(problemas)))
                continue

            marca = "OK "
            if traducoes:
                marca = "OK*"
                adaptadas.append((rotulo, traducoes))
            print(f"  [{marca}] {rotulo}  ({n} linhas)")
            ok += 1
        except Exception as exc:  # noqa: BLE001
            primeira_linha = str(exc).split("\n")[0][:160]
            print(f"  [FALHA] {rotulo}\n          {primeira_linha}")
            falhas.append((rotulo, primeira_linha))

    print(f"\n{'=' * 70}")
    print(f"  {ok} consultas OK | {len(falhas)} falhas")
    if adaptadas:
        print(
            f"\n  * {len(adaptadas)} consulta(s) usam sintaxe exclusiva do Trino e "
            "foram traduzidas para rodar no Spark.\n"
            "    Elas precisam de uma verificação no console do Athena:"
        )
        for rotulo, tr in adaptadas:
            print(f"      - {rotulo}: {', '.join(tr)}")
    if falhas:
        print("\n  Falhas:")
        for rotulo, erro in falhas:
            print(f"      - {rotulo}: {erro}")
    print("=" * 70)

    spark.stop()
    raise SystemExit(1 if falhas else 0)


if __name__ == "__main__":
    main()
