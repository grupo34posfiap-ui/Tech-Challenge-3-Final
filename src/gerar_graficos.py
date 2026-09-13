"""
Gera os gráficos do material executivo a partir da camada Gold.

Cada função produz UM gráfico que responde a UMA pergunta do enunciado. A
camada Gold já vem agregada e é pequena (centenas de linhas), então aqui usamos
pandas — subir um Spark para ler 200 linhas seria desperdício.

Decisões analíticas que atravessam o arquivo:

  * **Mediana para comparar carreiras, média para comparar regiões.** A pesquisa
    coleta salário em faixas largas; a mediana de quase toda região cai na mesma
    faixa (R$ 8.001–12.000) e some com a diferença regional. A média preserva o
    contraste porque é sensível à cauda. Onde a média é usada, o gráfico diz.
  * **Recortes com menos de 30 respondentes ficam fora**, não viram barra fina.
  * **Ausência de dado nunca vira zero.** 2023 não perguntou sobre cloud; 2025
    removeu o bloco de linguagens. Esses pontos são omitidos, não zerados.

Uso:
    python src/gerar_graficos.py
"""
from __future__ import annotations

import glob
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import viz_style as vs  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
GOLD = RAIZ / "data" / "gold"
SAIDA = RAIZ / "output" / "charts"

ANO_RECENTE = 2025


def ler_gold(tabela: str) -> pd.DataFrame:
    """Lê uma tabela Gold (um único Parquet por tabela)."""
    arquivos = glob.glob(str(GOLD / tabela / "*.parquet"))
    if not arquivos:
        raise FileNotFoundError(
            f"Tabela Gold '{tabela}' não encontrada. "
            "Rode antes: bash scripts/rodar_local.sh"
        )
    return pd.read_parquet(arquivos[0])


def salvar(fig, nome: str) -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    caminho = SAIDA / f"{nome}.png"
    fig.savefig(caminho, bbox_inches="tight", facecolor=vs.SUPERFICIE)
    plt.close(fig)
    print(f"  gerado  {caminho.relative_to(RAIZ)}")


def reais(valor: float, curto: bool = True) -> str:
    """Formata em reais. Acima de mil, abrevia — eixo com 6 dígitos vira ruído."""
    if pd.isna(valor):
        return "—"
    if curto and abs(valor) >= 1000:
        return f"R$ {valor / 1000:.1f}k".replace(".", ",")
    return f"R$ {valor:,.0f}".replace(",", ".")


# ===========================================================================
# P1 — Como está estruturado o mercado brasileiro de dados?
# ===========================================================================
def grafico_composicao_mercado() -> None:
    """Barras horizontais: quantos profissionais em cada família de carreira."""
    df = ler_gold("gold_perfil_mercado")
    df = df[(df.survey_year == ANO_RECENTE) & df.cargo.notna()]
    comp = (
        df.groupby("cargo", as_index=False)["respondentes"].sum()
        .sort_values("respondentes", ascending=True)
    )
    comp = comp[comp.respondentes >= 30]
    total = comp.respondentes.sum()

    fig, ax = plt.subplots(figsize=(10, 6.5))
    # Magnitude com ordem natural -> rampa sequencial de uma única matiz.
    cores = vs.rampa_sequencial(len(comp))[::-1]
    ax.barh(comp.cargo, comp.respondentes, height=0.68, color=cores, zorder=3)

    rotulos = [
        f"{v:,}".replace(",", ".") + f"  ({v / total * 100:.0f}%)"
        for v in comp.respondentes
    ]
    vs.rotular_barras_h(ax, comp.respondentes.tolist(), rotulos)

    vs.grade_x(ax)
    ax.set_xlim(0, comp.respondentes.max() * 1.22)
    ax.set_xticks([])
    vs.titular(
        ax,
        "Analista de Dados é a maior porta de entrada do mercado",
        f"Composição por família de carreira — edição {ANO_RECENTE}-26 "
        f"({total:,} profissionais com cargo declarado)".replace(",", "."),
    )
    vs.creditar(fig)
    salvar(fig, "01_composicao_mercado")


