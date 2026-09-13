#!/usr/bin/env python3
"""
Roda as 28 consultas de sql/02_consultas_analiticas.sql contra o Athena de
verdade (não simulação local) e confirma o status de cada uma.

Usado para reverificar o pipeline depois de qualquer mudança que toque nas
camadas Silver/Gold — a garantia de que "SUCCEEDED no Athena" não é uma
alegação, é reproduzível rodando este script.

Pré-requisito: `source scripts/00_configurar.sh` (credenciais + TC3_DATABASE
já exportados).

Uso:
    source scripts/00_configurar.sh
    python3 scripts/05_verificar_athena.py
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SQL_FILE = RAIZ / "sql" / "02_consultas_analiticas.sql"


def aws(*args: str) -> str:
    resultado = subprocess.run(
        ["aws", *args], capture_output=True, text=True, check=False
    )
    if resultado.returncode != 0:
        raise RuntimeError(resultado.stderr.strip())
    return resultado.stdout.strip()


def extrair_consultas(caminho: Path) -> list[tuple[str, str]]:
    """
    Divide o arquivo em (rótulo, sql) por statement, usando o comentário
    "-- N.M — descrição" imediatamente anterior como rótulo.
    """
    texto = caminho.read_text(encoding="utf-8")
    linhas = texto.split("\n")

    consultas: list[tuple[str, str]] = []
    rotulo_atual = "?"
    buffer: list[str] = []

    padrao_rotulo = re.compile(r"^--\s*(\d+\.\d+)\s*[—-]\s*(.+)$")

    for linha in linhas:
        m = padrao_rotulo.match(linha.strip())
        if m:
            rotulo_atual = f"{m.group(1)} — {m.group(2)}"
            continue
        if linha.strip().startswith("--") or not linha.strip():
            continue
        buffer.append(linha)
        if linha.rstrip().endswith(";"):
            sql = "\n".join(buffer).strip()
            if sql:
                consultas.append((rotulo_atual, sql))
            buffer = []

    return consultas


def rodar_consulta(sql: str, database: str, output_location: str) -> dict:
    execution_id = aws(
        "athena", "start-query-execution",
        "--query-string", sql,
        "--query-execution-context", f"Database={database}",
        "--result-configuration", f"OutputLocation={output_location}",
        "--query", "QueryExecutionId", "--output", "text",
    )

    estado = "RUNNING"
    while estado in ("QUEUED", "RUNNING"):
        time.sleep(2)
        saida = aws(
            "athena", "get-query-execution",
            "--query-execution-id", execution_id,
            "--output", "json",
        )
        info = json.loads(saida)["QueryExecution"]
        estado = info["Status"]["State"]

    return {
        "execution_id": execution_id,
        "estado": estado,
        "razao": info["Status"].get("StateChangeReason", ""),
        "bytes_escaneados": info.get("Statistics", {}).get(
            "DataScannedInBytes", 0
        ),
    }


def main() -> None:
    database = os.environ.get("TC3_DATABASE", "state_of_data")
    bucket = os.environ.get("TC3_BUCKET")
    if not bucket:
        print("ERRO: rode 'source scripts/00_configurar.sh' antes.")
        sys.exit(1)
    output_location = f"s3://{bucket}/athena-results/"

    consultas = extrair_consultas(SQL_FILE)
    print(f"{len(consultas)} consultas encontradas em {SQL_FILE.name}\n")

    sucesso = 0
    falha = 0
    linhas_resultado = []

    for rotulo, sql in consultas:
        try:
            r = rodar_consulta(sql, database, output_location)
        except RuntimeError as exc:
            print(f"  [ERRO CLI] {rotulo}: {exc}")
            falha += 1
            continue

        if r["estado"] == "SUCCEEDED":
            sucesso += 1
            gb = r["bytes_escaneados"] / 1e9
            print(f"  OK       {rotulo}  ({gb:.4f} GB escaneados)")
        else:
            falha += 1
            print(f"  FALHOU   {rotulo}  — {r['estado']}: {r['razao']}")

        linhas_resultado.append(
            f"| {rotulo} | {r['estado']} | `{r['execution_id']}` |"
        )

    print(f"\nResumo: {sucesso}/{len(consultas)} SUCCEEDED, {falha} falhas")

    saida_md = RAIZ / "docs" / "athena_execucao_atual.md"
    saida_md.write_text(
        "# Execução das 28 consultas — verificação atual\n\n"
        f"Rodado via `python3 scripts/05_verificar_athena.py` contra o "
        f"Athena real (banco `{database}`).\n\n"
        "| Consulta | Status | Query Execution ID |\n"
        "|---|---|---|\n" + "\n".join(linhas_resultado) + "\n\n"
        f"**Resultado: {sucesso}/{len(consultas)} SUCCEEDED, {falha} "
        "falhas.**\n",
        encoding="utf-8",
    )
    print(f"\nRelatório salvo em {saida_md.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
