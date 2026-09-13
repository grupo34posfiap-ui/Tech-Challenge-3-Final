"""
Gerador de dados sintéticos no formato do State of Data Brasil.

Serve para exercitar o pipeline ponta a ponta sem depender do download do
Kaggle — e, principalmente, para provar que a harmonização funciona quando as
edições **divergem de propósito**:

  * 2023 não tem as perguntas de IA generativa;
  * 2024 renomeia o código da pergunta de salário (P2_h -> P2_i);
  * 2025 acrescenta um bloco novo de linguagens e muda a grafia de senioridade.

Se a Silver consegue unificar estes três, unifica os reais.

Uso:
    python tests/gerar_dados_sinteticos.py --destino /tmp/tc3_fake/raw
"""
from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

random.seed(42)

UFS = ["SP", "RJ", "MG", "RS", "PR", "SC", "BA", "PE", "CE", "DF", "GO", "AM"]
GENEROS = ["Masculino", "Feminino", "Outro", "Prefiro não informar"]
CARGOS = [
    "Analista de Dados/Data Analyst",
    "Cientista de Dados/Data Scientist",
    "Engenheiro de Dados/Data Engineer",
    "Analista de BI/BI Analyst",
    "Engenheiro de Machine Learning/ML Engineer",
    "Analytics Engineer",
    "Gerente/Coordenador de Dados",
]
FAIXAS = [
    "Menos de R$ 1.000/mês",
    "de R$ 1.001/mês a R$ 2.000/mês",
    "de R$ 4.001/mês a R$ 6.000/mês",
    "de R$ 8.001/mês a R$ 12.000/mês",
    "de R$ 12.001/mês a R$ 16.000/mês",
    "de R$ 16.001/mês a R$ 20.000/mês",
    "de R$ 25.001/mês a R$ 30.000/mês",
    "Acima de R$ 40.001/mês",
]
MODELOS = ["Modelo 100% presencial", "Modelo híbrido flexível", "Modelo 100% remoto"]
SETORES = ["Finanças ou Bancos", "Tecnologia", "Varejo", "Saúde", "Indústria"]
NIVEIS = ["Graduação/Bacharelado", "Pós-graduação", "Mestrado", "Doutorado"]

LINGUAGENS = ["SQL", "Python", "R", "Scala", "Java", "JavaScript"]
BANCOS = ["MySQL", "PostgreSQL", "SQL Server", "BigQuery", "Redshift", "Oracle"]
CLOUDS = ["AWS", "Azure", "GCP"]
BIS = ["Power BI", "Tableau", "Looker Studio", "Qlik"]


def cabecalho(codigo: str, enunciado: str) -> str:
    """Reproduz o cabeçalho tupla-em-texto do Data Hackers."""
    return f"('{codigo} ', '{enunciado}')"


def montar_colunas(ano: int) -> list[str]:
    """Monta os cabeçalhos daquela edição, com as divergências propositais."""
    cols = [
        cabecalho("P0", "id"),
        cabecalho("P1_a", "Idade"),
        cabecalho("P1_b", "Genero"),
        cabecalho("P1_c", "Cor/raca/etnia"),
        cabecalho("P1_d", "PCD"),
        cabecalho("P1_i", "Estado onde mora"),
        cabecalho("P1_m", "Nivel de Ensino"),
        cabecalho("P1_n", "Área de Formação"),
        cabecalho("P2_a", "Qual sua situacao atual de trabalho?"),
        cabecalho("P2_b", "Setor da empresa"),
        cabecalho("P2_f", "Cargo Atual"),
    ]

    # Divergência 1: o código da pergunta de senioridade e salário muda de ano
    if ano == 2023:
        cols += [
            cabecalho("P2_g", "Nivel"),
            cabecalho("P2_h", "Faixa salarial"),
        ]
    else:
        cols += [
            cabecalho("P2_h", "Nivel"),
            cabecalho("P2_i", "Faixa salarial"),
        ]

    cols += [
        cabecalho("P2_r", "Forma de trabalho atual"),
        cabecalho("P2_i", "Quanto tempo de experiencia na area de dados voce tem?")
        if ano == 2023
        else cabecalho("P2_k", "Quanto tempo de experiencia na area de dados voce tem?"),
    ]

 # Divergência 2: blocos one-hot de tecnologia
    #
    # Cada bloco precisa da coluna-mãe (o enunciado da pergunta) além das
    # colunas-filhas: resolve_multiselect() acha o grupo pelo enunciado da
    # mãe e só DEPOIS coleta as filhas pelo prefixo do código dela. Sem a
    # mãe, o grupo inteiro fica invisível — mesmo com as filhas presentes.
    cols.append(cabecalho("P4_d", "Linguagem de programação (dia a dia)"))
    for i, lang in enumerate(LINGUAGENS, start=1):
        cols.append(cabecalho(f"P4_d_{i}", lang))
    cols.append(cabecalho("P4_e", "Banco de dados (dia a dia)"))
    for i, bd in enumerate(BANCOS, start=1):
        cols.append(cabecalho(f"P4_e_{i}", bd))
    cols.append(cabecalho("P4_f", "Cloud (dia a dia)"))
    for i, cl in enumerate(CLOUDS, start=1):
        cols.append(cabecalho(f"P4_f_{i}", cl))
    cols.append(cabecalho("P4_g", "Ferramenta de BI (dia a dia)"))
    for i, bi in enumerate(BIS, start=1):
        cols.append(cabecalho(f"P4_g_{i}", bi))

    # Divergência 3: IA generativa só existe a partir de 2024
    if ano >= 2024:
        cols += [
            cabecalho("P8_a", "Você utiliza IA Generativa no trabalho?"),
            cabecalho("P8_b", "Sua empresa utiliza IA Generativa?"),
        ]
    if ano >= 2025:
        cols.append(cabecalho("P8_e", "Qual o impacto da IA no seu trabalho?"))

    return cols