def grafico_piramide_senioridade() -> None:
    """Barras empilhadas 100%: distribuição de senioridade em cada edição."""
    df = ler_gold("gold_perfil_mercado")
    df = df[df.senioridade.notna()]
    pivot = (
        df.pivot_table(
            index="survey_year", columns="senioridade",
            values="respondentes", aggfunc="sum",
        ).fillna(0)
    )
    ordem = [c for c in vs.ORDEM_SENIORIDADE if c in pivot.columns]
    pivot = pivot[ordem]
    pct = pivot.div(pivot.sum(axis=1), axis=0) * 100

    fig, ax = plt.subplots(figsize=(10.5, 4.2))
    esquerda = np.zeros(len(pct))
    GAP = 0.35  # respiro entre segmentos, em pontos percentuais

    for i, nivel in enumerate(ordem):
        valores = pct[nivel].to_numpy()
        ax.barh(
            pct.index.astype(str), valores, left=esquerda, height=0.42,
            color=vs.COR_SENIORIDADE[nivel], label=nivel, zorder=3,
        )
        # Rótulo direto só onde o segmento comporta — número espremido não é lido
        for j, (v, e) in enumerate(zip(valores, esquerda)):
            if v >= 7:
                ax.text(
                    e + v / 2, j, f"{v:.0f}%", ha="center", va="center",
                    color="white", fontsize=10, fontweight="bold",
                )
        esquerda = esquerda + valores + GAP

    ax.set_xlim(0, 101 + GAP * len(ordem))
    ax.set_xticks([])
    ax.set_yticks(range(len(pct)))
    ax.set_yticklabels([f"{a}-{str(a + 1)[-2:]}" for a in pct.index])
    ax.invert_yaxis()
    vs.grade_x(ax)
    ax.grid(False)
    ax.legend(
        loc="lower center", bbox_to_anchor=(0.5, -0.30),
        ncol=len(ordem), handlelength=1.2, handleheight=1.2,
    )
    ax.set_ylabel("")
    vs.titular(
        ax,
        "A fatia de Júnior encolheu ao longo das três edições",
        "Distribuição de senioridade entre os profissionais com nível declarado "
        "— Especialista/Staff+ só existe como opção a partir de 2025-26",
    )
    vs.creditar(fig, y=-0.14)
    salvar(fig, "02_piramide_senioridade")


# ===========================================================================
# P2 — Quais perfis são mais valorizados?
# ===========================================================================
def grafico_premio_senioridade() -> None:
    """Salário mediano por senioridade, com o múltiplo em relação ao Júnior."""
    df = ler_gold("gold_remuneracao")
    df = df[
        (df.dimensao == "senioridade")
        & (df.survey_year == ANO_RECENTE)
        & df.amostra_suficiente
    ]
    ordem = [c for c in vs.ORDEM_SENIORIDADE if c in set(df.categoria)]
    df = df.set_index("categoria").loc[ordem].reset_index()

    base = df.salario_mediano.iloc[0]

    fig, ax = plt.subplots(figsize=(9.5, 5))
    cores = vs.rampa_sequencial(len(df))[::-1]
    ax.bar(df.categoria, df.salario_mediano, width=0.55, color=cores, zorder=3)

    for i, linha in df.iterrows():
        multiplo = linha.salario_mediano / base
        rotulo = reais(linha.salario_mediano, curto=False)
        if i > 0:
            rotulo += f"\n{multiplo:.1f}x o Júnior"
        ax.text(
            i, linha.salario_mediano * 1.03, rotulo,
            ha="center", va="bottom", fontsize=10.5, color=vs.TEXTO_SECUNDARIO,
        )

    vs.grade_y(ax)
    ax.set_ylim(0, df.salario_mediano.max() * 1.3)
    ax.set_yticks([])
    ax.spines["bottom"].set_color(vs.GRADE)
    vs.titular(
        ax,
        "Chegar a Sênior quadruplica o salário; Especialista/Staff+ vai além",
        f"Salário mediano mensal por senioridade — edição {ANO_RECENTE}-26",
    )
    vs.creditar(fig)
    salvar(fig, "03_premio_senioridade")


