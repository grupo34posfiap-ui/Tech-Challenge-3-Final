"""
Glue Job 1 — RAW → BRONZE
=========================

Lê os CSVs brutos das 3 edições do State of Data Brasil e os materializa em
Parquet, particionado por ``survey_year``.

O que a camada Bronze faz:
  * normaliza os cabeçalhos tupla-em-texto para snake_case (ver schema_utils);
  * preserva TODAS as colunas originais, sem descartar nada e sem tipar nada
    além de string — Bronze é fiel à origem por definição;
  * anexa metadados de linhagem (ano da pesquisa, arquivo de origem, timestamp).

O que a camada Bronze NÃO faz: unificar schemas entre edições, limpar valores
ou converter tipos. Isso é responsabilidade da Silver.

Execução no Glue:
    Job parameters:
      --raw_path    s3://<bucket>/raw
      --bronze_path s3://<bucket>/bronze

Execução local (mesmo código):
    spark-submit src/glue_jobs/job_bronze.py --raw_path data/raw --bronze_path data/bronze
"""
from __future__ import annotations

import os
import re
import sys

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

# --------------------------------------------------------------------------
# Import do schema_utils — funciona tanto local (src/ no path) quanto no Glue
# (arquivo enviado via --extra-py-files, que cai na raiz do sys.path).
# --------------------------------------------------------------------------
try:
    from schema_utils import is_droppable, normalize_columns
except ImportError:  # execução local a partir da raiz do projeto
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from schema_utils import is_droppable, normalize_columns


# --------------------------------------------------------------------------
# Argumentos — o Glue passa via getResolvedOptions, local via argv simples
# --------------------------------------------------------------------------
def get_args(defaults: dict[str, str]) -> dict[str, str]:
    """Lê os parâmetros do job funcionando dentro e fora do Glue."""
    try:
        from awsglue.utils import getResolvedOptions  # type: ignore

        return {
            **defaults,
            **getResolvedOptions(sys.argv, list(defaults.keys())),
        }
    except (ImportError, Exception):  # noqa: BLE001 — fora do Glue
        args = dict(defaults)
        argv = sys.argv[1:]
        for i, token in enumerate(argv):
            chave = token.lstrip("-")
            if token.startswith("--") and i + 1 < len(argv):
                args[chave] = argv[i + 1]
        return args


def build_spark(app_name: str) -> SparkSession:
    """SparkSession que serve tanto ao Glue quanto à execução local."""
    return (
        SparkSession.builder.appName(app_name)
        .config("spark.sql.parquet.compression.codec", "snappy")
        # Permite sobrescrever apenas as partições reprocessadas
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
        .config("spark.sql.legacy.timeParserPolicy", "LEGACY")
        .getOrCreate()
    )


# --------------------------------------------------------------------------
# Descoberta do ano da pesquisa a partir do nome do arquivo
# --------------------------------------------------------------------------
def infer_survey_year(path: str) -> int:
    """
    Deduz o ano de referência da edição pelo nome do arquivo.

    Os arquivos do Kaggle vêm com nomes como ``State_of_data_BR_2023.csv`` ou
    ``State_of_data_2024_2025.csv``. Usamos o PRIMEIRO ano de 4 dígitos
    encontrado, que é o ano de início da coleta.
    """
    anos = re.findall(r"(20\d{2})", os.path.basename(path))
    if not anos:
        raise ValueError(
            f"Não foi possível inferir o ano da pesquisa a partir de '{path}'. "
            "Renomeie o arquivo incluindo o ano (ex.: state_of_data_2023.csv)."
        )
    return int(anos[0])


def list_csv_files(spark: SparkSession, raw_path: str) -> list[str]:
    """Lista os CSVs da zona raw, tanto no S3 quanto no filesystem local."""
    if raw_path.startswith("s3"):
        jvm = spark._jvm
        jsc = spark._jsc
        uri = jvm.java.net.URI.create(raw_path)
        fs = jvm.org.apache.hadoop.fs.FileSystem.get(
            uri, jsc.hadoopConfiguration()
        )
        statuses = fs.listStatus(jvm.org.apache.hadoop.fs.Path(raw_path))
        return sorted(
            str(s.getPath())
            for s in statuses
            if str(s.getPath()).lower().endswith(".csv")
        )

    return sorted(
        os.path.join(raw_path, f)
        for f in os.listdir(raw_path)
        if f.lower().endswith(".csv")
    )


# --------------------------------------------------------------------------
# Leitura e normalização
# --------------------------------------------------------------------------
def read_survey_csv(spark: SparkSession, path: str) -> DataFrame:
    """
    Lê um CSV da pesquisa preservando tudo como string.

    ``multiLine`` é obrigatório: várias perguntas são de texto livre e contêm
    quebras de linha dentro das aspas. Sem isso o Spark parte um respondente em
    várias linhas corrompidas.
    """
    return (
        spark.read.option("header", "true")
        .option("multiLine", "true")
        .option("quote", '"')
        .option("escape", '"')
        .option("encoding", "UTF-8")
        .option("mode", "PERMISSIVE")
        .csv(path)
    )


def normalize_dataframe(df: DataFrame, path: str, survey_year: int) -> DataFrame:
    """Renomeia colunas, descarta lixo de exportação e anexa linhagem."""
    nomes = normalize_columns(df.columns)
    df = df.toDF(*nomes)

    manter = [c for c in df.columns if not is_droppable(c)]
    df = df.select(*manter)

    return (
        df.withColumn("survey_year", F.lit(survey_year).cast("int"))
        .withColumn("arquivo_origem", F.lit(os.path.basename(path)))
        .withColumn("ingerido_em", F.current_timestamp())
    )


def main() -> None:
    args = get_args(
        {
            "raw_path": "data/raw",
            "bronze_path": "data/bronze",
        }
    )
    raw_path = args["raw_path"].rstrip("/")
    bronze_path = args["bronze_path"].rstrip("/")

    spark = build_spark("tc3-job-bronze")
    spark.sparkContext.setLogLevel("WARN")

    arquivos = list_csv_files(spark, raw_path)
    if not arquivos:
        raise SystemExit(f"Nenhum CSV encontrado em {raw_path}")

    print(f"[bronze] {len(arquivos)} arquivo(s) encontrado(s) em {raw_path}")

    # Cada edição é escrita na sua própria partição. Não fazemos union aqui:
    # os schemas das 3 edições são diferentes de propósito, e reconciliá-los
    # é trabalho da camada Silver.
    for path in arquivos:
        survey_year = infer_survey_year(path)
        df = normalize_dataframe(read_survey_csv(spark, path), path, survey_year)

        n_linhas = df.count()
        n_colunas = len(df.columns)
        print(
            f"[bronze] {os.path.basename(path)} -> survey_year={survey_year} "
            f"| {n_linhas} linhas | {n_colunas} colunas"
        )

        (
            df.write.mode("overwrite")
            .partitionBy("survey_year")
            .parquet(bronze_path)
        )

    print(f"[bronze] concluído -> {bronze_path}")
    spark.stop()


if __name__ == "__main__":
    main()
