#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Cria o bucket do Data Lake, envia os CSVs brutos e publica os scripts Glue.
#
# Uso:
#   source scripts/00_configurar.sh
#   bash scripts/01_provisionar.sh
# ---------------------------------------------------------------------------
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${TC3_BUCKET:?rode 'source scripts/00_configurar.sh' antes}"

echo "==> 1/4  Criando bucket ${TC3_BUCKET}"
if aws s3api head-bucket --bucket "$TC3_BUCKET" 2>/dev/null; then
    echo "    bucket já existe, seguindo"
else
    # us-east-1 é a única região que NÃO aceita LocationConstraint
    if [ "$AWS_REGION" = "us-east-1" ]; then
        aws s3api create-bucket --bucket "$TC3_BUCKET" --region "$AWS_REGION"
    else
        aws s3api create-bucket --bucket "$TC3_BUCKET" --region "$AWS_REGION" \
            --create-bucket-configuration "LocationConstraint=${AWS_REGION}"
    fi
    # O Data Lake não deve ser público em hipótese alguma
    aws s3api put-public-access-block --bucket "$TC3_BUCKET" \
        --public-access-block-configuration \
        "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
    echo "    criado com acesso público bloqueado"
fi

echo "==> 2/4  Enviando CSVs brutos para ${S3_RAW}/"
if ! ls "${RAIZ}"/data/raw/*.csv >/dev/null 2>&1; then
    echo "ERRO: nenhum CSV em data/raw/."
    echo "      Baixe as 3 edições do Kaggle antes de rodar este script."
    exit 1
fi
aws s3 sync "${RAIZ}/data/raw/" "${S3_RAW}/" --exclude "*" --include "*.csv"

echo "==> 3/4  Empacotando módulos Python compartilhados"
# Os jobs importam schema_utils/mappings/job_bronze. No Glue esses módulos
# precisam viajar num .zip informado em --extra-py-files.
PACOTE="$(mktemp -d)/tc3_modulos.zip"
(
    cd "${RAIZ}/src"
    zip -q -r "$PACOTE" schema_utils.py mappings.py config.py
    cd glue_jobs && zip -q "$PACOTE" job_bronze.py
)
aws s3 cp "$PACOTE" "${S3_SCRIPTS}/tc3_modulos.zip"
echo "    ${S3_SCRIPTS}/tc3_modulos.zip"

echo "==> 4/4  Publicando os scripts dos jobs"
for job in job_bronze job_silver job_gold; do
    aws s3 cp "${RAIZ}/src/glue_jobs/${job}.py" "${S3_SCRIPTS}/${job}.py"
done

echo
echo "Provisionamento concluído."
echo "Próximo passo: bash scripts/02_criar_jobs.sh"
