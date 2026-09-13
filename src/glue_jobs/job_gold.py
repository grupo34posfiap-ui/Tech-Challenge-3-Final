"""
Glue Job 3 — SILVER → GOLD
==========================

Materializa as tabelas analíticas que respondem às perguntas de negócio do
Tech Challenge. Cada tabela Gold é pequena, desnormalizada e pensada para ser
consultada direto no Athena ou lida por um notebook de visualização.

Tabelas geradas:

  gold_perfil_mercado      — quem é o profissional de dados (cargo, senioridade,
                             formação, experiência), por ano
  gold_remuneracao         — estatísticas salariais por cargo, senioridade,
                             região e modelo de trabalho
  gold_diversidade_genero  — representatividade e gap salarial de gênero
  gold_tecnologias         — ranking de adoção de tecnologias, por ano
  gold_adocao_ia           — adoção de IA generativa e seu impacto
  gold_modelo_trabalho     — distribuição remoto/híbrido/presencial e salário
  gold_evolucao_anual      — série temporal dos indicadores-chave

Rigor estatístico aplicado em todas as agregações salariais:
  * usa-se **mediana** além da média — a distribuição salarial é assimétrica à
    direita, e a média sozinha superestima o salário típico;
  * recortes com menos de MIN_AMOSTRA respondentes são marcados como não
    confiáveis (``amostra_suficiente = false``) em vez de descartados — quem
    consome decide, mas fica avisado.

Execução no Glue:
    --silver_path s3://<bucket>/silver
    --gold_path   s3://<bucket>/gold

Execução local:
    spark-submit src/glue_jobs/job_gold.py \
        --silver_path data/silver --gold_path data/gold
"""
from __future__ import annotations

import os
import sys

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

try:
    from job_bronze import build_spark, get_args
except ImportError:
    sys.path.insert(0, os.path.dirname(__file__))
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from job_bronze import build_spark, get_args


# Abaixo deste número de respondentes, qualquer estatística de recorte vira
# ruído. 30 é o limiar clássico para o teorema central do limite valer na
# prática — não é magia, mas é uma linha defensável e explícita.
MIN_AMOSTRA = 30


# ===========================================================================
# Helpers de agregação
# ===========================================================================
def stats_salariais(df: DataFrame, *dimensoes: str) -> DataFrame:
    """
    Agrega salário por um conjunto de dimensões, com média, mediana e amostra.

    Só entram no cálculo respondentes com salário informado — respondentes sem
    remuneração (desempregados, estudantes) distorceriam a estatística se
    fossem tratados como zero.
    """
    return (
        df.filter(F.col("salario_medio_mensal").isNotNull())
        .groupBy(*dimensoes)
        .agg(
            F.count("*").alias("respondentes"),
            F.round(F.avg("salario_medio_mensal"), 2).alias("salario_medio"),
            F.round(
                F.percentile_approx("salario_medio_mensal", 0.5), 2
            ).alias("salario_mediano"),
            F.round(
                F.percentile_approx("salario_medio_mensal", 0.25), 2
            ).alias("salario_p25"),
            F.round(
                F.percentile_approx("salario_medio_mensal", 0.75), 2
            ).alias("salario_p75"),
        )
        .withColumn(
            "amostra_suficiente", F.col("respondentes") >= F.lit(MIN_AMOSTRA)
        )
    )


def escrever(df: DataFrame, gold_path: str, nome: str) -> None:
    """Persiste uma tabela Gold em Parquet e reporta o volume."""
    destino = f"{gold_path}/{nome}"
    # Tabelas Gold são pequenas (dezenas a milhares de linhas). Um único
    # arquivo por tabela evita o problema de small files no S3 e deixa a
    # leitura pelo Athena mais barata.
    df.coalesce(1).write.mode("overwrite").parquet(destino)
    print(f"[gold] {nome}: {df.count()} linhas -> {destino}")


# ===========================================================================
# Tabelas Gold
# ===========================================================================
def build_perfil_mercado(silver: DataFrame) -> DataFrame:
    """Composição do mercado: quantos profissionais em cada cargo/senioridade."""
    from pyspark.sql import Window

    base = silver.filter(F.col("cargo").isNotNull())
    janela_ano = Window.partitionBy("survey_year")

    return (
        base.groupBy("survey_year", "cargo", "senioridade")
        .agg(
            F.count("*").alias("respondentes"),
            F.round(F.avg("idade"), 1).alias("idade_media"),
            F.round(
                F.percentile_approx("salario_medio_mensal", 0.5), 2
            ).alias("salario_mediano"),
        )
        .withColumn(
            "pct_do_ano",
            F.round(
                F.col("respondentes") * 100.0
                / F.sum("respondentes").over(janela_ano),
                2,
            ),
        )
        .withColumn(
            "amostra_suficiente", F.col("respondentes") >= F.lit(MIN_AMOSTRA)
        )
        .orderBy("survey_year", F.desc("respondentes"))
    )


