-- ===========================================================================
-- Tech Challenge Fase 3 — DDL do Glue Data Catalog / Amazon Athena
-- ===========================================================================
--
-- Este script cria o database e as tabelas externas apontando para as camadas
-- do Data Lake no S3.
--
-- QUANDO USAR: o caminho preferencial é o Glue Crawler (ver
-- scripts/04_criar_crawler.sh), que infere o schema sozinho. Este DDL existe
-- como alternativa determinística — útil quando o Crawler não roda por
-- limitação de role no AWS Academy Lab, e útil como documentação explícita
-- do contrato de cada tabela.
--
-- ANTES DE EXECUTAR: substitua SEU-BUCKET pelo nome real do seu bucket.
--   No editor do Athena: Ctrl+H / Cmd+H, trocar SEU-BUCKET.
--   Ou pelo terminal:  sed -i '' 's/SEU-BUCKET/meu-bucket-real/g' 01_ddl_athena.sql
--
-- Execute os blocos UM DE CADA VEZ no console do Athena (o editor não aceita
-- múltiplos statements em uma execução).
-- ===========================================================================


-- ---------------------------------------------------------------------------
-- 0. Database
-- ---------------------------------------------------------------------------
CREATE DATABASE IF NOT EXISTS state_of_data
COMMENT 'State of Data Brasil — 3 últimas edições — Tech Challenge Fase 3';