def grafico_salario_por_cargo() -> None:
    """
    Salário por família de carreira, mostrando a faixa interquartil.

    A barra sozinha esconderia que ML Engineer tem dispersão muito maior que
    Analista de Dados — e dispersão é exatamente o que um time de recrutamento
    precisa saber para montar uma proposta.
    """
    df = ler_gold("gold_remuneracao")
    df = df[
        (df.dimensao == "cargo")
        & (df.survey_year == ANO_RECENTE)
        & df.amostra_suficiente
        & (df.categoria != "Outros")
    ].sort_values("salario_mediano")

    fig, ax = plt.subplots(figsize=(10.5, 6.5))
    y = np.arange(len(df))

    # Faixa p25–p75 como régua de fundo; a mediana como o marcador que importa.
    ax.hlines(y, df.salario_p25, df.salario_p75,
              color=vs.RECUADO, linewidth=7, zorder=2)
    # Ênfase: o cargo mais bem pago recebe a cor de destaque, o resto recua
    cores = [vs.DESTAQUE if i == len(df) - 1 else "#7fa8d9" for i in range(len(df))]
    ax.scatter(df.salario_mediano, y, s=110, color=cores, zorder=4,
               edgecolor=vs.SUPERFICIE, linewidth=2)

    ax.set_yticks(y)
    ax.set_yticklabels(df.categoria)

    # Rótulos alinhados numa coluna própria à direita, e não colados ao fim de
    # cada barra: quando mediana e p75 coincidem, o texto cobriria o marcador.
    limite = df.salario_p75.max() * 1.30
    coluna_rotulo = df.salario_p75.max() * 1.06
    for i, linha in enumerate(df.itertuples()):
        ax.text(
            coluna_rotulo, i,
            f"{reais(linha.salario_mediano)}   n={linha.respondentes}",
            va="center", ha="left", fontsize=10, color=vs.TEXTO_SECUNDARIO,
        )

    vs.grade_x(ax)
    ax.set_xlim(0, limite)
    ax.set_xticks([0, 5000, 10000, 15000, 20000, 25000])
    ax.set_xticklabels(["0", "5k", "10k", "15k", "20k", "25k"])
    ax.set_xlabel(
        "Salário mensal em R$ — mediana (ponto) e faixa entre o 1º e o 3º quartil (barra)"
    )
    vs.titular(
        ax,
        "Engenharia de ML e de Dados lideram a remuneração",
        f"Remuneração por família de carreira — edição {ANO_RECENTE}-26 "
        "(apenas recortes com 30+ respondentes)",
    )
    vs.creditar(fig)
    salvar(fig, "04_salario_por_cargo")


# ===========================================================================
# P3 — Diversidade de gênero
# ===========================================================================
def grafico_representatividade_genero() -> None:
    """Série temporal da representatividade feminina — uma série, sem legenda."""
    df = ler_gold("gold_evolucao_anual").sort_values("survey_year")

    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(df.survey_year, df.pct_mulheres, marker="o",
            color=vs.COR_GENERO["Feminino"], zorder=3)

    for _, linha in df.iterrows():
        ax.annotate(
            f"{linha.pct_mulheres:.1f}%",
            (linha.survey_year, linha.pct_mulheres),
            textcoords="offset points", xytext=(0, 12),
            ha="center", fontsize=11, color=vs.TEXTO_SECUNDARIO,
        )

    vs.grade_y(ax)
    ax.set_xticks(df.survey_year)
    ax.set_xticklabels([f"{a}-{str(a + 1)[-2:]}" for a in df.survey_year])
    ax.set_ylim(0, max(df.pct_mulheres) * 1.6)
    ax.set_yticks([])
    ax.spines["bottom"].set_color(vs.GRADE)
    vs.titular(
        ax,
        "A participação feminina está recuando, não avançando",
        "Percentual de mulheres entre os respondentes, por edição da pesquisa",
    )
    vs.creditar(fig)
    salvar(fig, "05_representatividade_genero")


