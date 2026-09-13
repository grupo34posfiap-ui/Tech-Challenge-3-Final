#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Configuração compartilhada pelos scripts de deploy na AWS
#
# Uso:  source scripts/00_configurar.sh
#
# PRÉ-REQUISITO — credenciais do AWS Academy Lab:
#   No Learner Lab, clique em "AWS Details" > "AWS CLI" e copie o bloco
#   apresentado para ~/.aws/credentials (perfil [default]).
#   As credenciais expiram junto com a sessão do lab (~4h) — quando os
#   comandos começarem a devolver "ExpiredToken", copie o bloco de novo.
# ---------------------------------------------------------------------------
set -a

# O nome do bucket precisa ser único globalmente no S3. O sufixo com o ID da
# conta evita colisão com outros grupos usando o mesmo nome de projeto.
export AWS_REGION="${AWS_REGION:-us-east-1}"

CONTA_ID="$(aws sts get-caller-identity --query Account --output text 2>/dev/null)"
if [ -z "$CONTA_ID" ] || [ "$CONTA_ID" = "None" ]; then
    echo "ERRO: não consegui autenticar na AWS."
    echo "      Copie as credenciais do Learner Lab (AWS Details > AWS CLI)"
    echo "      para ~/.aws/credentials e tente de novo."
    return 1 2>/dev/null || exit 1
fi

export TC3_BUCKET="${TC3_BUCKET:-tech-challenge-fase3-${CONTA_ID}}"
export TC3_DATABASE="state_of_data"

export S3_RAW="s3://${TC3_BUCKET}/raw"
export S3_BRONZE="s3://${TC3_BUCKET}/bronze"
export S3_SILVER="s3://${TC3_BUCKET}/silver"
export S3_GOLD="s3://${TC3_BUCKET}/gold"
export S3_SCRIPTS="s3://${TC3_BUCKET}/scripts"
export S3_ATHENA="s3://${TC3_BUCKET}/athena-results"

# O AWS Academy Lab não permite criar roles. LabRole é a role pré-provisionada
# com as permissões de S3, Glue e Athena que o pipeline precisa.
export GLUE_ROLE="${GLUE_ROLE:-arn:aws:iam::${CONTA_ID}:role/LabRole}"

# Glue 5.0 = Spark 3.5 + Python 3.11 — o mesmo runtime reproduzido em env.sh
export GLUE_VERSION="5.0"
export GLUE_WORKERS=2
export GLUE_WORKER_TYPE="G.1X"

set +a

echo "Configuração AWS carregada"
echo "  Conta    : ${CONTA_ID}"
echo "  Região   : ${AWS_REGION}"
echo "  Bucket   : ${TC3_BUCKET}"
echo "  Role     : ${GLUE_ROLE}"
echo "  Glue     : ${GLUE_VERSION} (${GLUE_WORKERS}x ${GLUE_WORKER_TYPE})"