def build_remuneracao(silver: DataFrame) -> DataFrame:
    """
    Estatísticas salariais em múltiplos recortes, empilhadas numa só tabela.

    Empilhar (formato longo) em vez de gerar uma tabela por recorte mantém o
    Data Catalog enxuto e permite que o notebook filtre por ``dimensao``.
    """
    recortes = [
        ("cargo", "cargo"),
        ("senioridade", "senioridade"),
        ("regiao", "regiao"),
        ("modelo_trabalho", "modelo_trabalho"),
        ("setor_empresa", "setor_empresa"),
        ("nivel_ensino", "nivel_ensino"),
        ("tempo_experiencia_dados", "tempo_experiencia_dados"),
    ]

    partes = []
    for nome_dimensao, coluna in recortes:
        if coluna not in silver.columns:
            continue
        parte = (
            stats_salariais(
                silver.filter(F.col(coluna).isNotNull()), "survey_year", coluna
            )
            .withColumn("dimensao", F.lit(nome_dimensao))
            .withColumnRenamed(coluna, "categoria")
            .select(
                "survey_year", "dimensao", "categoria", "respondentes",
                "salario_medio", "salario_mediano", "salario_p25",
                "salario_p75", "amostra_suficiente",
            )
        )
        partes.append(parte)

    resultado = partes[0]
    for parte in partes[1:]:
        resultado = resultado.unionByName(parte)

    return resultado.orderBy(
        "survey_year", "dimensao", F.desc("salario_mediano")
    )


def build_diversidade_genero(silver: DataFrame) -> DataFrame:
    """
    Representatividade de gênero e gap salarial, por ano e senioridade.

    O gap é calculado contra o salário mediano masculino do mesmo recorte —
    comparar contra a média geral misturaria efeito de composição (mulheres
    concentradas em cargos juniores) com diferença de remuneração.
    """
    from pyspark.sql import Window

    # Sem senioridade não há como separar diferença de remuneração de
    # diferença de composição — que é justamente o ponto desta tabela.
    base = silver.filter(
        F.col("genero").isNotNull() & F.col("senioridade").isNotNull()
    )

    agregado = (
        base.groupBy("survey_year", "senioridade", "genero")
        .agg(
            F.count("*").alias("respondentes"),
            F.round(
                F.percentile_approx("salario_medio_mensal", 0.5), 2
            ).alias("salario_mediano"),
        )
    )

    janela_recorte = Window.partitionBy("survey_year", "senioridade")

    return (
        agregado.withColumn(
            "pct_representatividade",
            F.round(
                F.col("respondentes") * 100.0
                / F.sum("respondentes").over(janela_recorte),
                2,
            ),
        )
        .withColumn(
            "salario_mediano_masculino",
            F.max(
                F.when(F.col("genero") == "Masculino", F.col("salario_mediano"))
            ).over(janela_recorte),
        )
        .withColumn(
            "gap_salarial_pct",
            F.round(
                (F.col("salario_mediano") - F.col("salario_mediano_masculino"))
                * 100.0
                / F.col("salario_mediano_masculino"),
                2,
            ),
        )
        .withColumn(
            "amostra_suficiente", F.col("respondentes") >= F.lit(MIN_AMOSTRA)
        )
        .orderBy("survey_year", "senioridade", F.desc("respondentes"))
    )


