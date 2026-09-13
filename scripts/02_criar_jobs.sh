#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Cria (ou atualiza) os 3 Glue Jobs do pipeline.
#
# Uso:
#   source scripts/00_configurar.sh
#   bash scripts/02_criar_jobs.sh
# ---------------------------------------------------------------------------
set -euo pipefail

: "${TC3_BUCKET:?rode 'source scripts/00_configurar.sh' antes}"

criar_job () {
    local NOME="$1" SCRIPT="$2" ARG_ENTRADA="$3" VAL_ENTRADA="$4" \
          ARG_SAIDA="$5" VAL_SAIDA="$6"

    # --additional-python-modules não é necessário: o pipeline usa só a stdlib
    # e o próprio PySpark. --extra-py-files carrega nossos módulos internos.
    local ARGS
    ARGS=$(cat <<JSON
{
  "--${ARG_ENTRADA}": "${VAL_ENTRADA}",
  "--${ARG_SAIDA}": "${VAL_SAIDA}",
  "--extra-py-files": "${S3_SCRIPTS}/tc3_modulos.zip",
  "--enable-metrics": "true",
  "--enable-continuous-cloudwatch-log": "true",
  "--enable-spark-ui": "true",
  "--spark-event-logs-path": "s3://${TC3_BUCKET}/spark-logs/",
  "--job-language": "python"
}
JSON
)

    local COMANDO="Name=glueetl,ScriptLocation=${S3_SCRIPTS}/${SCRIPT},PythonVersion=3"

    if aws glue get-job --job-name "$NOME" >/dev/null 2>&1; then
        echo "==> atualizando job ${NOME}"
        aws glue update-job --job-name "$NOME" --job-update "{
            \"Role\": \"${GLUE_ROLE}\",
            \"Command\": {\"Name\": \"glueetl\",
                          \"ScriptLocation\": \"${S3_SCRIPTS}/${SCRIPT}\",
                          \"PythonVersion\": \"3\"},
            \"DefaultArguments\": ${ARGS},
            \"GlueVersion\": \"${GLUE_VERSION}\",
            \"NumberOfWorkers\": ${GLUE_WORKERS},
            \"WorkerType\": \"${GLUE_WORKER_TYPE}\",
            \"Timeout\": 60
        }" >/dev/null
    else
        echo "==> criando job ${NOME}"
        aws glue create-job \
            --name "$NOME" \
            --role "$GLUE_ROLE" \
            --command "$COMANDO" \
            --default-arguments "$ARGS" \
            --glue-version "$GLUE_VERSION" \
            --number-of-workers "$GLUE_WORKERS" \
            --worker-type "$GLUE_WORKER_TYPE" \
            --timeout 60 >/dev/null
    fi
    echo "    ok"
}

criar_job "tc3-job-bronze" "job_bronze.py" \
          "raw_path"    "$S3_RAW"    "bronze_path" "$S3_BRONZE"

criar_job "tc3-job-silver" "job_silver.py" \
          "bronze_path" "$S3_BRONZE" "silver_path" "$S3_SILVER"

criar_job "tc3-job-gold" "job_gold.py" \
          "silver_path" "$S3_SILVER" "gold_path"   "$S3_GOLD"

echo
echo "Jobs criados. Próximo passo: bash scripts/03_executar_pipeline.sh"
