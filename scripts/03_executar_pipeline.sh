#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Executa os 3 jobs em sequência, aguardando cada um terminar.
#
# Os jobs são encadeados por dependência de dados (silver precisa do bronze
# pronto), então rodá-los em paralelo produziria resultado incompleto — daí a
# espera explícita entre eles.
#
# Uso:
#   source scripts/00_configurar.sh
#   bash scripts/03_executar_pipeline.sh
# ---------------------------------------------------------------------------
set -euo pipefail

: "${TC3_BUCKET:?rode 'source scripts/00_configurar.sh' antes}"

executar_e_aguardar () {
    local NOME="$1"
    echo "==> disparando ${NOME}"
    local RUN_ID
    RUN_ID=$(aws glue start-job-run --job-name "$NOME" \
             --query JobRunId --output text)
    echo "    run id: ${RUN_ID}"

    local ESTADO="STARTING"
    local SEGUNDOS=0
    while [[ "$ESTADO" == "STARTING" || "$ESTADO" == "RUNNING" || "$ESTADO" == "WAITING" ]]; do
        sleep 20
        SEGUNDOS=$((SEGUNDOS + 20))
        ESTADO=$(aws glue get-job-run --job-name "$NOME" --run-id "$RUN_ID" \
                 --query 'JobRun.JobRunState' --output text)
        printf "\r    %s  (%ds)          " "$ESTADO" "$SEGUNDOS"
    done
    echo

    if [ "$ESTADO" != "SUCCEEDED" ]; then
        echo "    FALHOU (${ESTADO})"
        aws glue get-job-run --job-name "$NOME" --run-id "$RUN_ID" \
            --query 'JobRun.ErrorMessage' --output text
        echo
        echo "    Logs completos no CloudWatch:"
        echo "      /aws-glue/jobs/output  (stream ${RUN_ID})"
        exit 1
    fi

    local DPU
    DPU=$(aws glue get-job-run --job-name "$NOME" --run-id "$RUN_ID" \
          --query 'JobRun.ExecutionTime' --output text)
    echo "    SUCEDIDO em ${DPU}s"
}

executar_e_aguardar "tc3-job-bronze"
executar_e_aguardar "tc3-job-silver"
executar_e_aguardar "tc3-job-gold"

echo
echo "Pipeline concluído. Conteúdo do Data Lake:"
for camada in bronze silver gold; do
    N=$(aws s3 ls "s3://${TC3_BUCKET}/${camada}/" --recursive | wc -l | tr -d ' ')
    echo "  ${camada}: ${N} objetos"
done

echo
echo "Próximo passo: bash scripts/04_criar_crawler.sh"