-- ===========================================================================
-- CAMADA SILVER — uma linha por respondente, schema unificado entre edições
--
-- Tabela chamada "silver" (e não "silver_respondentes") de propósito: é o
-- nome que o Glue Crawler atribui automaticamente, a partir do prefixo do S3
-- (s3://bucket/silver/). Como scripts/04_criar_crawler.sh é o caminho usado
-- de fato no deploy, manter o mesmo nome aqui evita que quem seguir só este
-- DDL manual acabe com uma tabela cujo nome não bate com o que as 28
-- consultas de sql/02_consultas_analiticas.sql esperam.
-- ===========================================================================
CREATE EXTERNAL TABLE IF NOT EXISTS state_of_data.silver (
    respondente_id            string,
    idade                     int,
    faixa_idade               string,
    genero                    string,
    cor_raca_etnia            string,
    pcd                       boolean,
    uf_residencia             string,
    nivel_ensino              string,
    area_formacao             string,
    situacao_trabalho         string,
    setor_empresa             string,
    porte_empresa             string,
    gestor                    boolean,
    cargo                     string,
    cargo_original            string,
    senioridade               string,
    faixa_salarial            string,
    salario_medio_mensal      double,
    tempo_experiencia_dados   string,
    tempo_experiencia_ti      string,
    modelo_trabalho           string,
    satisfacao_empresa        string,
    motivo_insatisfacao       string,
    busca_nova_oportunidade   boolean,
    empresa_teve_layoff       boolean,
    -- Bloco de IA generativa. A pergunta original não é sim/não: o respondente
    -- descreve COMO usa. Guardamos a categoria (tipo_uso_ia) e derivamos o
    -- booleano de adoção (usa_ia_generativa) a partir dela.
    tipo_uso_ia               string,
    usa_ia_generativa         boolean,
    prioridade_ia_empresa     string,
    empresa_prioriza_ia       boolean,
    resultado_ia_empresa      string,   -- só existe na edição 2025-26
    cloud_preferida           string,
    possui_data_lake          boolean,
    linguagens                array<string>,   -- ausente na edição 2025-26
    bancos_dados              array<string>,
    cloud_utilizada           array<string>,   -- ausente na edição 2023-24
    ferramentas_bi            array<string>,
    regiao                    string
)
PARTITIONED BY (survey_year int)
STORED AS PARQUET
LOCATION 's3://SEU-BUCKET/silver/'
TBLPROPERTIES ('parquet.compression' = 'SNAPPY');

-- Partições vêm do caminho (survey_year=2023/...). Sem este comando o Athena
-- devolve zero linhas mesmo com os arquivos no lugar.
MSCK REPAIR TABLE state_of_data.silver;


-- ===========================================================================
-- CAMADA GOLD — tabelas analíticas agregadas
-- ===========================================================================

-- --------------------------------------------------------------------------
-- Série temporal dos indicadores-chave — a base do storytelling
-- --------------------------------------------------------------------------
CREATE EXTERNAL TABLE IF NOT EXISTS state_of_data.gold_evolucao_anual (
    survey_year              int,
    total_respondentes       bigint,
    idade_media              double,
    salario_mediano_geral    double,
    pct_mulheres             double,
    pct_remoto               double,
    pct_hibrido              double,
    pct_presencial           double,
    pct_usa_ia_generativa    double,
    pct_empresa_prioriza_ia  double
)
STORED AS PARQUET
LOCATION 's3://SEU-BUCKET/gold/gold_evolucao_anual/';


-- --------------------------------------------------------------------------
-- Composição do mercado por cargo e senioridade
-- --------------------------------------------------------------------------
CREATE EXTERNAL TABLE IF NOT EXISTS state_of_data.gold_perfil_mercado (
    survey_year          int,
    cargo                string,
    senioridade          string,
    respondentes         bigint,
    idade_media          double,
    salario_mediano      double,
    pct_do_ano           double,
    amostra_suficiente   boolean
)
STORED AS PARQUET
LOCATION 's3://SEU-BUCKET/gold/gold_perfil_mercado/';


-- --------------------------------------------------------------------------
-- Remuneração — formato longo: uma linha por (ano, dimensão, categoria)
-- --------------------------------------------------------------------------
CREATE EXTERNAL TABLE IF NOT EXISTS state_of_data.gold_remuneracao (
    survey_year          int,
    dimensao             string,
    categoria            string,
    respondentes         bigint,
    salario_medio        double,
    salario_mediano      double,
    salario_p25          double,
    salario_p75          double,
    amostra_suficiente   boolean
)
STORED AS PARQUET
LOCATION 's3://SEU-BUCKET/gold/gold_remuneracao/';


-- --------------------------------------------------------------------------
-- Diversidade de gênero e gap salarial
-- --------------------------------------------------------------------------
CREATE EXTERNAL TABLE IF NOT EXISTS state_of_data.gold_diversidade_genero (
    survey_year                 int,
    senioridade                 string,
    genero                      string,
    respondentes                bigint,
    salario_mediano             double,
    pct_representatividade      double,
    salario_mediano_masculino   double,
    gap_salarial_pct            double,
    amostra_suficiente          boolean
)
STORED AS PARQUET
LOCATION 's3://SEU-BUCKET/gold/gold_diversidade_genero/';


-- --------------------------------------------------------------------------
-- Adoção de tecnologias
-- --------------------------------------------------------------------------
CREATE EXTERNAL TABLE IF NOT EXISTS state_of_data.gold_tecnologias (
    survey_year         int,
    categoria           string,
    tecnologia          string,
    usuarios            bigint,
    base_respondentes   bigint,
    pct_adocao          double
)
STORED AS PARQUET
LOCATION 's3://SEU-BUCKET/gold/gold_tecnologias/';


-- --------------------------------------------------------------------------
-- Adoção de IA generativa
-- --------------------------------------------------------------------------
CREATE EXTERNAL TABLE IF NOT EXISTS state_of_data.gold_adocao_ia (
    survey_year          int,
    cargo                string,
    senioridade          string,
    respondentes         bigint,
    base_uso_pessoal     bigint,
    usam_ia              bigint,
    base_uso_empresa     bigint,
    empresas_usam_ia     bigint,
    pct_uso_pessoal      double,
    pct_uso_empresa      double,
    amostra_suficiente   boolean
)
STORED AS PARQUET
LOCATION 's3://SEU-BUCKET/gold/gold_adocao_ia/';


-- --------------------------------------------------------------------------
-- Impacto da IA generativa — resultado obtido, não só adoção
-- (pergunta exclusiva da edição 2025-26; ver nota em job_gold.py)
-- --------------------------------------------------------------------------
CREATE EXTERNAL TABLE IF NOT EXISTS state_of_data.gold_impacto_ia (
    survey_year            int,
    resultado_ia_empresa   string,
    respondentes           bigint,
    pct                    double
)
STORED AS PARQUET
LOCATION 's3://SEU-BUCKET/gold/gold_impacto_ia/';


-- --------------------------------------------------------------------------
-- Remuneração regional controlada por senioridade
-- (a versão em gold_remuneracao com dimensao='regiao' mistura região com
-- composição de carreira — ver nota em job_gold.py)
-- --------------------------------------------------------------------------
CREATE EXTERNAL TABLE IF NOT EXISTS state_of_data.gold_remuneracao_regional (
    survey_year          int,
    regiao               string,
    senioridade          string,
    respondentes         bigint,
    salario_medio        double,
    salario_mediano      double,
    amostra_suficiente   boolean
)
STORED AS PARQUET
LOCATION 's3://SEU-BUCKET/gold/gold_remuneracao_regional/';


-- --------------------------------------------------------------------------
-- Modelos de trabalho por região
-- --------------------------------------------------------------------------
CREATE EXTERNAL TABLE IF NOT EXISTS state_of_data.gold_modelo_trabalho (
    survey_year          int,
    regiao               string,
    modelo_trabalho      string,
    respondentes         bigint,
    salario_mediano      double,
    pct_na_regiao        double,
    amostra_suficiente   boolean
)
STORED AS PARQUET
LOCATION 's3://SEU-BUCKET/gold/gold_modelo_trabalho/';


-- ===========================================================================
-- VERIFICAÇÃO — rode depois de criar tudo
-- ===========================================================================
-- SHOW TABLES IN state_of_data;
-- SELECT * FROM state_of_data.gold_evolucao_anual ORDER BY survey_year;
-- SELECT survey_year, COUNT(*) FROM state_of_data.silver
--   GROUP BY survey_year ORDER BY survey_year;
