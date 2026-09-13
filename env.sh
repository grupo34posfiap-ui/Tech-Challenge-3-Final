#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Ambiente local do Tech Challenge Fase 3
#
# Espelha o runtime do AWS Glue 5.0 (Python 3.11 + Spark 3.5.x + Java 17), para
# que o MESMO código PySpark rode local e na AWS sem alteração.
#
# Uso:  source env.sh
# ---------------------------------------------------------------------------
set -a

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

# Java 17 — mesma major version do Glue 5.0
JAVA_HOME="/opt/homebrew/opt/openjdk@17"
PATH="$JAVA_HOME/bin:$PROJECT_ROOT/.venv/bin:$PATH"

# Driver e workers precisam do MESMO interpretador, senão o Spark aborta
PYSPARK_PYTHON="$PROJECT_ROOT/.venv/bin/python"
PYSPARK_DRIVER_PYTHON="$PROJECT_ROOT/.venv/bin/python"

# Permite importar src/ como pacote nos notebooks e jobs.
# O `:-` é necessário porque os scripts rodam com `set -u`, e PYTHONPATH
# normalmente não existe no ambiente.
PYTHONPATH="$PROJECT_ROOT/src:${PYTHONPATH:-}"

# Evita o warning de hostname resolvendo para endereço externo
SPARK_LOCAL_IP="127.0.0.1"

set +a

echo "Ambiente Tech Challenge 3 carregado"
echo "  Python : $(python --version 2>&1)"
echo "  Java   : $(java -version 2>&1 | head -1)"
