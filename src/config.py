"""
Configuração central do pipeline — Tech Challenge Fase 3.

Um único ponto de verdade para caminhos, nomes de camadas e identificação das
pesquisas. Tanto a execução local quanto os Glue Jobs leem daqui (os jobs
recebem os caminhos S3 como argumentos, com estes valores como default).
"""
from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------
# Raiz do projeto
# --------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
BRONZE_DIR = DATA_DIR / "bronze"
SILVER_DIR = DATA_DIR / "silver"
GOLD_DIR = DATA_DIR / "gold"

OUTPUT_DIR = PROJECT_ROOT / "output"
CHARTS_DIR = OUTPUT_DIR / "charts"

# --------------------------------------------------------------------------
# AWS — sobrescreva via variável de ambiente ao rodar no Academy Lab
# --------------------------------------------------------------------------
S3_BUCKET = os.environ.get("TC3_BUCKET", "tech-challenge-fase3-datalake")

S3_RAW = f"s3://{S3_BUCKET}/raw"
S3_BRONZE = f"s3://{S3_BUCKET}/bronze"
S3_SILVER = f"s3://{S3_BUCKET}/silver"
S3_GOLD = f"s3://{S3_BUCKET}/gold"
S3_ATHENA_RESULTS = f"s3://{S3_BUCKET}/athena-results"

GLUE_DATABASE = "state_of_data"
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# --------------------------------------------------------------------------
# As 3 últimas pesquisas State of Data Brasil disponíveis no Data Hackers
#
# `survey_year` é a chave de partição usada em todas as camadas. Usamos o ano
# de INÍCIO da coleta, que é como a comunidade referencia cada edição.
# --------------------------------------------------------------------------
SURVEYS = [
    {
        "survey_year": 2023,
        "label": "2023-2024",
        "kaggle": "datahackers/state-of-data-brazil-2023",
    },
    {
        "survey_year": 2024,
        "label": "2024-2025",
        "kaggle": "datahackers/state-of-data-brazil-20242025",
    },
    {
        "survey_year": 2025,
        "label": "2025-2026",
        "kaggle": "datahackers/state-of-data-brazil-2025-2026",
    },
]

SURVEY_YEARS = [s["survey_year"] for s in SURVEYS]

# --------------------------------------------------------------------------
# Tabelas da camada Gold — cada uma vira um prefixo no S3 e uma tabela no
# Glue Data Catalog consultável pelo Athena.
# --------------------------------------------------------------------------
GOLD_TABLES = [
    "gold_perfil_mercado",
    "gold_remuneracao",
    "gold_diversidade_genero",
    "gold_tecnologias",
    "gold_adocao_ia",
    "gold_modelo_trabalho",
    "gold_evolucao_anual",
]


def ensure_local_dirs() -> None:
    """Cria a árvore de diretórios local usada pela execução fora da AWS."""
    for d in (RAW_DIR, BRONZE_DIR, SILVER_DIR, GOLD_DIR, CHARTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