def grafico_gap_salarial_genero() -> None:
    """
    Gap salarial feminino por senioridade — barras divergentes em torno do zero.

    Controlar por senioridade é o que separa "mulheres ganham menos" de
    "mulheres estão concentradas em cargos juniores". As duas coisas são
    problemas, mas exigem respostas diferentes da empresa.
    """
    df = ler_gold("gold_diversidade_genero")
    df = df[
        (df.survey_year == ANO_RECENTE)
        & (df.genero == "Feminino")
        & df.amostra_suficiente
    ]
    ordem = [c for c in vs.ORDEM_SENIORIDADE if c in set(df.senioridade)]
    df = df.set_index("senioridade").loc[ordem].reset_index()

    fig, ax = plt.subplots(figsize=(9.5, 5))
    cores = [
        vs.DIVERGENTE_NEGATIVO if v < 0 else vs.DIVERGENTE_POSITIVO
        for v in df.gap_salarial_pct
    ]
    ax.barh(df.senioridade, df.gap_salarial_pct, height=0.55,
            color=cores, zorder=3)
    ax.axvline(0, color=vs.TEXTO_SECUNDARIO, linewidth=1.1, zorder=4)

    for i, linha in df.iterrows():
        v = linha.gap_salarial_pct
        texto = "sem diferença" if abs(v) < 0.5 else f"{v:+.1f}%"
        ax.text(
            v + (-1.2 if v < 0 else 1.2), i, texto,
            va="center", ha="right" if v < 0 else "left",
            fontsize=10.5, color=vs.TEXTO_SECUNDARIO,
        )

    ax.invert_yaxis()
    vs.grade_x(ax)
    limite = max(abs(df.gap_salarial_pct.min()), 8) * 1.5
    ax.set_xlim(-limite, limite * 0.5)
    ax.set_xticks([])
    vs.titular(
        ax,
        "O gap salarial não existe na base — ele se abre no topo",
        "Diferença do salário mediano feminino em relação ao masculino — "
        "as faixas da pesquisa são largas, então\n'sem diferença' significa "
        f"mesma faixa salarial, não necessariamente o mesmo salário — edição {ANO_RECENTE}-26",
    )
    vs.creditar(fig)
    salvar(fig, "06_gap_salarial_genero")


# ===========================================================================
# P4 — Tecnologias mais adotadas
# ===========================================================================
def grafico_tecnologias() -> None:
    """Small multiples: top tecnologias de cada categoria, na edição mais recente."""
    df = ler_gold("gold_tecnologias")

    # Linguagens saiu do questionário em 2025 — usamos a última edição em que a
    # pergunta existiu e dizemos isso no rótulo, em vez de mostrar um painel vazio.
    categorias = ["Linguagem", "Banco de dados", "Cloud", "Ferramenta de BI"]

    fig, axes = plt.subplots(2, 2, figsize=(13, 8.5))
    for ax, categoria in zip(axes.flat, categorias):
        sub = df[df.categoria == categoria]
        ano = sub.survey_year.max()
        sub = sub[sub.survey_year == ano].nlargest(7, "pct_adocao").sort_values(
            "pct_adocao"
        )

        cores = vs.rampa_sequencial(len(sub))[::-1]
        ax.barh(sub.tecnologia, sub.pct_adocao, height=0.66, color=cores, zorder=3)
        vs.rotular_barras_h(
            ax, sub.pct_adocao.tolist(),
            [f"{v:.0f}%" for v in sub.pct_adocao],
        )
        vs.grade_x(ax)
        ax.set_xlim(0, sub.pct_adocao.max() * 1.2)
        ax.set_xticks([])
        sufixo = "" if ano == ANO_RECENTE else f"  (última edição com a pergunta: {ano}-{str(ano + 1)[-2:]})"
        ax.set_title(f"{categoria}{sufixo}", fontsize=13.5, pad=10)
        ax.tick_params(axis="y", labelsize=11)

    fig.suptitle(
        "SQL e Python são o alicerce; AWS e Power BI dominam a stack",
        x=0.005, y=1.06, ha="left", fontsize=16, fontweight="bold",
        color=vs.TEXTO_PRIMARIO,
    )
    fig.text(
        0.005, 1.005,
        "Percentual de adoção entre os profissionais que responderam cada bloco do questionário",
        ha="left", fontsize=11, color=vs.TEXTO_SECUNDARIO,
    )
    fig.tight_layout()
    vs.creditar(fig)
    salvar(fig, "07_tecnologias")