def build_tecnologias(silver: DataFrame) -> DataFrame:
    """
    Ranking de adoção de tecnologias por ano.

    Cada array de tecnologia vira linhas via explode; o denominador é o número
    de respondentes que RESPONDERAM aquele bloco (array não nulo), não o total
    da edição — senão uma edição que não fez a pergunta apareceria como 0% de
    adoção em vez de "sem dado".
    """
    grupos = [
        ("linguagens", "Linguagem"),
        ("bancos_dados", "Banco de dados"),
        ("cloud_utilizada", "Cloud"),
        ("ferramentas_bi", "Ferramenta de BI"),
    ]

    partes = []
    for coluna, categoria in grupos:
        if coluna not in silver.columns:
            continue

        respondeu = silver.filter(F.col(coluna).isNotNull())
        base_ano = respondeu.groupBy("survey_year").agg(
            F.count("*").alias("base_respondentes")
        )

        contagem = (
            respondeu.select(
                "survey_year", F.explode(F.col(coluna)).alias("tecnologia")
            )
            .filter(F.col("tecnologia").isNotNull() & (F.col("tecnologia") != ""))
            .groupBy("survey_year", "tecnologia")
            .agg(F.count("*").alias("usuarios"))
        )

        parte = (
            contagem.join(base_ano, on="survey_year", how="inner")
            .withColumn("categoria", F.lit(categoria))
            .withColumn(
                "pct_adocao",
                F.round(
                    F.col("usuarios") * 100.0 / F.col("base_respondentes"), 2
                ),
            )
            .select(
                "survey_year", "categoria", "tecnologia", "usuarios",
                "base_respondentes", "pct_adocao",
            )
        )
        partes.append(parte)

    resultado = partes[0]
    for parte in partes[1:]:
        resultado = resultado.unionByName(parte)

    return resultado.orderBy("survey_year", "categoria", F.desc("pct_adocao"))


def build_adocao_ia(silver: DataFrame) -> DataFrame:
    """
    Adoção de IA generativa por ano, cargo e senioridade.

    Edições que não fizeram a pergunta produzem ``base_respondentes = 0`` e
    percentual nulo — ausência de dado, não ausência de adoção.
    """
    base = silver.groupBy("survey_year", "cargo", "senioridade").agg(
        F.count("*").alias("respondentes"),
        F.count(F.col("usa_ia_generativa")).alias("base_uso_pessoal"),
        F.sum(F.col("usa_ia_generativa").cast("int")).alias("usam_ia"),
        F.count(F.col("empresa_prioriza_ia")).alias("base_uso_empresa"),
        F.sum(F.col("empresa_prioriza_ia").cast("int")).alias("empresas_usam_ia"),
    )

    return (
        base.withColumn(
            "pct_uso_pessoal",
            F.when(
                F.col("base_uso_pessoal") > 0,
                F.round(
                    F.col("usam_ia") * 100.0 / F.col("base_uso_pessoal"), 2
                ),
            ),
        )
        .withColumn(
            "pct_uso_empresa",
            F.when(
                F.col("base_uso_empresa") > 0,
                F.round(
                    F.col("empresas_usam_ia") * 100.0
                    / F.col("base_uso_empresa"),
                    2,
                ),
            ),
        )
        .withColumn(
            "amostra_suficiente", F.col("respondentes") >= F.lit(MIN_AMOSTRA)
        )
        .orderBy("survey_year", F.desc("respondentes"))
    )


def build_impacto_ia(silver: DataFrame) -> DataFrame:
    """
    Impacto da IA generativa nos resultados da empresa — não só adoção.

    ``gold_adocao_ia`` mede QUEM usa IA e QUEM prioriza; esta tabela mede o
    passo seguinte, que o enunciado pede explicitamente ("qual o índice de
    adoção de IA e SEU IMPACTO"): a empresa está de fato colhendo resultado
    dos projetos de IA generativa, ou ainda está em piloto?

    Só a edição 2025-26 tem essa pergunta (``resultado_ia_empresa``) — é
    natural que só ela apareça na tabela; as edições anteriores não
    fizeram a pergunta, então não têm o que agregar aqui.
    """
    from pyspark.sql import Window

    base = silver.filter(F.col("resultado_ia_empresa").isNotNull())

    return (
        base.groupBy("survey_year", "resultado_ia_empresa")
        .agg(F.count("*").alias("respondentes"))
        .withColumn(
            "pct",
            F.round(
                F.col("respondentes") * 100.0
                / F.sum("respondentes").over(Window.partitionBy("survey_year")),
                2,
            ),
        )
        .orderBy("survey_year", F.desc("respondentes"))
    )


def build_remuneracao_regional(silver: DataFrame) -> DataFrame:
    """
    Salário por região, controlado por senioridade.

    ``gold_remuneracao`` (dimensao='regiao') cruza salário só com região, e
    isso confunde duas coisas diferentes: diferença de CUSTO DE VIDA/MERCADO
    regional com diferença de COMPOSIÇÃO (uma região pode ter, por acaso,
    mais gente sênior que outra). O Sudeste tem 15,8% de Especialista/Staff+
    contra 6,4% do Nordeste em 2025 — sozinho, isso já infla a média bruta do
    Sudeste sem dizer nada sobre quanto custa contratar um Sênior em cada
    lugar.

    Esta tabela cruza região × senioridade, para que a comparação seja feita
    dentro do mesmo nível de carreira. Uso média (não mediana) pelo mesmo
    motivo do corte por região simples: as faixas salariais são largas
    demais para a mediana distinguir regiões dentro do mesmo nível.
    """
    base = silver.filter(
        F.col("salario_medio_mensal").isNotNull()
        & F.col("regiao").isNotNull()
        & (F.col("regiao") != "Não informado")
        & F.col("senioridade").isNotNull()
    )

    return (
        base.groupBy("survey_year", "regiao", "senioridade")
        .agg(
            F.count("*").alias("respondentes"),
            F.round(F.avg("salario_medio_mensal"), 2).alias("salario_medio"),
            F.round(
                F.percentile_approx("salario_medio_mensal", 0.5), 2
            ).alias("salario_mediano"),
        )
        .withColumn(
            "amostra_suficiente", F.col("respondentes") >= F.lit(MIN_AMOSTRA)
        )
        .orderBy("survey_year", "regiao", "senioridade")
    )


