"""
Sistema visual dos gráficos do Tech Challenge.

Centralizar estilo em um módulo evita o problema clássico de deck de consultoria:
doze gráficos com doze paletas diferentes, em que a mesma categoria muda de cor
entre slides e o leitor perde a referência.

Regras aplicadas (validadas com o validador de paleta do projeto):

  * **cor segue a entidade, nunca o ranking** — "Feminino" é sempre a mesma cor,
    em todos os gráficos, independente da posição na ordenação;
  * **magnitude usa uma única matiz** (azul, claro→escuro); identidade usa a
    paleta categórica em ordem fixa; polaridade (gap salarial) usa a divergente
    azul↔vermelho com cinza neutro no zero;
  * **rótulos diretos em todas as barras** — três das cores ficam abaixo de 3:1
    de contraste com o fundo, e o rótulo visível é o que cumpre a regra de
    alívio;
  * grade e eixos são fios de cabelo recessivos, nunca tracejados;
  * nunca dois eixos Y no mesmo gráfico.
"""
from __future__ import annotations

import matplotlib as mpl

# A ordem das categorias vem de mappings.py, fonte única de verdade do schema
# canônico. Duplicá-la aqui já custou caro: uma cópia desatualizada desta lista
# descartou silenciosamente os 349 "Especialista/Staff+" de 2025 do gráfico da
# pirâmide, e os percentuais renormalizaram para 100% como se nada faltasse.
from mappings import ORDEM_MODELO, ORDEM_SENIORIDADE

# ---------------------------------------------------------------------------
# Superfícies e tinta
# ---------------------------------------------------------------------------
SUPERFICIE = "#fcfcfb"
TEXTO_PRIMARIO = "#0b0b0b"
TEXTO_SECUNDARIO = "#52514e"
TEXTO_APAGADO = "#82817c"
GRADE = "#e6e5e1"

# ---------------------------------------------------------------------------
# Paleta categórica — ORDEM FIXA. Slots são atribuídos por entidade, jamais
# ciclados nem reordenados por valor.
# ---------------------------------------------------------------------------
CATEGORICA = [
    "#2a78d6",  # 1 azul
    "#eb6834",  # 2 laranja
    "#1baf7a",  # 3 água
    "#eda100",  # 4 amarelo
    "#e87ba4",  # 5 magenta
    "#008300",  # 6 verde
    "#4a3aa7",  # 7 violeta
    "#e34948",  # 8 vermelho
]

# Sequencial (magnitude): uma única matiz, claro -> escuro
SEQUENCIAL = [
    "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec",
    "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab",
    "#184f95", "#104281", "#0d366b",
]

# Divergente (polaridade): azul ↔ vermelho, cinza neutro no meio
DIVERGENTE_NEGATIVO = "#e34948"
DIVERGENTE_POSITIVO = "#2a78d6"
DIVERGENTE_NEUTRO = "#f0efec"

# Ênfase: um destaque, o resto recua
DESTAQUE = "#2a78d6"
RECUADO = "#c9c8c3"

# ---------------------------------------------------------------------------
# Cores fixas por entidade — a garantia de consistência entre slides
# ---------------------------------------------------------------------------
COR_GENERO = {
    "Masculino": CATEGORICA[0],
    "Feminino": CATEGORICA[1],
    "Outro / Não informado": CATEGORICA[2],
}

COR_SENIORIDADE = {
    nivel: CATEGORICA[i] for i, nivel in enumerate(ORDEM_SENIORIDADE)
}

COR_MODELO_TRABALHO = {
    modelo: CATEGORICA[i] for i, modelo in enumerate(ORDEM_MODELO)
}


