#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Executa o pipeline completo localmente, com o mesmo código PySpark que roda
# no AWS Glue. Serve para desenvolver e validar sem gastar sessão do lab.
#
# Uso:  bash scripts/rodar_local.sh
# ---------------------------------------------------------------------------
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

# shellcheck disable=SC1091
source env.sh

if ! ls data/raw/*.csv >/dev/null 2>&1; then
    echo "ERRO: nenhum CSV em data/raw/."
    echo
    echo "Baixe as 3 últimas edições do State of Data Brasil e coloque aqui:"
    echo "  https://www.kaggle.com/datasets/datahackers/state-of-data-brazil-2023"
    echo "  https://www.kaggle.com/datasets/datahackers/state-of-data-brazil-20242025"
    echo "  https://www.kaggle.com/datasets/datahackers/state-of-data-brazil-2025-2026"
    echo
    echo "Os arquivos precisam ter o ano no nome (ex.: state_of_data_2023.csv)."
    exit 1
fi

# O Spark é verborrágico demais para um log de execução legível. O filtro
# abaixo remove o ruído — e o `|| true` existe porque, com `pipefail`, um grep
# que não casa nada retorna 1 e abortaria o script mesmo com o job bem-sucedido.
# A falha real do Python continua propagando normalmente.
silenciar_spark () {
    grep -Ev "^[0-9]{2}/|WARN|^\[Stage|adjust logging" || true
}

etapa () {
    echo
    echo "######################################################################"
    echo "  $1"
    echo "######################################################################"
}

etapa "1/6  RAW -> BRONZE"
python src/glue_jobs/job_bronze.py \
    --raw_path data/raw --bronze_path data/bronze 2>&1 | silenciar_spark

etapa "2/6  BRONZE -> SILVER"
python src/glue_jobs/job_silver.py \
    --bronze_path data/bronze --silver_path data/silver 2>&1 | silenciar_spark

etapa "3/6  SILVER -> GOLD"
python src/glue_jobs/job_gold.py \
    --silver_path data/silver --gold_path data/gold 2>&1 | silenciar_spark

etapa "4/6  Diagrama da arquitetura"
python src/gerar_diagrama.py

etapa "5/6  Gráficos"
python src/gerar_graficos.py

etapa "6/6  Material executivo"
python src/gerar_apresentacao.py

echo
echo "Pipeline local concluído."
echo "  Data Lake : data/{bronze,silver,gold}/"
echo "  Gráficos  : output/charts/"
echo "  Deck      : output/Tech_Challenge_Fase3_Material_Executivo.pptx"