def build_modelo_trabalho(silver: DataFrame) -> DataFrame:
    """Distribuição dos modelos de trabalho e o salário associado a cada um."""
    from pyspark.sql import Window

    base = silver.filter(F.col("modelo_trabalho").isNotNull())
    janela = Window.partitionBy("survey_year", "regiao")

    return (
        base.groupBy("survey_year", "regiao", "modelo_trabalho")
        .agg(
            F.count("*").alias("respondentes"),
            F.round(
                F.percentile_approx("salario_medio_mensal", 0.5), 2
            ).alias("salario_mediano"),
        )
        .withColumn(
            "pct_na_regiao",
            F.round(
                F.col("respondentes") * 100.0
                / F.sum("respondentes").over(janela),
                2,
            ),
        )
        .withColumn(
            "amostra_suficiente", F.col("respondentes") >= F.lit(MIN_AMOSTRA)
        )
        .orderBy("survey_year", "regiao", F.desc("respondentes"))
    )


def build_evolucao_anual(silver: DataFrame) -> DataFrame:
    """Indicadores-chave em série temporal — a espinha dorsal do storytelling."""
    return (
        silver.groupBy("survey_year")
        .agg(
            F.count("*").alias("total_respondentes"),
            F.round(F.avg("idade"), 1).alias("idade_media"),
            F.round(
                F.percentile_approx("salario_medio_mensal", 0.5), 2
            ).alias("salario_mediano_geral"),
            F.round(
                F.avg((F.col("genero") == "Feminino").cast("int")) * 100, 2
            ).alias("pct_mulheres"),
            F.round(
                F.avg((F.col("modelo_trabalho") == "Remoto").cast("int")) * 100,
                2,
            ).alias("pct_remoto"),
            F.round(
                F.avg((F.col("modelo_trabalho") == "Híbrido").cast("int")) * 100,
                2,
            ).alias("pct_hibrido"),
            F.round(
                F.avg((F.col("modelo_trabalho") == "Presencial").cast("int"))
                * 100,
                2,
            ).alias("pct_presencial"),
            F.round(
                F.avg(F.col("usa_ia_generativa").cast("int")) * 100, 2
            ).alias("pct_usa_ia_generativa"),
            F.round(
                F.avg(F.col("empresa_prioriza_ia").cast("int")) * 100, 2
            ).alias("pct_empresa_prioriza_ia"),
        )
        .orderBy("survey_year")
    )


# ===========================================================================
def main() -> None:
    args = get_args({"silver_path": "data/silver", "gold_path": "data/gold"})
    silver_path = args["silver_path"].rstrip("/")
    gold_path = args["gold_path"].rstrip("/")

    spark = build_spark("tc3-job-gold")
    spark.sparkContext.setLogLevel("WARN")

    silver = spark.read.parquet(silver_path)
    # A Silver é lida várias vezes (uma por tabela Gold); cachear evita
    # reprocessar o parse e as UDFs a cada agregação.
    silver.cache()
    print(f"[gold] silver carregada: {silver.count()} respondentes")

    tabelas = {
        "gold_perfil_mercado": build_perfil_mercado,
        "gold_remuneracao": build_remuneracao,
        "gold_diversidade_genero": build_diversidade_genero,
        "gold_tecnologias": build_tecnologias,
        "gold_adocao_ia": build_adocao_ia,
        "gold_impacto_ia": build_impacto_ia,
        "gold_remuneracao_regional": build_remuneracao_regional,
        "gold_modelo_trabalho": build_modelo_trabalho,
        "gold_evolucao_anual": build_evolucao_anual,
    }

    for nome, construtor in tabelas.items():
        escrever(construtor(silver), gold_path, nome)

    print("[gold] concluído")
    spark.stop()


if __name__ == "__main__":
    main()