def aplicar_estilo() -> None:
    """Configura o matplotlib com o sistema visual do projeto."""
    mpl.rcParams.update(
        {
            "figure.facecolor": SUPERFICIE,
            "axes.facecolor": SUPERFICIE,
            "savefig.facecolor": SUPERFICIE,
            "savefig.dpi": 200,
            "savefig.bbox": "tight",
            "figure.dpi": 110,
            "font.family": "sans-serif",
            "font.sans-serif": [
                "Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans",
            ],
            "font.size": 11,
            "text.color": TEXTO_PRIMARIO,
            "axes.labelcolor": TEXTO_SECUNDARIO,
            "axes.edgecolor": GRADE,
            "axes.linewidth": 0.8,
            "axes.titlesize": 15,
            "axes.titleweight": "bold",
            "axes.titlecolor": TEXTO_PRIMARIO,
            "axes.titlelocation": "left",
            "axes.titlepad": 16,
            "axes.labelsize": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "xtick.color": TEXTO_SECUNDARIO,
            "ytick.color": TEXTO_SECUNDARIO,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "xtick.major.size": 0,
            "ytick.major.size": 0,
            # Grade sólida e recessiva — tracejado vira ruído e sugere
            # "projeção" onde só existe referência de leitura.
            "grid.color": GRADE,
            "grid.linestyle": "-",
            "grid.linewidth": 0.8,
            "legend.frameon": False,
            "legend.fontsize": 10,
            "lines.linewidth": 2.0,
            "lines.markersize": 8,
        }
    )


def titular(ax, titulo: str, subtitulo: str | None = None) -> None:
    """
    Aplica título e subtítulo com a hierarquia do deck.

    O subtítulo é onde vive a conclusão ("Sênior ganha 2,4x o Júnior"); o
    título nomeia o recorte. Gráfico executivo que só nomeia o eixo obriga o
    leitor a descobrir sozinho o que deveria ver.
    """
    # Cada linha extra do subtítulo empurra o título pra cima; um pad fixo
    # calibrado para 1 linha faz o título invadir a 2ª linha de subtítulos
    # mais longos (foi o que causou a sobreposição no gráfico de gap salarial
    # de gênero).
    linhas_subtitulo = subtitulo.count("\n") + 1 if subtitulo else 0
    pad = 28 + (linhas_subtitulo - 1) * 14 if subtitulo else 16
    ax.set_title(titulo, pad=pad)
    if subtitulo:
        ax.text(
            0.0, 1.03, subtitulo,
            transform=ax.transAxes, ha="left", va="bottom",
            fontsize=11, color=TEXTO_SECUNDARIO,
        )


def grade_x(ax) -> None:
    """Grade vertical apenas — para barras horizontais."""
    ax.grid(axis="x", zorder=0)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_visible(False)


def grade_y(ax) -> None:
    """Grade horizontal apenas — para barras verticais e linhas."""
    ax.grid(axis="y", zorder=0)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)


def rotular_barras_h(ax, valores, rotulos, *, offset=None, cor=None) -> None:
    """
    Rótulo direto ao final de cada barra horizontal.

    Obrigatório neste projeto: parte da paleta fica abaixo de 3:1 de contraste
    com o fundo, e o rótulo visível é o que torna o gráfico legível para quem
    não distingue as matizes.
    """
    if offset is None:
        largura = max(abs(v) for v in valores) if len(valores) else 1
        offset = largura * 0.015

    for y, (valor, rotulo) in enumerate(zip(valores, rotulos)):
        deslocamento = offset if valor >= 0 else -offset
        ax.text(
            valor + deslocamento, y, rotulo,
            va="center",
            ha="left" if valor >= 0 else "right",
            fontsize=10, color=cor or TEXTO_SECUNDARIO,
        )


def rampa_sequencial(n: int) -> list[str]:
    """
    n cores da rampa sequencial, do mais escuro (maior) ao mais claro.

    Nunca desce abaixo do passo 250: mais claro que isso o mark some no fundo.
    """
    if n <= 1:
        return [SEQUENCIAL[7]]
    disponiveis = SEQUENCIAL[3:]  # a partir do passo 250
    passo = (len(disponiveis) - 1) / (n - 1)
    indices = [round(i * passo) for i in range(n)]
    return [disponiveis[i] for i in reversed(indices)]


def creditar(fig, fonte: str = "Fonte: State of Data Brasil — Data Hackers + Bain",
             y: float = -0.02) -> None:
    """
    Assina o gráfico com a fonte dos dados.

    ``y`` desce o crédito quando o gráfico tem legenda na base — senão os dois
    disputam a mesma linha e se sobrepõem depois do recorte do bbox.
    """
    fig.text(
        0.0, y, fonte,
        ha="left", va="top", fontsize=9, color=TEXTO_APAGADO,
    )
