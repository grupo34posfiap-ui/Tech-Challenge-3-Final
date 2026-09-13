#!/usr/bin/env bash
set -euo pipefail

: "${TC3_BUCKET:?rode 'source scripts/00_configurar.sh' antes}"

CRAWLER_SILVER="tc3-crawler-silver"
CRAWLER_GOLD="tc3-crawler-gold"

echo "==> garantindo o database ${TC3_DATABASE}"
aws glue create-database \
    --database-input "{\"Name\": \"${TC3_DATABASE}\",
                       \"Description\": \"State of Data Brasil — Tech Challenge Fase 3\"}" \
    2>/dev/null || echo "    já existe"

ALVO_SILVER=$(cat <<JSON
{"S3Targets": [{"Path": "${S3_SILVER}/"}]}
JSON
)
CONFIG_SILVER='{"Version":1.0,"CrawlerOutput":{"Partitions":{"AddOrUpdateBehavior":"InheritFromTable"}}}'

ALVO_GOLD=$(cat <<JSON
{"S3Targets": [{"Path": "${S3_GOLD}/"}]}
JSON
)
CONFIG_GOLD='{"Version":1.0,"Grouping":{"TableLevelConfiguration":3},"CrawlerOutput":{"Partitions":{"AddOrUpdateBehavior":"InheritFromTable"}}}'

criar_ou_atualizar_crawler () {
    local NOME="$1" ALVOS="$2" CONFIG="$3"
    if aws glue get-crawler --name "$NOME" >/dev/null 2>&1; then
        aws glue update-crawler --name "$NOME" --role "$GLUE_ROLE" \
            --database-name "$TC3_DATABASE" --targets "$ALVOS" \
            --configuration "$CONFIG" >/dev/null
    else
        aws glue create-crawler --name "$NOME" --role "$GLUE_ROLE" \
            --database-name "$TC3_DATABASE" --targets "$ALVOS" \
            --configuration "$CONFIG" >/dev/null
    fi
}

aguardar_crawler () {
    local NOME="$1"
    local ESTADO="RUNNING"
    local SEGUNDOS=0
    while [ "$ESTADO" != "READY" ]; do
        sleep 15
        SEGUNDOS=$((SEGUNDOS + 15))
        ESTADO=$(aws glue get-crawler --name "$NOME" \
                 --query 'Crawler.State' --output text)
        printf "\r    %s  (%ds)          " "$ESTADO" "$SEGUNDOS"
    done
    echo
}

if aws glue get-crawler --name "tc3-crawler-datalake" >/dev/null 2>&1; then
    echo "==> removendo crawler antigo tc3-crawler-datalake"
    aws glue delete-crawler --name "tc3-crawler-datalake" >/dev/null
fi
for TABELA_ERRADA in survey_year_2023 survey_year_2024 survey_year_2025; do
    aws glue delete-table --database-name "$TC3_DATABASE" --name "$TABELA_ERRADA" \
        >/dev/null 2>&1 || true
done

criar_ou_atualizar_crawler "$CRAWLER_SILVER" "$ALVO_SILVER" "$CONFIG_SILVER"
criar_ou_atualizar_crawler "$CRAWLER_GOLD" "$ALVO_GOLD" "$CONFIG_GOLD"

echo "==> executando crawler da silver"
aws glue start-crawler --name "$CRAWLER_SILVER"
aguardar_crawler "$CRAWLER_SILVER"

echo "==> executando crawler da gold"
aws glue start-crawler --name "$CRAWLER_GOLD"
aguardar_crawler "$CRAWLER_GOLD"

echo
echo "Tabelas catalogadas em ${TC3_DATABASE}:"
aws glue get-tables --database-name "$TC3_DATABASE" \
    --query 'TableList[].{Tabela:Name,Colunas:length(StorageDescriptor.Columns)}' \
    --output table

echo
echo "==> configurando o local de resultados do Athena"
aws athena update-work-group --work-group primary \
    --configuration-updates \
    "ResultConfigurationUpdates={OutputLocation=${S3_ATHENA}/}" 2>/dev/null \
    || echo "    configure manualmente no console: Athena > Settings > ${S3_ATHENA}/"

echo
echo "Pronto. Abra o Athena e rode as consultas de sql/02_consultas_analiticas.sql"
