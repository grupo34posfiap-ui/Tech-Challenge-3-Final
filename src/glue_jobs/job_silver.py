"""
Glue Job 2 — BRONZE → SILVER
============================

Harmoniza as três edições do State of Data Brasil em um único schema canônico.

Este é o job que carrega o peso do projeto. As edições não compartilham nomes
de coluna, e algumas perguntas simplesmente não existem em edições anteriores
(IA generativa é o caso mais evidente). O job:

  1. processa **uma edição por vez**, resolvendo o schema daquela edição contra
     o dicionário canônico (``mappings.resolve_schema``);
  2. preenche com NULL os campos canônicos que aquela edição não possui, para
     que o union seja possível sem perder linhas;
  3. normaliza os *valores* — senioridade, cargo, gênero, modelo de trabalho —
     em categorias comparáveis entre anos;
  4. converte faixa salarial textual em ponto médio numérico;
  5. colapsa os blocos de colunas one-hot de tecnologia em arrays;
  6. registra em log tudo que não conseguiu resolver.

O resultado é uma tabela única, particionada por ``survey_year``, com uma linha
por respondente e semântica idêntica entre as três edições.

Execução no Glue:
    --bronze_path s3://<bucket>/bronze
    --silver_path s3://<bucket>/silver

Execução local:
    spark-submit src/glue_jobs/job_silver.py \
        --bronze_path data/bronze --silver_path data/silver
"""
from __future__ import annotations

import os
import sys

from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F
from pyspark.sql import types as T

if __name__ == "__main__":  # execução local a partir da raiz do projeto
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, os.path.dirname(__file__))

from job_bronze import build_spark, get_args  # noqa: E402
from mappings import (  # noqa: E402
    CANONICAL_FIELDS,
    CARGO_CANONICO,
    GENERO_CANONICO,
    MODELO_TRABALHO_CANONICO,
    PRIORIDADE_IA_CANONICA,
    RESULTADO_IA_CANONICA,
    SENIORIDADE_CANONICA,
    TIPO_USO_IA_CANONICO,
    UF_PARA_REGIAO,
    canonicalizar,
    eh_item_tecnologia,
    empresa_prioriza_ia,
    parse_booleano,
    parse_faixa_salarial,
    resolve_multiselect,
    resolve_schema,
    rotulo_item_multiselect,
    usa_ia_generativa,
)


# ===========================================================================
# UDFs — as regras de negócio vivem em mappings.py (Python puro e testável);
# aqui apenas as expomos ao Spark.
# ===========================================================================
#
# Todas as canonicalizações devolvem NULL (default=None) quando a resposta está
# ausente, em vez de um rótulo "Não informado". A diferença importa: cerca de
# 27% dos respondentes não têm nível de carreira — são desempregados,
# estudantes e acadêmicos, para quem a pergunta não se aplica. Como NULL, eles
# saem sozinhos de qualquer agregação por senioridade; como rótulo, virariam a
# segunda maior "senioridade" do mercado brasileiro em todos os gráficos.
udf_salario = F.udf(parse_faixa_salarial, T.DoubleType())
udf_booleano = F.udf(parse_booleano, T.BooleanType())
udf_senioridade = F.udf(
    lambda v: canonicalizar(v, SENIORIDADE_CANONICA, default=None), T.StringType()
)
udf_cargo = F.udf(
    lambda v: canonicalizar(v, CARGO_CANONICO, default=None), T.StringType()
)
udf_genero = F.udf(
    lambda v: canonicalizar(v, GENERO_CANONICO, default=None), T.StringType()
)
udf_modelo = F.udf(
    lambda v: canonicalizar(v, MODELO_TRABALHO_CANONICO, default=None), T.StringType()
)
udf_tipo_uso_ia = F.udf(
    lambda v: canonicalizar(v, TIPO_USO_IA_CANONICO, default=None), T.StringType()
)
udf_prioridade_ia = F.udf(
    lambda v: canonicalizar(v, PRIORIDADE_IA_CANONICA, default=None), T.StringType()
)
udf_resultado_ia = F.udf(
    lambda v: canonicalizar(v, RESULTADO_IA_CANONICA, default=None), T.StringType()
)
udf_usa_ia = F.udf(usa_ia_generativa, T.BooleanType())
udf_empresa_prioriza_ia = F.udf(empresa_prioriza_ia, T.BooleanType())