def gerar_linha(ano: int, idx: int) -> dict[str, str]:
    """Gera um respondente sintético coerente com a edição."""
    linha: dict[str, str] = {}
    cols = montar_colunas(ano)

    senioridade_pool = (
        ["Júnior", "Pleno", "Sênior"]
        if ano < 2025
        else ["Junior", "Pleno", "Senior", "Gerente"]  # grafia muda em 2025
    )

    valores = {
        "id": f"{ano}-{idx:05d}",
        "Idade": str(random.randint(20, 55)),
        "Genero": random.choices(GENEROS, weights=[62, 33, 3, 2])[0],
        "Cor/raca/etnia": random.choice(["Branca", "Parda", "Preta", "Amarela"]),
        "PCD": random.choices(["Sim", "Não"], weights=[5, 95])[0],
        "Estado onde mora": random.choices(UFS, weights=[38, 12, 10, 8, 7, 6, 5, 4, 3, 4, 2, 1])[0],
        "Nivel de Ensino": random.choice(NIVEIS),
        "Área de Formação": random.choice(["Computação/TI", "Estatística", "Engenharias", "Economia"]),
        "Qual sua situacao atual de trabalho?": random.choices(
            ["Empregado (CLT)", "Empregado (PJ)", "Desempregado", "Freelancer"],
            weights=[65, 20, 8, 7],
        )[0],
        "Setor da empresa": random.choice(SETORES),
        "Cargo Atual": random.choice(CARGOS),
        "Nivel": random.choice(senioridade_pool),
        "Faixa salarial": random.choices(FAIXAS, weights=[3, 8, 20, 25, 18, 12, 8, 6])[0],
        "Forma de trabalho atual": random.choices(MODELOS, weights=[20, 45, 35])[0],
        "Quanto tempo de experiencia na area de dados voce tem?": random.choice(
            ["Menos de 1 ano", "de 1 a 2 anos", "de 3 a 4 anos", "de 5 a 6 anos", "Mais de 10 anos"]
        ),
        "Você utiliza IA Generativa no trabalho?": random.choices(
            ["Sim", "Não"], weights=[70 if ano == 2024 else 88, 30 if ano == 2024 else 12]
        )[0],
        "Sua empresa utiliza IA Generativa?": random.choices(
            ["Sim", "Não"], weights=[55 if ano == 2024 else 75, 45 if ano == 2024 else 25]
        )[0],
        "Qual o impacto da IA no seu trabalho?": random.choice(
            ["Aumentou muito minha produtividade", "Aumentou pouco", "Nenhum impacto"]
        ),
    }

    # One-hot das tecnologias
    for tech_list in (LINGUAGENS, BANCOS, CLOUDS, BIS):
        for t in tech_list:
            valores[t] = random.choices(["1", "0"], weights=[35, 65])[0]
    # SQL e Python são quase universais — força a distribuição realista
    valores["SQL"] = random.choices(["1", "0"], weights=[90, 10])[0]
    valores["Python"] = random.choices(["1", "0"], weights=[80, 20])[0]

    for col in cols:
        # Recupera o enunciado de dentro do cabeçalho tupla
        enunciado = col.split("', '")[1].rstrip("')")
        linha[col] = valores.get(enunciado, "")

    return linha


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destino", required=True)
    parser.add_argument("--linhas", type=int, default=800)
    args = parser.parse_args()

    destino = Path(args.destino)
    destino.mkdir(parents=True, exist_ok=True)

    for ano, n in ((2023, args.linhas), (2024, int(args.linhas * 1.2)), (2025, int(args.linhas * 1.4))):
        cols = montar_colunas(ano)
        caminho = destino / f"state_of_data_{ano}.csv"
        with caminho.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=cols)
            writer.writeheader()
            for i in range(n):
                writer.writerow(gerar_linha(ano, i))
        print(f"gerado {caminho} — {n} linhas, {len(cols)} colunas")


if __name__ == "__main__":
    main()