# ===========================================================================
# P5 — Adoção de IA generativa
# ===========================================================================
def grafico_adocao_ia() -> None:
    """
    Duas séries no mesmo eixo — mas de bases diferentes, não da mesma pessoa.

    ``usa_ia_generativa`` e ``empresa_prioriza_ia`` vêm de blocos distintos do
    questionário: nas 3 edições, a interseção de respondentes é vazia (quem
    respondeu um não respondeu o outro — checado direto na Silver). O gráfico
    ainda vale a pena — mostra a evolução de dois indicadores relevantes —,
    mas o rótulo de cada série carrega o próprio ``n`` para que ninguém leia
    a distância entre as curvas como "a mesma pessoa, adoção vs. empresa".
    """
    df = ler_gold("gold_evolucao_anual").sort_values("survey_year")
    ado = ler_gold("gold_adocao_ia")
    n_pessoal = {
        int(ano): int(g.base_uso_pessoal.sum())
        for ano, g in ado.groupby("survey_year")
    }
    n_empresa = {
        int(ano): int(g.base_uso_empresa.sum())
        for ano, g in ado.groupby("survey_year")
    }

    fig, ax = plt.subplots(figsize=(9.8, 5.2))
    ultimo = df.iloc[-1]
    series = [
        ("pct_usa_ia_generativa", "Uso pessoal de IA generativa",
         vs.CATEGORICA[0], n_pessoal),
        ("pct_empresa_prioriza_ia", "Bloco organizacional: empresa prioriza IA",
         vs.CATEGORICA[1], n_empresa),
    ]
    for coluna, rotulo, cor, bases in series:
        ax.plot(df.survey_year, df[coluna], marker="o", color=cor,
                label=rotulo, zorder=3)
        # Direct label só no ponto final, com o n do bloco ao lado — é
        # exatamente o n que faltava para não ler as duas curvas como a
        # mesma amostra.
        ax.annotate(
            f"{ultimo[coluna]:.0f}% (n={bases[int(ultimo.survey_year)]})",
            (ultimo.survey_year, ultimo[coluna]),
            textcoords="offset points", xytext=(10, -4),
            fontsize=11, fontweight="bold", color=cor,
        )

    # Sombreado mantido — ainda ajuda a ver a distância entre as duas curvas
    # — mas o rótulo agora fala em "contraste entre blocos", não "lacuna",
    # pra não sugerir uma métrica única medida na mesma amostra.
    ax.fill_between(
        df.survey_year, df.pct_usa_ia_generativa, df.pct_empresa_prioriza_ia,
        color=vs.CATEGORICA[0], alpha=0.07, zorder=1,
    )
    meio = len(df) // 2
    ax.annotate(
        f"contraste de {df.iloc[-1].pct_usa_ia_generativa - df.iloc[-1].pct_empresa_prioriza_ia:.0f} p.p. entre blocos",
        (df.iloc[meio].survey_year,
         (df.iloc[meio].pct_usa_ia_generativa + df.iloc[meio].pct_empresa_prioriza_ia) / 2),
        ha="center", fontsize=10.5, color=vs.TEXTO_APAGADO, style="italic",
    )

    vs.grade_y(ax)
    ax.set_xticks(df.survey_year)
    ax.set_xticklabels([f"{a}-{str(a + 1)[-2:]}" for a in df.survey_year])
    ax.set_ylim(0, 108)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_yticklabels(["0", "25%", "50%", "75%", "100%"])
    ax.spines["bottom"].set_color(vs.GRADE)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.25), ncol=2)
    vs.titular(
        ax,
        "Dois blocos do questionário, sem respondentes em comum",
        "Uso pessoal de IA generativa e prioridade organizacional declarada "
        "vêm de recortes disjuntos do questionário em todas as edições — "
        "nunca a mesma pessoa respondendo às duas perguntas",
    )
    vs.creditar(fig, y=-0.14)
    salvar(fig, "08_adocao_ia")


