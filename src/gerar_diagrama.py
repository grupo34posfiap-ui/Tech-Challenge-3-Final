"""
Renderiza o diagrama da arquitetura AWS em PNG, para embutir no deck.

Por que este arquivo existe: o entregável oficial da arquitetura é o
``architecture/arquitetura_aws.drawio`` — editável, como o enunciado pede. Mas
exportar o .drawio para imagem exige o app do Draw.io instalado, e o deck
precisa da figura pronta. Este script gera uma versão PNG equivalente, para
que o material executivo saia completo sem dependência externa.

Se você editar o .drawio, atualize aqui também (ou exporte o .drawio como PNG
pelo app e substitua o arquivo gerado — o deck só lê o PNG).

Uso:
    python src/gerar_diagrama.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import viz_style as vs  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "output" / "charts" / "00_arquitetura.png"

# Cores oficiais das categorias de serviço AWS
VERDE_S3 = "#277116"
ROXO_ANALYTICS = "#5A30B5"
VERMELHO_IAM = "#C7131F"
ROSA_CW = "#BC1356"
GRAFITE = "#232F3E"


def caixa(ax, x, y, w, h, titulo, subtitulo="", *, cor=GRAFITE,
          preenchimento="#FFFFFF", cor_texto=None, fontsize=10.5,
          tracejado=False):
    """Desenha um bloco de serviço com título e legenda."""
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.02,rounding_size=0.12",
            linewidth=1.6, edgecolor=cor, facecolor=preenchimento,
            linestyle="--" if tracejado else "-", zorder=3,
        )
    )
    cor_texto = cor_texto or cor
    ax.text(x + w / 2, y + h * (0.62 if subtitulo else 0.5), titulo,
            ha="center", va="center", fontsize=fontsize, fontweight="bold",
            color=cor_texto, zorder=4)
    if subtitulo:
        ax.text(x + w / 2, y + h * 0.27, subtitulo, ha="center", va="center",
        fontsize=9.6, color=vs.TEXTO_SECUNDARIO, zorder=4)


def area(ax, x, y, w, h, rotulo, cor, preenchimento):
    """Área tracejada que agrupa serviços relacionados."""
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.02,rounding_size=0.15",
            linewidth=1.3, edgecolor=cor, facecolor=preenchimento,
            linestyle="--", zorder=1,
        )
    )
    ax.text(x + 0.15, y + h - 0.22, rotulo, ha="left", va="center",
            fontsize=10, fontweight="bold", color=cor, zorder=2)


def seta(ax, p1, p2, *, cor=GRAFITE, rotulo="", tracejada=False,
         curvatura=0.0, deslocamento=(0, 0)):
    """Conector direcionado entre dois pontos."""
    ax.add_patch(
        FancyArrowPatch(
            p1, p2,
            arrowstyle="-|>", mutation_scale=13,
            linewidth=1.7, color=cor, zorder=5,
            linestyle="--" if tracejada else "-",
            connectionstyle=f"arc3,rad={curvatura}",
            shrinkA=3, shrinkB=3,
        )
    )
    if rotulo:
        mx = (p1[0] + p2[0]) / 2 + deslocamento[0]
        my = (p1[1] + p2[1]) / 2 + deslocamento[1]
        ax.text(mx, my, rotulo, ha="center", va="center", fontsize=9.4,
                color=cor, zorder=6,
                bbox=dict(boxstyle="round,pad=0.22", facecolor=vs.SUPERFICIE,
                          edgecolor="none"))


def main() -> None:
    vs.aplicar_estilo()
    fig, ax = plt.subplots(figsize=(16, 8.6))
    ax.set_xlim(0, 20)
    ax.set_ylim(-1.35, 10.6)
    ax.axis("off")

    # ---------------------------------------------------------------- título
    ax.text(0, 10.25, "Arquitetura da solução — Tech Challenge Fase 3",
            fontsize=18, fontweight="bold", color=vs.TEXTO_PRIMARIO)
    ax.text(0, 9.85,
            "Ingestão  ·  Data Lake em camadas (Bronze/Silver/Gold)  ·  Catalogação  ·  "
            "Consulta analítica  ·  Storytelling executivo",
            fontsize=11, color=vs.TEXTO_SECUNDARIO)

    # ---------------------------------------------------------------- fontes
    area(ax, 0.1, 3.4, 2.5, 3.2, "Fontes", "#879196", "#F5F7F8")
    for i, (ano, rotulo) in enumerate(
        [(0, "State of Data\n2023-24"), (1, "State of Data\n2024-25"),
         (2, "State of Data\n2025-26")]
    ):
        caixa(ax, 0.35, 5.5 - i * 0.85, 2.0, 0.66, rotulo.split("\n")[0],
              rotulo.split("\n")[1], fontsize=9.4)

    # --------------------------------------------------------------- AWS box
    ax.add_patch(
        FancyBboxPatch(
            (2.95, 0.5), 14.75, 8.9,
            boxstyle="round,pad=0.02,rounding_size=0.2",
            linewidth=1.8, edgecolor=GRAFITE, facecolor="none", zorder=0,
        )
    )
    ax.text(3.2, 9.1, "AWS Cloud  ·  AWS Academy Lab  ·  us-east-1",
            fontsize=10.5, fontweight="bold", color=GRAFITE)

    # ------------------------------------------------------------- ingestão
    caixa(ax, 3.25, 4.55, 1.75, 1.0, "Ingestão",
          "AWS CLI / Console", fontsize=9.5)

    # ------------------------------------------------- S3 data lake (medalhão)
    area(ax, 5.35, 3.55, 9.4, 2.95, "Amazon S3 — Data Lake",
         "#7AA116", "#F2F8EC")

    camadas = [
        (5.65, "RAW", "CSV original", "#8C8C8C"),
        (7.85, "BRONZE", "Parquet bruto\nparticionado", "#8C6239"),
        (10.05, "SILVER", "Schema unificado\ne tratado", "#6E7B8B"),
        (12.25, "GOLD", "9 tabelas\nanalíticas", "#B8860B"),
    ]
    for x, nome, desc, cor in camadas:
        caixa(ax, x, 4.0, 2.0, 1.35, nome, desc, cor=VERDE_S3,
              cor_texto=cor, fontsize=10.5)

    # ----------------------------------------------------------- Glue Jobs
    jobs = [
        (6.75, "job_bronze", "CSV para Parquet"),
        (8.95, "job_silver", "harmoniza 3 edições"),
        (11.15, "job_gold", "agregações"),
    ]
    for x, nome, desc in jobs:
        caixa(ax, x, 6.9, 2.0, 1.1, nome, desc, cor=ROXO_ANALYTICS,
              preenchimento="#F7F3FF", fontsize=9.5)
        ax.text(x + 1.0, 8.15, "AWS Glue (PySpark)", ha="center",
                fontsize=9.2, color=ROXO_ANALYTICS, style="italic")

    # ------------------------------------------------------------ catálogo
    #
    # Dois crawlers, não um: rodar um único crawler apontando para silver E
    # gold ao mesmo tempo, com a config de TableLevelConfiguration pensada
    # para o gold (várias subpastas = várias tabelas) aplicada também à
    # silver (uma única tabela particionada), quebrava a silver em tabelas
    # fantasma (survey_year_2023, _2024, _2025). Confirmado rodando de
    # verdade — ver scripts/04_criar_crawler.sh e docs/evidencia_execucao_aws.md.
    # O Data Catalog fica ENTRE os dois crawlers (não depois dos dois) — assim
    # cada seta crawler->catalog é curta e reta, sem precisar contornar a
    # caixa vizinha.
    area(ax, 6.6, 1.0, 5.6, 2.1, "Catalogação", ROXO_ANALYTICS, "#F7F3FF")
    caixa(ax, 6.75, 1.35, 1.3, 1.05, "Crawler", "Silver",
          cor=ROXO_ANALYTICS, fontsize=9)
    caixa(ax, 8.2, 1.35, 2.3, 1.05, "Glue Data Catalog",
          "db: state_of_data", cor=ROXO_ANALYTICS, fontsize=9.5)
    caixa(ax, 10.65, 1.35, 1.3, 1.05, "Crawler", "Gold",
          cor=ROXO_ANALYTICS, fontsize=9)

    # -------------------------------------------------------------- consumo
    caixa(ax, 15.15, 4.35, 2.3, 1.35, "Amazon Athena",
          "SQL analítico\n28 consultas", cor=ROXO_ANALYTICS,
          preenchimento="#F7F3FF", fontsize=10)
    caixa(ax, 15.15, 6.9, 2.3, 1.1, "Glue Notebook",
          "Spark interativo", cor=ROXO_ANALYTICS,
          preenchimento="#F7F3FF", fontsize=9.5)
    caixa(ax, 15.15, 1.35, 2.3, 1.05, "QuickSight",
          "opcional", cor=ROXO_ANALYTICS, fontsize=9.5, tracejado=True)

    # ---------------------------------------------------- governança
    area(ax, 3.15, 1.0, 3.1, 2.1, "Segurança e observabilidade",
         VERMELHO_IAM, "#FDF3F4")
    caixa(ax, 3.4, 1.35, 1.3, 1.05, "IAM", "LabRole", cor=VERMELHO_IAM,
          fontsize=9.5)
    caixa(ax, 4.85, 1.35, 1.15, 1.05, "CloudWatch", "logs", cor=ROSA_CW,
          fontsize=9)

    # ------------------------------------------------------------ entregável
    caixa(ax, 17.85, 4.35, 1.9, 1.35, "Material\nexecutivo",
          "DataViz +\nStorytelling", cor="#B8860B",
          preenchimento="#FFF8E1", fontsize=9.5)

    # ================================================================ setas
    for i in range(3):
        seta(ax, (2.35, 5.83 - i * 0.85), (3.25, 5.05), cor="#879196")
    seta(ax, (5.0, 5.05), (5.65, 4.68), rotulo="1")

    # raw -> job_bronze -> bronze
    seta(ax, (6.65, 5.35), (7.2, 6.9), cor=ROXO_ANALYTICS)
    seta(ax, (8.35, 6.9), (8.85, 5.35), cor=ROXO_ANALYTICS, rotulo="2")
    # bronze -> job_silver -> silver
    seta(ax, (8.85, 5.35), (9.4, 6.9), cor=ROXO_ANALYTICS)
    seta(ax, (10.55, 6.9), (11.05, 5.35), cor=ROXO_ANALYTICS, rotulo="3")
    # silver -> job_gold -> gold
    seta(ax, (11.05, 5.35), (11.6, 6.9), cor=ROXO_ANALYTICS)
    seta(ax, (12.75, 6.9), (13.25, 5.35), cor=ROXO_ANALYTICS, rotulo="4")

    # crawler — um par de setas para cada um dos dois crawlers
    seta(ax, (11.05, 4.0), (7.4, 2.4), cor=ROXO_ANALYTICS, tracejada=True,
         rotulo="5")
    seta(ax, (13.25, 4.0), (11.3, 2.4), cor=ROXO_ANALYTICS, tracejada=True)
    # Catalog fica entre os dois crawlers — cada seta é curta e reta.
    seta(ax, (8.05, 1.875), (8.2, 1.875), cor=ROXO_ANALYTICS, rotulo="6",
         deslocamento=(0, 0.35))
    seta(ax, (10.65, 1.875), (10.5, 1.875), cor=ROXO_ANALYTICS)
    seta(ax, (9.35, 2.4), (15.6, 4.35), cor=ROXO_ANALYTICS, rotulo="7",
         curvatura=-0.15)

    # gold -> athena
    seta(ax, (14.25, 4.68), (15.15, 4.9), rotulo="8")
    seta(ax, (13.4, 5.35), (15.15, 7.2), cor=ROXO_ANALYTICS, tracejada=True,
         curvatura=0.12)
    # athena -> entregável
    seta(ax, (17.45, 5.02), (17.85, 5.02), cor="#B8860B", rotulo="9",
         deslocamento=(0, 0.32))
    seta(ax, (16.3, 6.9), (16.3, 5.7), cor="#B8860B", tracejada=True)
    seta(ax, (16.3, 4.35), (16.3, 2.4), cor=ROXO_ANALYTICS, tracejada=True)

    # ------------------------------------------------------------- legenda
    passos = (
        "1  Upload dos 3 CSVs brutos para a zona RAW        "
        "2  job_bronze: normaliza cabeçalhos e grava Parquet particionado\n"
        "3  job_silver: harmoniza as 3 edições num schema canônico único   "
        "4  job_gold: gera as 9 tabelas analíticas agregadas\n"
        "5-6  Dois crawlers (Silver e Gold) populam o Data Catalog — bronze não é catalogado        "
        "7-8  Athena consulta as tabelas via SQL        "
        "9  Resultados alimentam os gráficos e a narrativa executiva"
    )
    ax.text(0.1, -1.25, passos, fontsize=9, color=vs.TEXTO_SECUNDARIO,
            va="bottom", linespacing=1.7)

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(SAIDA, bbox_inches="tight", facecolor=vs.SUPERFICIE, dpi=200)
    plt.close(fig)
    print(f"gerado  {SAIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