def mapa_regiao_spark() -> Column:
    """Constrói a expressão CASE WHEN que traduz UF em região."""
    mapa = F.create_map(
        *[x for uf, reg in UF_PARA_REGIAO.items()
          for x in (F.lit(uf), F.lit(reg))]
    )
    return mapa


def col_ou_nulo(df: DataFrame, mapeamento: dict[str, str], campo: str) -> Column:
    """
    Retorna a coluna do Bronze correspondente ao campo canônico.

    Quando a edição não tem a pergunta, devolve NULL tipado como string — o que
    mantém o union viável e deixa a ausência explícita na análise.
    """
    origem = mapeamento.get(campo)
    if origem is None:
        return F.lit(None).cast("string").alias(campo)
    return F.col(origem).cast("string").alias(campo)


def limpar_texto(coluna: Column) -> Column:
    """Trim + conversão das várias representações de vazio para NULL real."""
    limpa = F.trim(coluna)
    return F.when(
        (limpa == "") | (F.lower(limpa).isin("nan", "none", "null", "-")),
        F.lit(None),
    ).otherwise(limpa)


# ===========================================================================
# Colapso dos blocos one-hot de tecnologia em arrays
# ===========================================================================
def construir_arrays_tecnologia(
    df: DataFrame, colunas_bronze: list[str]
) -> tuple[DataFrame, list[str]]:
    """
    Acrescenta ao DataFrame um ``array<string>`` por bloco de colunas binárias.

    A pesquisa registra "quais linguagens você usa" como dezenas de colunas 0/1.
    Mantê-las soltas na Silver criaria uma tabela com centenas de colunas
    esparsas, inutilizável no Athena. Colapsamos cada bloco em um array com os
    nomes das tecnologias efetivamente marcadas pelo respondente.
    """
    grupos = resolve_multiselect(colunas_bronze)
    criados: list[str] = []

    for nome_grupo, colunas in grupos.items():
        # A opção "não utilizo nenhuma das listadas" é resposta válida, mas não
        # é uma tecnologia — mantê-la faria ela disputar o ranking com SQL.
        tecnologias = [c for c in colunas if eh_item_tecnologia(c)]

        if not tecnologias:
            # Edição sem esse bloco de perguntas. NULL (e não array vazio)
            # porque "não perguntamos" é diferente de "não usa nada": o array
            # vazio entraria no denominador da adoção e mentiria o percentual.
            df = df.withColumn(nome_grupo, F.lit(None).cast("array<string>"))
            print(f"[silver]   grupo '{nome_grupo}': ausente nesta edição")
        else:
            itens = [
                F.when(
                    udf_booleano(F.col(c).cast("string")),
                    F.lit(rotulo_item_multiselect(c)),
                )
                for c in tecnologias
            ]
            # array_compact remove os NULLs das tecnologias não marcadas
            marcadas = F.array_compact(F.array(*itens))

            # Quem NÃO chegou nesta seção do questionário tem todas as colunas
            # do bloco nulas; quem respondeu tem 0 ou 1 em cada uma. Sem essa
            # distinção, os ~40% que pularam o bloco entrariam no denominador
            # como se usassem nenhuma tecnologia, deflacionando toda a taxa de
            # adoção (Power BI cairia de 59% para 36%, por exemplo).
            respondeu_bloco = F.greatest(
                *[F.col(c).isNotNull().cast("int") for c in colunas]
            ) == F.lit(1)

            df = df.withColumn(
                nome_grupo,
                F.when(respondeu_bloco, marcadas).otherwise(
                    F.lit(None).cast("array<string>")
                ),
            )
            print(
                f"[silver]   grupo '{nome_grupo}': {len(tecnologias)} tecnologias"
                f" ({len(colunas) - len(tecnologias)} opções não-técnicas descartadas)"
            )
        criados.append(nome_grupo)

    return df, criados