def grafico_impacto_ia() -> None:
    """
    Estágio de maturidade da IA generativa dentro das empresas.

    Responde à metade do enunciado que a adoção sozinha não cobre: não
    "quantos usam", mas "que resultado a empresa está de fato colhendo".
    Só existe na edição mais recente — a pergunta é nova, e o gráfico diz
    isso explicitamente em vez de fingir uma série temporal que não existe.
    """
    df = ler_gold("gold_impacto_ia")
    df = df[df.survey_year == df.survey_year.max()]
    base = int(df.respondentes.sum())
    ano = int(df.survey_year.iloc[0])

    # Ordem de maturidade crescente — "não sabe opinar" fica à parte, no fim,
    # por não ser um estágio do funil.
    ORDEM = [
        "Não começou",
        "Em investigação/planejamento",
        "Piloto, sem resultado ainda",
        "Em produção, com resultado",
        "Não sabe opinar",
    ]
    df = df.set_index("resultado_ia_empresa").reindex(ORDEM).reset_index()
    df.columns = ["resultado_ia_empresa", "survey_year", "respondentes", "pct"]

    cores = {
        "Não começou": "#c9c8c3",
        "Em investigação/planejamento": "#e8a33d",
        "Piloto, sem resultado ainda": vs.CATEGORICA[1],
        "Em produção, com resultado": vs.DIVERGENTE_POSITIVO,
        "Não sabe opinar": "#e0dfd9",
    }

    fig, ax = plt.subplots(figsize=(10, 5))
    y = np.arange(len(df))
    ax.barh(y, df.pct, height=0.6,
            color=[cores[c] for c in df.resultado_ia_empresa], zorder=3)
    vs.rotular_barras_h(ax, df.pct.tolist(), [f"{v:.0f}%" for v in df.pct])

    ax.set_yticks(y)
    ax.set_yticklabels(df.resultado_ia_empresa)
    ax.invert_yaxis()
    vs.grade_x(ax)
    ax.set_xlim(0, df.pct.max() * 1.25)
    ax.set_xticks([])

    # A régua "produção vs. ainda não" é o argumento do slide — deixa
    # explícito no rótulo em vez de forçar o leitor a somar de cabeça.
    em_producao = df.loc[
        df.resultado_ia_empresa == "Em produção, com resultado", "pct"
    ].iloc[0]
    ax.axvline(em_producao, color=vs.TEXTO_APAGADO, linewidth=0.9,
               linestyle=":", zorder=2)

    vs.titular(
        ax,
        f"Só {em_producao:.0f}% do bloco organizacional relata resultado "
        "real com IA generativa",
        f"Estágio dos projetos de IA generativa/LLM segundo o respondente — "
        f"edição {ano}-{str(ano + 1)[-2:]} (n={base}, pergunta exclusiva desta edição)",
    )
    vs.creditar(fig)
    salvar(fig, "12_impacto_ia")


# ===========================================================================
# P6 — Regiões, senioridades e modelos de trabalho
# ===========================================================================
def grafico_modelo_trabalho() -> None:
    """Barras empilhadas 100%: evolução dos modelos de trabalho."""
    df = ler_gold("gold_evolucao_anual").sort_values("survey_year")

    fig, ax = plt.subplots(figsize=(9.8, 4.6))
    colunas = [
        ("pct_presencial", "Presencial"),
        ("pct_hibrido", "Híbrido"),
        ("pct_remoto", "Remoto"),
    ]
    esquerda = np.zeros(len(df))
    GAP = 0.35

    for coluna, rotulo in colunas:
        valores = df[coluna].to_numpy()
        ax.barh(
            df.survey_year.astype(str), valores, left=esquerda, height=0.6,
            color=vs.COR_MODELO_TRABALHO[rotulo], label=rotulo, zorder=3,
        )
        for j, (v, e) in enumerate(zip(valores, esquerda)):
            if v >= 7:
                ax.text(e + v / 2, j, f"{v:.0f}%", ha="center", va="center",
                        color="white", fontsize=10, fontweight="bold")
        esquerda = esquerda + valores + GAP

    # set_yticks antes de set_yticklabels: sem fixar as posições, o matplotlib
    # usa um locator automático e os rótulos podem cair na linha errada.
    ax.set_yticks(range(len(df)))
    ax.set_yticklabels([f"{a}-{str(a + 1)[-2:]}" for a in df.survey_year])
    ax.set_xticks([])
    ax.invert_yaxis()
    ax.grid(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.28), ncol=3,
              handlelength=1.2, handleheight=1.2)
    vs.titular(
        ax,
        "O retorno ao escritório é real, mas lento",
        "Distribuição dos modelos de trabalho declarados, por edição",
    )
    vs.creditar(fig, y=-0.14)
    salvar(fig, "09_modelo_trabalho")