# ===========================================================================
# Transformação de uma edição
# ===========================================================================
def transformar_edicao(df: DataFrame, survey_year: int) -> DataFrame:
    """Converte uma edição do Bronze no schema canônico da Silver."""
    colunas = df.columns
    mapeamento, nao_resolvidos = resolve_schema(colunas)

    print(f"\n[silver] === edição {survey_year} ===")
    print(f"[silver] {len(colunas)} colunas no bronze")
    print(f"[silver] {len(mapeamento)} campos canônicos resolvidos")
    if nao_resolvidos:
        print(
            f"[silver] AUSENTES nesta edição ({len(nao_resolvidos)}): "
            + ", ".join(nao_resolvidos)
        )

    # 1) Colapsa os blocos one-hot de tecnologia enquanto as colunas originais
    #    ainda estão disponíveis no DataFrame.
    com_tech, nomes_arrays = construir_arrays_tecnologia(df, colunas)

    # 2) Projeta os campos canônicos (ainda como texto bruto) + os arrays.
    #    Esta projeção intermediária é o que permite, no passo seguinte,
    #    referenciar os campos pelo nome canônico em vez do nome da edição.
    campos_canonicos = tuple(CANONICAL_FIELDS.keys())
    base = com_tech.select(
        *[col_ou_nulo(df, mapeamento, campo) for campo in campos_canonicos],
        *[F.col(n) for n in nomes_arrays],
    )

    # 3) Limpeza textual + normalizações de valor
    silver = (
        base.select(
            F.lit(survey_year).cast("int").alias("survey_year"),
            F.coalesce(
                limpar_texto(F.col("respondente_id")),
                F.concat_ws(
                    "_", F.lit(survey_year),
                    F.monotonically_increasing_id().cast("string"),
                ),
            ).alias("respondente_id"),
            F.col("idade").cast("int").alias("idade"),
            limpar_texto(F.col("faixa_idade")).alias("faixa_idade"),
            udf_genero(limpar_texto(F.col("genero"))).alias("genero"),
            limpar_texto(F.col("cor_raca_etnia")).alias("cor_raca_etnia"),
            udf_booleano(F.col("pcd")).alias("pcd"),
            F.upper(limpar_texto(F.col("uf_residencia"))).alias("uf_residencia"),
            limpar_texto(F.col("regiao_declarada")).alias("regiao_declarada"),
            limpar_texto(F.col("nivel_ensino")).alias("nivel_ensino"),
            limpar_texto(F.col("area_formacao")).alias("area_formacao"),
            limpar_texto(F.col("situacao_trabalho")).alias("situacao_trabalho"),
            limpar_texto(F.col("setor_empresa")).alias("setor_empresa"),
            limpar_texto(F.col("porte_empresa")).alias("porte_empresa"),
            udf_booleano(F.col("gestor")).alias("gestor"),
            udf_cargo(limpar_texto(F.col("cargo"))).alias("cargo"),
            limpar_texto(F.col("cargo")).alias("cargo_original"),
            udf_senioridade(limpar_texto(F.col("senioridade"))).alias("senioridade"),
            limpar_texto(F.col("faixa_salarial")).alias("faixa_salarial"),
            udf_salario(F.col("faixa_salarial")).alias("salario_medio_mensal"),
            limpar_texto(F.col("tempo_experiencia_dados"))
            .alias("tempo_experiencia_dados"),
            limpar_texto(F.col("tempo_experiencia_ti"))
            .alias("tempo_experiencia_ti"),
            udf_modelo(limpar_texto(F.col("modelo_trabalho")))
            .alias("modelo_trabalho"),
            limpar_texto(F.col("satisfacao_empresa")).alias("satisfacao_empresa"),
            limpar_texto(F.col("motivo_insatisfacao")).alias("motivo_insatisfacao"),
            udf_booleano(F.col("busca_nova_oportunidade"))
            .alias("busca_nova_oportunidade"),
            udf_booleano(F.col("empresa_teve_layoff")).alias("empresa_teve_layoff"),

            # --- IA generativa ---------------------------------------------
            # A pergunta original não é sim/não: o respondente descreve COMO
            # usa. Guardamos a categoria (para analisar o padrão de consumo) e
            # derivamos o booleano de adoção (para a taxa).
            udf_tipo_uso_ia(limpar_texto(F.col("tipo_uso_ia"))).alias("tipo_uso_ia"),
            udf_usa_ia(F.col("tipo_uso_ia")).alias("usa_ia_generativa"),
            udf_prioridade_ia(limpar_texto(F.col("prioridade_ia_empresa")))
            .alias("prioridade_ia_empresa"),
            udf_empresa_prioriza_ia(F.col("prioridade_ia_empresa"))
            .alias("empresa_prioriza_ia"),
            udf_resultado_ia(limpar_texto(F.col("resultado_ia_empresa")))
            .alias("resultado_ia_empresa"),

            limpar_texto(F.col("cloud_preferida")).alias("cloud_preferida"),
            udf_booleano(F.col("possui_data_lake")).alias("possui_data_lake"),
            *[F.col(n) for n in nomes_arrays],
        )
    )

    # 4) Região derivada da UF, com fallback para a região declarada
    # Região derivada da UF; a região declarada pelo respondente é o fallback
    # para quem não informou o estado. Sem UF nem região declarada fica NULL.
    silver = silver.withColumn(
        "regiao",
        F.coalesce(
            mapa_regiao_spark()[F.col("uf_residencia")],
            F.col("regiao_declarada"),
        ),
    ).drop("regiao_declarada")

    return silver