def grafico_salario_regiao() -> None:
    """
    Salário médio Nordeste vs. Sudeste, controlado por senioridade.

    A comparação bruta (todo mundo do Nordeste vs. todo mundo do Sudeste)
    confunde duas coisas: diferença de mercado regional e diferença de
    COMPOSIÇÃO — o Sudeste concentra bem mais Especialista/Staff+ (15,8% dos
    respondentes, contra 6,4% no Nordeste), que é o nível mais bem pago.
    Misturado, isso infla a distância bruta entre as regiões sem dizer nada
    sobre quanto custa contratar um Sênior especificamente em cada lugar.

    Comparar dentro do mesmo nível de senioridade é o que isola o efeito
    regional do efeito de composição — e o resultado muda a conclusão: o gap
    é real e grande na base da carreira, mas desaparece no topo.

    Média (não mediana) pelo mesmo motivo do corte regional simples: as
    faixas salariais são largas demais para a mediana distinguir regiões
    dentro do mesmo nível.
    """
    df = ler_gold("gold_remuneracao_regional")
    df = df[
        (df.survey_year == ANO_RECENTE)
        & df.regiao.isin(["Nordeste", "Sudeste"])
    ]
    ordem = [n for n in vs.ORDEM_SENIORIDADE if n in set(df.senioridade)]
    df = df.set_index("senioridade").loc[ordem].reset_index()

    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    largura = 0.36
    x = np.arange(len(ordem))

    for i, regiao in enumerate(["Nordeste", "Sudeste"]):
        sub = df[df.regiao == regiao].set_index("senioridade").loc[ordem].reset_index()
        cor = vs.RECUADO if regiao == "Nordeste" else vs.DESTAQUE
        deslocamento = (i - 0.5) * largura
        ax.bar(
            x + deslocamento, sub.salario_medio, width=largura,
            color=cor, label=regiao, zorder=3,
        )
        for xi, linha in zip(x + deslocamento, sub.itertuples()):
            rotulo = reais(linha.salario_medio, curto=False)
            if not linha.amostra_suficiente:
                rotulo += "*"
            ax.text(xi, linha.salario_medio * 1.02, rotulo, ha="center",
                    va="bottom", fontsize=9.5, color=vs.TEXTO_SECUNDARIO)

    # A régua embaixo de cada par mostra a diferença percentual — é o número
    # que sustenta a conclusão do título, não a altura das barras sozinha.
    for xi, nivel in zip(x, ordem):
        nord = df[(df.regiao == "Nordeste") & (df.senioridade == nivel)]
        sud = df[(df.regiao == "Sudeste") & (df.senioridade == nivel)]
        if nord.empty or sud.empty:
            continue
        diff = (nord.salario_medio.iloc[0] / sud.salario_medio.iloc[0] - 1) * 100
        # Uma diferença de magnitude parecida com a do Júnior, mas apoiada em
        # 17 respondentes (Especialista/Staff+ no Nordeste), não é o mesmo
        # achado que -14% apoiado em 69. O percentual entra em cinza e com
        # asterisco quando qualquer um dos dois lados fica abaixo do corte —
        # ele existe, mas não sustenta uma alegação de negócio sozinho.
        confiavel = bool(nord.amostra_suficiente.iloc[0] and sud.amostra_suficiente.iloc[0])
        if confiavel:
            cor_diff = vs.DIVERGENTE_NEGATIVO if diff < -3 else vs.TEXTO_APAGADO
            texto = f"{diff:+.0f}%"
        else:
            cor_diff = vs.TEXTO_APAGADO
            texto = f"{diff:+.0f}%*"
        ax.text(xi, -df.salario_medio.max() * 0.11, texto,
                ha="center", va="top", fontsize=10, color=cor_diff,
                fontweight="bold" if confiavel and diff < -3 else "normal")

    ax.set_xticks(x)
    ax.set_xticklabels(ordem)
    vs.grade_y(ax)
    ax.set_ylim(-df.salario_medio.max() * 0.16, df.salario_medio.max() * 1.22)
    ax.set_yticks([])
    ax.axhline(0, color=vs.GRADE, linewidth=0.9)
    ax.legend(loc="upper left", ncol=2)

    vs.titular(
        ax,
        "O gap regional é real na base da carreira — e some no topo",
        f"Salário médio mensal, Nordeste vs. Sudeste, por senioridade — "
        f"edição {ANO_RECENTE}-26 (percentual = Nordeste em relação ao Sudeste)",
    )
    vs.creditar(fig)
    salvar(fig, "10_salario_regiao")