def alinhar_schemas(dfs: list[DataFrame]) -> list[DataFrame]:
    """
    Garante que todos os DataFrames tenham as mesmas colunas, na mesma ordem.

    Necessário porque ``unionByName`` com ``allowMissingColumns`` ainda exige
    tipos compatíveis; alinhar explicitamente evita surpresas silenciosas.
    """
    # Cada coluna carrega consigo o tipo da primeira edição em que apareceu.
    # Castar tudo para string quebraria os arrays de tecnologia.
    tipos: dict[str, T.DataType] = {}
    ordem: list[str] = []
    for df in dfs:
        for campo in df.schema.fields:
            if campo.name not in tipos:
                tipos[campo.name] = campo.dataType
                ordem.append(campo.name)

    alinhados = []
    for df in dfs:
        for c in ordem:
            if c not in df.columns:
                df = df.withColumn(c, F.lit(None).cast(tipos[c]))
        alinhados.append(df.select(*ordem))
    return alinhados


def main() -> None:
    args = get_args(
        {"bronze_path": "data/bronze", "silver_path": "data/silver"}
    )
    bronze_path = args["bronze_path"].rstrip("/")
    silver_path = args["silver_path"].rstrip("/")

    spark = build_spark("tc3-job-silver")
    spark.sparkContext.setLogLevel("WARN")

    # Descobre as edições pelo valor da partição — isso funciona mesmo sem
    # merge de schema, porque survey_year vem do caminho, não do arquivo.
    anos = sorted(
        r["survey_year"]
        for r in spark.read.parquet(bronze_path)
        .select("survey_year")
        .distinct()
        .collect()
    )
    print(f"[silver] edições encontradas no bronze: {anos}")

    partes = []
    for ano in anos:
        # Cada partição é lida pelo SEU caminho, e não filtrando o dataset
        # inteiro. O Spark não faz merge de schema em Parquet por padrão: ao
        # ler o diretório raiz ele adota o schema de um único arquivo, o que
        # apagaria silenciosamente as perguntas que só existem nas edições
        # mais recentes (IA generativa, por exemplo).
        edicao = spark.read.parquet(f"{bronze_path}/survey_year={ano}")
        partes.append(transformar_edicao(edicao, ano))

    alinhados = alinhar_schemas(partes)
    silver = alinhados[0]
    for outra in alinhados[1:]:
        silver = silver.unionByName(outra)

    # Um respondente não pode aparecer duas vezes na mesma edição
    silver = silver.dropDuplicates(["survey_year", "respondente_id"])

    total = silver.count()
    print(f"\n[silver] total consolidado: {total} respondentes")
    silver.groupBy("survey_year").count().orderBy("survey_year").show()

    (
        silver.write.mode("overwrite")
        .partitionBy("survey_year")
        .parquet(silver_path)
    )
    print(f"[silver] concluído -> {silver_path}")
    spark.stop()


if __name__ == "__main__":
    main()