def grafico_evolucao_salario_senioridade() -> None:
    """Como cada nível de carreira evoluiu ao longo das três edições."""
    df = ler_gold("gold_remuneracao")
    df = df[(df.dimensao == "senioridade") & df.amostra_suficiente]

    fig, ax = plt.subplots(figsize=(9.8, 5.2))
    niveis = [n for n in vs.ORDEM_SENIORIDADE if n in set(df.categoria)]

    for nivel in niveis:
        sub = df[df.categoria == nivel].sort_values("survey_year")
        # Especialista/Staff+ só existe em 2025 — um ponto isolado, não uma linha
        estilo = {"marker": "o"} if len(sub) > 1 else {"marker": "o", "linestyle": "none"}
        ax.plot(sub.survey_year, sub.salario_mediano,
                color=vs.COR_SENIORIDADE[nivel], label=nivel, zorder=3, **estilo)
        ultimo = sub.iloc[-1]
        ax.annotate(
            reais(ultimo.salario_mediano),
            (ultimo.survey_year, ultimo.salario_mediano),
            textcoords="offset points", xytext=(10, -4),
            fontsize=10.5, color=vs.COR_SENIORIDADE[nivel], fontweight="bold",
        )

    vs.grade_y(ax)
    ax.set_xticks(sorted(df.survey_year.unique()))
    ax.set_xticklabels(
        [f"{a}-{str(a + 1)[-2:]}" for a in sorted(df.survey_year.unique())]
    )
    ax.set_xlim(2022.8, 2025.5)
    ax.set_ylim(0, df.salario_mediano.max() * 1.25)
    ax.set_yticks([])
    ax.spines["bottom"].set_color(vs.GRADE)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.25), ncol=4)
    vs.titular(
        ax,
        "Só o topo da carreira teve reajuste nominal",
        "Salário mediano mensal por senioridade, ao longo das três edições "
        "(valores nominais, sem correção pela inflação)",
    )
    vs.creditar(fig, y=-0.14)
    salvar(fig, "11_evolucao_salario_senioridade")


# ===========================================================================
def main() -> None:
    vs.aplicar_estilo()
    print("Gerando gráficos a partir da camada Gold...\n")

    for funcao in (
        grafico_composicao_mercado,
        grafico_piramide_senioridade,
        grafico_premio_senioridade,
        grafico_salario_por_cargo,
        grafico_representatividade_genero,
        grafico_gap_salarial_genero,
        grafico_tecnologias,
        grafico_adocao_ia,
        grafico_impacto_ia,
        grafico_modelo_trabalho,
        grafico_salario_regiao,
        grafico_evolucao_salario_senioridade,
    ):
        funcao()

    print(f"\nConcluído — {SAIDA.relative_to(RAIZ)}/")


if __name__ == "__main__":
    main()
