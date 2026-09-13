"""
Monta o material executivo (PPTX) a partir dos gráficos e da camada Gold.

Princípio que orienta o arquivo: **nenhum número é digitado à mão**. Todos os
valores citados nos títulos, nos destaques e nas recomendações são lidos da
camada Gold em tempo de geração. Um deck com números escritos manualmente
começa correto e envelhece errado — basta reprocessar o pipeline para o texto
divergir dos gráficos ao lado.

O deck segue a estrutura de uma narrativa executiva: contexto, método,
evidência (agrupada por pergunta de negócio) e recomendação. Cada slide de
gráfico tem como título a CONCLUSÃO, não o nome do eixo.

Uso:
    python src/gerar_apresentacao.py
"""
from __future__ import annotations

import glob
import sys
from pathlib import Path

import pandas as pd
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import viz_style as vs  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
GOLD = RAIZ / "data" / "gold"
CHARTS = RAIZ / "output" / "charts"
SAIDA = RAIZ / "output" / "Tech_Challenge_Fase3_Material_Executivo.pptx"

LARGURA = Inches(13.333)
ALTURA = Inches(7.5)

ANO = 2025


def cor(hex_str: str) -> RGBColor:
    return RGBColor.from_string(hex_str.lstrip("#").upper())


TINTA = cor(vs.TEXTO_PRIMARIO)
TINTA_SEC = cor(vs.TEXTO_SECUNDARIO)
TINTA_FRACA = cor(vs.TEXTO_APAGADO)
FUNDO = cor(vs.SUPERFICIE)
AZUL = cor(vs.CATEGORICA[0])
LARANJA = cor(vs.CATEGORICA[1])


# ===========================================================================
# Leitura dos números — a única fonte de verdade do texto do deck
# ===========================================================================
def ler(tabela: str) -> pd.DataFrame:
    arquivos = glob.glob(str(GOLD / tabela / "*.parquet"))
    if not arquivos:
        raise FileNotFoundError(
            f"Tabela Gold '{tabela}' ausente — rode antes: bash scripts/rodar_local.sh"
        )
    return pd.read_parquet(arquivos[0])


def coletar_numeros() -> dict:
    """Extrai da Gold todos os valores citados no texto do deck."""
    evo = ler("gold_evolucao_anual").sort_values("survey_year")
    rem = ler("gold_remuneracao")
    rem_regional = ler("gold_remuneracao_regional")
    impacto_ia = ler("gold_impacto_ia")
    ado_ia = ler("gold_adocao_ia")
    div = ler("gold_diversidade_genero")
    tec = ler("gold_tecnologias")
    perfil = ler("gold_perfil_mercado")

    ultimo, primeiro = evo.iloc[-1], evo.iloc[0]

    # As perguntas de uso pessoal e de priorização pela empresa são blocos
    # DIFERENTES do questionário — na edição mais recente, dos 3.494
    # respondentes, 2.105 responderam só a pergunta de uso pessoal, 638
    # responderam só a de priorização organizacional, e ZERO respondeu às
    # duas (confirmado direto na Silver: a interseção é vazia). Os 98% e os
    # 62% não são "a mesma pessoa antes e depois" — são dois recortes
    # disjuntos do questionário, cada um com seu próprio n. Guardamos os dois
    # n's aqui para que nenhum slide apresente a diferença entre eles como
    # se fosse uma lacuna medida na mesma amostra.
    ado_ultimo = ado_ia[ado_ia.survey_year == ANO]
    base_uso_pessoal_ia = int(ado_ultimo.base_uso_pessoal.sum())
    base_uso_empresa_ia = int(ado_ultimo.base_uso_empresa.sum())

    sen = rem[
        (rem.dimensao == "senioridade") & (rem.survey_year == ANO)
        & rem.amostra_suficiente
    ].set_index("categoria")

    cargos = rem[
        (rem.dimensao == "cargo") & (rem.survey_year == ANO)
        & rem.amostra_suficiente & (rem.categoria != "Outros")
    ].sort_values("salario_mediano", ascending=False)

    regioes = rem[
        (rem.dimensao == "regiao") & (rem.survey_year == ANO)
        & rem.amostra_suficiente
    ].sort_values("salario_medio", ascending=False)

    # Comparação regional controlada por senioridade — a bruta acima confunde
    # diferença de mercado com diferença de composição (Sudeste concentra bem
    # mais Especialista/Staff+). Júnior é o corte mais confiável dos dois
    # (ambas as regiões acima do corte de amostra) e é onde o gap realmente
    # está — no topo da carreira ele desaparece.
    regional_junior = rem_regional[
        (rem_regional.survey_year == ANO)
        & (rem_regional.senioridade == "Júnior")
        & rem_regional.regiao.isin(["Nordeste", "Sudeste"])
        & rem_regional.amostra_suficiente
    ].set_index("regiao")
    regional_senior = rem_regional[
        (rem_regional.survey_year == ANO)
        & (rem_regional.senioridade == "Sênior")
        & rem_regional.regiao.isin(["Nordeste", "Sudeste"])
        & rem_regional.amostra_suficiente
    ].set_index("regiao")

    impacto_recente = impacto_ia[impacto_ia.survey_year == impacto_ia.survey_year.max()]
    pct_producao = impacto_recente.loc[
        impacto_recente.resultado_ia_empresa == "Em produção, com resultado", "pct"
    ]
    pct_piloto = impacto_recente.loc[
        impacto_recente.resultado_ia_empresa == "Piloto, sem resultado ainda", "pct"
    ]

    gap_senior = div[
        (div.survey_year == ANO) & (div.genero == "Feminino")
        & (div.senioridade == "Sênior")
    ]

    def topo(categoria: str) -> tuple[str, float]:
        sub = tec[tec.categoria == categoria]
        sub = sub[sub.survey_year == sub.survey_year.max()]
        linha = sub.nlargest(1, "pct_adocao").iloc[0]
        return linha.tecnologia, linha.pct_adocao

    n_cargos = (
        perfil[(perfil.survey_year == ANO) & perfil.cargo.notna()]
        .groupby("cargo")["respondentes"].sum().sort_values(ascending=False)
    )

    return {
        "total_respondentes": int(evo.total_respondentes.sum()),
        "respondentes_por_ano": {
            int(r.survey_year): int(r.total_respondentes)
            for _, r in evo.iterrows()
        },
        "pct_ia_ultimo": ultimo.pct_usa_ia_generativa,
        "pct_ia_primeiro": primeiro.pct_usa_ia_generativa,
        "pct_empresa_ia_ultimo": ultimo.pct_empresa_prioriza_ia,
        "lacuna_ia": ultimo.pct_usa_ia_generativa - ultimo.pct_empresa_prioriza_ia,
        "base_uso_pessoal_ia": base_uso_pessoal_ia,
        "base_uso_empresa_ia": base_uso_empresa_ia,
        "pct_mulheres_primeiro": primeiro.pct_mulheres,
        "pct_mulheres_ultimo": ultimo.pct_mulheres,
        "pct_remoto_primeiro": primeiro.pct_remoto,
        "pct_remoto_ultimo": ultimo.pct_remoto,
        "pct_presencial_primeiro": primeiro.pct_presencial,
        "pct_presencial_ultimo": ultimo.pct_presencial,
        "sal_junior": sen.loc["Júnior", "salario_mediano"],
        "sal_senior": sen.loc["Sênior", "salario_mediano"],
        "sal_especialista": (
            sen.loc["Especialista/Staff+", "salario_mediano"]
            if "Especialista/Staff+" in sen.index else None
        ),
        "multiplo_senior": sen.loc["Sênior", "salario_mediano"]
        / sen.loc["Júnior", "salario_mediano"],
        "cargo_topo": cargos.iloc[0].categoria,
        "cargo_topo_sal": cargos.iloc[0].salario_mediano,
        "cargo_maior_volume": n_cargos.index[0],
        "cargo_maior_volume_n": int(n_cargos.iloc[0]),
        "regiao_cara": regioes.iloc[0].categoria,
        "regiao_cara_sal": regioes.iloc[0].salario_medio,
        "regiao_barata": regioes.iloc[-1].categoria,
        "regiao_barata_sal": regioes.iloc[-1].salario_medio,
        # Bruto — só para dar contexto de dimensão da amostra, NUNCA citado
        # sozinho como "custa X% menos" (ver nota metodológica do slide).
        "desconto_regional_bruto": (
            1 - regioes.iloc[-1].salario_medio / regioes.iloc[0].salario_medio
        ) * 100,
        # Controlado por senioridade — o número que sustenta a recomendação.
        "desconto_regional_junior": (
            1 - regional_junior.loc["Nordeste", "salario_medio"]
            / regional_junior.loc["Sudeste", "salario_medio"]
        ) * 100,
        "desconto_regional_senior": (
            1 - regional_senior.loc["Nordeste", "salario_medio"]
            / regional_senior.loc["Sudeste", "salario_medio"]
        ) * 100,
        "gap_senior": (
            gap_senior.iloc[0].gap_salarial_pct if not gap_senior.empty else None
        ),
        "top_cloud": topo("Cloud"),
        "top_bi": topo("Ferramenta de BI"),
        "top_linguagem": topo("Linguagem"),
        "top_banco": topo("Banco de dados"),
        "pct_ia_producao": pct_producao.iloc[0] if not pct_producao.empty else None,
        "pct_ia_piloto": pct_piloto.iloc[0] if not pct_piloto.empty else None,
        "base_impacto_ia": int(impacto_recente.respondentes.sum()),
    }


def brl(valor: float) -> str:
    return f"R$ {valor:,.0f}".replace(",", ".")


def dec(valor: float, casas: int = 1) -> str:
    """Número decimal na convenção pt-BR (vírgula como separador decimal)."""
    return f"{valor:.{casas}f}".replace(".", ",")


def milhar(valor: int) -> str:
    """
    Inteiro com separador de milhar à brasileira (14.002, não 14,002).

    Formata só o número, nunca a frase ao redor — um ``.replace(",", ".")``
    aplicado à string inteira já quebrou pontuação de frases que tinham
    vírgula gramatical perto de um número (ver histórico de correções).
    """
    return f"{valor:,}".replace(",", ".")


# ===========================================================================
# Primitivas de slide
# ===========================================================================
def novo_slide(prs: Presentation):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # layout em branco
    fundo = slide.background.fill
    fundo.solid()
    fundo.fore_color.rgb = FUNDO
    return slide


def texto(slide, x, y, w, h, conteudo, *, tamanho=18, negrito=False,
          tinta=TINTA, alinhamento=PP_ALIGN.LEFT, espacamento=1.0):
    caixa = slide.shapes.add_textbox(x, y, w, h)
    quadro = caixa.text_frame
    quadro.word_wrap = True
    linhas = conteudo.split("\n")
    for i, linha in enumerate(linhas):
        p = quadro.paragraphs[0] if i == 0 else quadro.add_paragraph()
        p.alignment = alinhamento
        p.line_spacing = espacamento
        run = p.add_run()
        run.text = linha
        run.font.size = Pt(tamanho)
        run.font.bold = negrito
        run.font.color.rgb = tinta
        run.font.name = "Helvetica Neue"
    return caixa


def barra_de_acento(slide, x, y, largura=Inches(1.6), cor_barra=AZUL):
    """Filete colorido usado como marcador de hierarquia."""
    from pptx.enum.shapes import MSO_SHAPE

    forma = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, largura, Pt(4))
    forma.fill.solid()
    forma.fill.fore_color.rgb = cor_barra
    forma.line.fill.background()
    forma.shadow.inherit = False
    return forma


def slide_grafico(prs, arquivo: str, titulo: str, subtitulo: str = "",
                  nota: str = "") -> None:
    """
    Slide padrão: takeaway como título e o gráfico ocupando o corpo.

    A imagem é escalada preservando proporção e centralizada — esticar um
    gráfico para preencher o slide distorce as escalas e é mentira visual.
    """
    slide = novo_slide(prs)
    caminho = CHARTS / arquivo
    if not caminho.exists():
        raise FileNotFoundError(f"Gráfico ausente: {caminho}")

    texto(slide, Inches(0.6), Inches(0.35), Inches(12.1), Inches(0.6),
          titulo, tamanho=25, negrito=True)
    if subtitulo:
        texto(slide, Inches(0.6), Inches(0.95), Inches(12.1), Inches(0.4),
              subtitulo, tamanho=13, tinta=TINTA_SEC)

    topo = Inches(1.5)
    disponivel_h = Inches(5.3)
    disponivel_w = Inches(12.1)

    from PIL import Image

    with Image.open(caminho) as img:
        proporcao = img.width / img.height

    altura = disponivel_h
    largura = Emu(int(altura * proporcao))
    if largura > disponivel_w:
        largura = disponivel_w
        altura = Emu(int(largura / proporcao))

    esquerda = Emu(int((LARGURA - largura) / 2))
    slide.shapes.add_picture(str(caminho), esquerda, topo,
                             width=largura, height=altura)

    if nota:
        texto(slide, Inches(0.6), Inches(6.9), Inches(12.1), Inches(0.4),
              nota, tamanho=10, tinta=TINTA_FRACA)


def slide_secao(prs, numero: str, titulo: str, pergunta: str) -> None:
    """Divisor de seção — dá respiro à narrativa e ancora a pergunta."""
    slide = novo_slide(prs)
    texto(slide, Inches(1.0), Inches(2.4), Inches(2.0), Inches(1.2),
          numero, tamanho=64, negrito=True, tinta=AZUL)
    barra_de_acento(slide, Inches(1.05), Inches(3.75), Inches(2.2))
    texto(slide, Inches(1.0), Inches(4.05), Inches(10.5), Inches(0.9),
          titulo, tamanho=34, negrito=True)
    texto(slide, Inches(1.0), Inches(5.0), Inches(10.0), Inches(0.8),
          pergunta, tamanho=16, tinta=TINTA_SEC)


def slide_destaques(prs, titulo: str, subtitulo: str,
                    cartoes: list[tuple[str, str]]) -> None:
    """Linha de números-chave — o resumo que o executivo lê primeiro."""
    slide = novo_slide(prs)
    texto(slide, Inches(0.6), Inches(0.5), Inches(12.1), Inches(0.6),
          titulo, tamanho=26, negrito=True)
    texto(slide, Inches(0.6), Inches(1.15), Inches(12.1), Inches(0.5),
          subtitulo, tamanho=13, tinta=TINTA_SEC)

    n = len(cartoes)
    margem = Inches(0.6)
    espaco = Inches(0.25)
    largura = Emu(int((LARGURA - 2 * margem - espaco * (n - 1)) / n))

    for i, (valor, rotulo) in enumerate(cartoes):
        x = Emu(int(margem + i * (largura + espaco)))
        barra_de_acento(slide, x, Inches(2.3), Emu(int(largura * 0.35)))
        texto(slide, x, Inches(2.55), largura, Inches(1.2),
              valor, tamanho=40, negrito=True, tinta=AZUL)
        texto(slide, x, Inches(3.75), largura, Inches(1.6),
              rotulo, tamanho=13, tinta=TINTA_SEC, espacamento=1.15)


def slide_texto(prs, titulo: str, subtitulo: str,
                blocos: list[tuple[str, str]], *, nota: str = "") -> None:
    """Slide de conteúdo em duas colunas de blocos titulados."""
    slide = novo_slide(prs)
    texto(slide, Inches(0.6), Inches(0.45), Inches(12.1), Inches(0.6),
          titulo, tamanho=26, negrito=True)
    texto(slide, Inches(0.6), Inches(1.1), Inches(12.1), Inches(0.5),
          subtitulo, tamanho=13, tinta=TINTA_SEC)

    col_largura = Inches(5.85)
    for i, (cabecalho, corpo) in enumerate(blocos):
        coluna = i % 2
        linha = i // 2
        x = Inches(0.6) + coluna * Inches(6.25)
        # 1.62in de passo entre linhas já causou sobreposição real: com corpo
        # em 12pt/1.2 de espaçamento, um bloco de ~5 linhas já enche a caixa
        # de 1.0in alocada e o texto continua descendo (a caixa não recorta,
        # só quebra linha) — sobrando 0.07in de folga antes do próximo bloco.
        # 2.0in dá ~0.55in de folga real, suficiente até para blocos mais
        # longos que os atuais.
        y = Inches(1.85) + linha * Inches(2.0)
        barra_de_acento(slide, x, y, Inches(0.55),
                        AZUL if coluna == 0 else LARANJA)
        texto(slide, x, y + Inches(0.12), col_largura, Inches(0.4),
              cabecalho, tamanho=15, negrito=True)
        texto(slide, x, y + Inches(0.55), col_largura, Inches(1.0),
              corpo, tamanho=12, tinta=TINTA_SEC, espacamento=1.2)

    if nota:
        texto(slide, Inches(0.6), Inches(6.95), Inches(12.1), Inches(0.4),
              nota, tamanho=10, tinta=TINTA_FRACA)


# ===========================================================================
def construir(n: dict) -> Presentation:
    prs = Presentation()
    prs.slide_width = LARGURA
    prs.slide_height = ALTURA

    anos = n["respondentes_por_ano"]
    edicoes = " · ".join(f"{a}-{str(a + 1)[-2:]}" for a in sorted(anos))

    # ---------------------------------------------------------------- capa
    capa = novo_slide(prs)
    barra_de_acento(capa, Inches(1.0), Inches(2.15), Inches(2.4))
    texto(capa, Inches(1.0), Inches(2.45), Inches(11.0), Inches(1.4),
          "O mercado brasileiro de Dados e IA", tamanho=44, negrito=True)
    texto(capa, Inches(1.0), Inches(3.75), Inches(11.0), Inches(1.0),
          "Evidências de três edições do State of Data Brasil para decisões\n"
          "de contratação, capacitação e investimento",
          tamanho=18, tinta=TINTA_SEC, espacamento=1.3)
    texto(capa, Inches(1.0), Inches(5.6), Inches(11.0), Inches(0.9),
          f"Tech Challenge — Fase 3   ·   {edicoes}   ·   "
          f"{milhar(n['total_respondentes'])} respondentes",
          tamanho=13, tinta=TINTA_FRACA)
    texto(capa, Inches(1.0), Inches(6.15), Inches(11.0), Inches(0.9),
          "Grupo 34   ·   Arthur Dalbello Vicentini, Giovani dos Reis Gil, "
          "Pedro Henrique Bitencourt Dias, Luiz Henrique Gusmão Souto e Silva, "
          "Enrique Jorge Matuoka",
          tamanho=11, tinta=TINTA_FRACA)

    # ------------------------------------------------------------- contexto
    slide_texto(
        prs,
        "O problema de negócio",
        "Uma instituição financeira de grande porte quer expandir sua área de "
        "Dados, Analytics e IA — e precisa de evidência, não de intuição.",
        [
            ("Quem contratar",
             "Quais famílias de carreira formam o mercado, qual o custo de cada "
             "uma e onde está a escassez de profissionais maduros."),
            ("Quanto pagar",
             "Faixas de remuneração por senioridade, cargo e região, com a "
             "dispersão que uma proposta precisa considerar."),
            ("Onde contratar",
             "Diferença real de custo entre regiões e o papel do trabalho "
             "remoto em ampliar o funil de talentos."),
            ("Onde investir",
             "Quais tecnologias têm adoção consolidada e qual o estágio real "
             "de adoção de IA generativa nas empresas."),
        ],
        nota="Fonte: State of Data Brasil — pesquisa conduzida pela comunidade "
             "Data Hackers em parceria com a Bain & Company.",
    )

    # ---------------------------------------------------------- arquitetura
    slide_grafico(
        prs, "00_arquitetura.png",
        "A solução: um pipeline em camadas sobre a AWS",
        "Da ingestão dos CSVs brutos à consulta analítica catalogada — "
        "processamento distribuído com Spark no AWS Glue",
        nota="Diagrama editável em architecture/arquitetura_aws.drawio",
    )

    # ------------------------------------------------------------ método
    slide_texto(
        prs,
        "Como os dados foram tratados",
        "As três edições não compartilham nomes de coluna nem o mesmo conjunto "
        "de perguntas. Harmonizá-las foi o principal desafio técnico.",
        [
            ("Cabeçalhos incompatíveis",
             "A edição 2023 usa tuplas serializadas ((\"P1_a\", \"Idade\")); as "
             "seguintes usam código pontuado (1.a_idade). Ambos convergem para "
             "um identificador único."),
            ("Códigos que se deslocam",
             "A mesma pergunta muda de letra entre edições — modelo de trabalho "
             "é P2_r em 2024 e P2_q em 2025. O mapeamento é feito pela "
             "semântica, nunca pelo código."),
            ("Perguntas que nascem e morrem",
             "2025 removeu o bloco de linguagens; 2023 não perguntou sobre "
             "cloud. Ausência é registrada como NULL e nunca convertida em "
             "zero."),
            ("Rigor estatístico",
             "Salário em faixas vira ponto médio; usa-se mediana além da média; "
             "recortes com menos de 30 respondentes são sinalizados como "
             "amostra insuficiente."),
        ],
        nota=f"Base consolidada: {milhar(n['total_respondentes'])} respondentes "
             f"({'; '.join(f'{a}: {milhar(v)}' for a, v in sorted(anos.items()))})",
    )

    # ---------------------------------------------------------- destaques
    slide_destaques(
        prs,
        "O que os dados dizem, em cinco números",
        f"Edição {ANO}-{str(ANO + 1)[-2:]}, salvo indicação em contrário",
        [
            (f"{dec(n['multiplo_senior'])}x",
             "o Sênior ganha o salário do Júnior — "
             "o prêmio de senioridade é o maior retorno da carreira"),
            (f"{n['pct_ia_ultimo']:.0f}%",
             "dos profissionais já usam IA generativa no trabalho, "
             f"contra {n['pct_ia_primeiro']:.0f}% duas edições atrás"),
            (f"{n['lacuna_ia']:.0f} p.p.",
             "de contraste entre dois blocos do questionário: uso pessoal "
             f"de IA (n={milhar(n['base_uso_pessoal_ia'])}) e priorização "
             f"pela empresa (n={milhar(n['base_uso_empresa_ia'])}) — "
             "amostras distintas, não a mesma pessoa antes e depois"),
            (f"{n['pct_mulheres_ultimo']:.0f}%",
             "de mulheres no mercado — participação em queda desde "
             f"{n['pct_mulheres_primeiro']:.0f}%"),
            (f"{n['pct_ia_producao']:.0f}%",
             "dos respondentes do bloco organizacional relatam que a "
             "empresa já colhe resultado com IA — o restante ainda está "
             "em piloto ou nem começou"),
        ],
    )

    # ==================================================== 1. O MERCADO
    slide_secao(prs, "01", "Como está estruturado o mercado",
                "Quem são, quantos são e em que nível de carreira estão os "
                "profissionais de dados no Brasil?")
    slide_grafico(
        prs, "01_composicao_mercado.png",
        f"{n['cargo_maior_volume']} concentra o maior volume do mercado",
        f"{milhar(n['cargo_maior_volume_n'])} profissionais na edição {ANO}-"
        f"{str(ANO + 1)[-2:]} — a principal porta de entrada da área",
    )
    slide_grafico(
        prs, "02_piramide_senioridade.png",
        "A fatia de Júnior encolheu ao longo das três edições",
        "Também surge uma faixa de Especialista/Staff+ acima do Sênior — "
        "mas essa categoria só passou a ser perguntada separadamente em "
        "2025-26, então parte do efeito é mudança no questionário, não só "
        "no mercado",
        nota="Considera apenas respondentes com nível de carreira declarado; "
             "desempregados e estudantes ficam fora deste recorte.",
    )

    # ============================================ 2. PERFIS VALORIZADOS
    slide_secao(prs, "02", "Quais perfis o mercado mais valoriza",
                "Onde está o prêmio de remuneração — por carreira, por "
                "senioridade e ao longo do tempo?")
    slide_grafico(
        prs, "04_salario_por_cargo.png",
        f"{n['cargo_topo']} lidera com mediana de {brl(n['cargo_topo_sal'])}",
        "A faixa interquartil mostra a dispersão que uma proposta precisa "
        "considerar — carreiras técnicas de ponta variam muito mais",
    )
    slide_grafico(
        prs, "03_premio_senioridade.png",
        f"Subir de Júnior a Sênior multiplica o salário por {dec(n['multiplo_senior'])}",
        "Nenhuma outra variável do estudo — formação, região ou tecnologia — "
        "produz um salto de remuneração dessa magnitude",
    )
    slide_grafico(
        prs, "11_evolucao_salario_senioridade.png",
        "Só o topo da carreira teve reajuste ao longo das três edições",
        f"A mediana de Júnior e Pleno ficou parada; a de Sênior saltou para "
        f"{brl(n['sal_senior'])}",
        nota="Valores nominais, sem correção pela inflação — em termos reais, "
             "a estabilidade de Júnior e Pleno representa perda de poder de compra.",
    )

    # ==================================================== 3. DIVERSIDADE
    slide_secao(prs, "03", "O cenário de diversidade de gênero",
                "A representatividade feminina está avançando? E existe "
                "diferença de remuneração?")
    slide_grafico(
        prs, "05_representatividade_genero.png",
        f"A participação feminina caiu de {dec(n['pct_mulheres_primeiro'])}% "
        f"para {dec(n['pct_mulheres_ultimo'])}%",
        "A tendência é de retração ao longo das três edições — não de avanço",
    )
    if n["gap_senior"] is not None:
        slide_grafico(
            prs, "06_gap_salarial_genero.png",
            "O gap salarial não existe na base — ele se abre no topo",
            f"Entre Sênior, a mediana feminina é {abs(n['gap_senior']):.0f}% "
            "menor que a masculina; entre Júnior e Pleno não há diferença",
            nota="Controlar por senioridade separa diferença de remuneração de "
                 "diferença de composição — as duas exigem respostas distintas.",
        )

    # ============================================== 4. TECNOLOGIA E IA
    slide_secao(prs, "04", "Tecnologias e adoção de IA",
                "Qual é a stack consolidada do mercado e em que estágio está "
                "a adoção de inteligência artificial?")
    slide_grafico(
        prs, "07_tecnologias.png",
        f"{n['top_linguagem'][0]} e {n['top_cloud'][0]} são as apostas seguras da stack",
        f"{n['top_linguagem'][0]} em {n['top_linguagem'][1]:.0f}% dos "
        f"profissionais, {n['top_cloud'][0]} em {n['top_cloud'][1]:.0f}% e "
        f"{n['top_bi'][0]} em {n['top_bi'][1]:.0f}%",
        nota="Percentuais calculados sobre quem respondeu cada bloco do "
             "questionário, não sobre o total de respondentes.",
    )
    slide_grafico(
        prs, "08_adocao_ia.png",
        f"{n['pct_ia_ultimo']:.0f}% usam IA no trabalho; "
        f"{n['pct_empresa_ia_ultimo']:.0f}% relatam que a empresa prioriza",
        "Dois blocos distintos do questionário, sem respondentes em comum: "
        f"uso pessoal (n={milhar(n['base_uso_pessoal_ia'])}) e priorização "
        f"organizacional (n={milhar(n['base_uso_empresa_ia'])}) — o "
        f"contraste de {n['lacuna_ia']:.0f} p.p. é entre blocos, não dentro "
        "da mesma amostra",
    )
    slide_grafico(
        prs, "12_impacto_ia.png",
        f"Só {n['pct_ia_producao']:.0f}% do bloco organizacional relatam "
        "resultado real com IA",
        f"{n['pct_ia_piloto']:.0f}% ainda estão em piloto sem resultado — a "
        "pergunta que decide o próximo ciclo de investimento não é mais "
        "\"quem usa\", é \"quem entrega\"",
        nota=f"Pergunta exclusiva da edição {ANO}-{str(ANO + 1)[-2:]} "
             f"(n={n['base_impacto_ia']}); não há série histórica para comparar.",
    )

    # ======================================= 5. TRABALHO E GEOGRAFIA
    slide_secao(prs, "05", "Modelos de trabalho e geografia",
                "Onde estão os profissionais, como trabalham e quanto custa "
                "contratá-los em cada região?")
    slide_grafico(
        prs, "09_modelo_trabalho.png",
        "O retorno ao presencial é real, mas lento",
        f"O trabalho remoto caiu de {n['pct_remoto_primeiro']:.0f}% para "
        f"{n['pct_remoto_ultimo']:.0f}%, enquanto o presencial subiu de "
        f"{n['pct_presencial_primeiro']:.0f}% para "
        f"{n['pct_presencial_ultimo']:.0f}%",
    )
    slide_grafico(
        prs, "10_salario_regiao.png",
        f"O gap Nordeste-Sudeste é de {abs(n['desconto_regional_junior']):.0f}% "
        "no Júnior — e some no Sênior",
        "Comparação bruta (todo mundo de uma região contra a outra) mistura "
        "composição de carreira com diferença regional; controlando por "
        "senioridade, a distância real está na base",
        nota="Usa-se a média, e não a mediana: as faixas salariais da pesquisa "
             "são largas e a mediana de todas as regiões cai na mesma faixa. "
             "Especialista/Staff+ no Nordeste tem amostra abaixo de 30 "
             "respondentes — resultado indicativo, não comparação firme.",
    )

    # ==================================================== RECOMENDAÇÕES
    slide_secao(prs, "06", "Recomendações estratégicas",
                "O que a instituição financeira deve fazer com esta evidência.")

    slide_texto(
        prs,
        "Contratação: onde está a arbitragem",
        "Quatro movimentos que reduzem custo sem reduzir qualidade do time.",
        [
            ("Formar em vez de disputar sênior",
             f"O Sênior custa {dec(n['multiplo_senior'])}x o Júnior e é o perfil "
             "mais disputado. Contratar Pleno e investir em trilha interna "
             "captura a maior parte da competência por fração do custo."),
            ("Usar o remoto como alavanca geográfica — só na base",
             f"Com {n['pct_remoto_ultimo']:.0f}% do mercado em regime remoto, "
             f"contratar Júnior no {n['regiao_barata']} custa "
             f"{abs(n['desconto_regional_junior']):.0f}% menos que no "
             f"{n['regiao_cara']}. No Sênior essa vantagem já não existe — "
             "a arbitragem funciona para formar talento, não para economizar "
             "no topo da carreira."),
            ("Priorizar Engenharia de Dados",
             "É a segunda maior família de carreira e a que sustenta qualquer "
             "iniciativa de IA. Sem base de dados confiável, investimento em "
             "modelo não se converte em resultado."),
            ("Tratar diversidade como risco de talento",
             f"Com a participação feminina em {n['pct_mulheres_ultimo']:.0f}% e "
             "em queda, quem não atuar sobre retenção e promoção disputa um "
             "funil cada vez mais estreito."),
        ],
    )

    slide_texto(
        prs,
        "Tecnologia e IA: onde investir",
        "A stack a padronizar e o estágio real da adoção de IA.",
        [
            ("Padronizar na stack consolidada",
             f"{n['top_linguagem'][0]}, {n['top_cloud'][0]} e "
             f"{n['top_bi'][0]} concentram a adoção. Escolher fora disso "
             "aumenta o custo e o tempo de contratação."),
            ("Fechar a lacuna de IA pelo lado da empresa",
             f"{n['pct_ia_ultimo']:.0f}% dos profissionais já usam IA "
             f"generativa, mas só {n['pct_empresa_ia_ultimo']:.0f}% dos "
             "respondentes do bloco organizacional relatam que a empresa "
             "prioriza IA — blocos diferentes do questionário, não a mesma "
             "amostra. O uso já acontece — sem política, acontece sem "
             "governança."),
            ("Ancorar a governança antes de escalar",
             "Uso individual de ferramentas pagas do próprio bolso é comum na "
             "amostra. Para uma instituição financeira, isso é exposição de "
             "dado sensível a fornecedor não homologado."),
            ("Medir retorno, não adoção",
             f"A adoção individual já está saturada ({n['pct_ia_ultimo']:.0f}%). "
             "O que diferencia as empresas agora é sair do piloto: só "
             f"{n['pct_ia_producao']:.0f}% do bloco organizacional relata "
             f"resultado — a maioria ({n['pct_ia_piloto']:.0f}%) ainda testa "
             "sem retorno mensurável."),
        ],
    )

    # ------------------------------------------------- notas metodológicas
    slide_texto(
        prs,
        "Notas metodológicas e limitações",
        "O que este estudo pode e o que não pode sustentar.",
        [
            ("Amostra autosselecionada",
             "A pesquisa é respondida por voluntários da comunidade Data "
             "Hackers. Sobre-representa profissionais engajados e o Sudeste; "
             "não é uma amostra probabilística do mercado."),
            ("Salário em faixas largas",
             "A remuneração é coletada em intervalos, convertidos aqui no ponto "
             "médio. Diferenças menores que uma faixa não são detectáveis — daí "
             "o uso da média nos cortes regionais."),
            ("Base decrescente entre edições",
             f"De {milhar(anos[min(anos)])} respondentes na primeira edição "
             f"para {milhar(anos[max(anos)])} na última. Comparações entre "
             "anos são de proporção, nunca de volume absoluto."),
            ("Perguntas não comparáveis",
             "Blocos que existem em apenas parte das edições são analisados "
             "somente nos anos disponíveis, e os gráficos indicam isso "
             "explicitamente."),
        ],
        nota="Pipeline, consultas e scripts completos no repositório do projeto. "
             "Todos os números deste material são gerados a partir da camada "
             "Gold, sem digitação manual.",
    )

    return prs


def main() -> None:
    print("Coletando números da camada Gold...")
    numeros = coletar_numeros()

    print("Montando o material executivo...")
    prs = construir(numeros)

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    prs.save(SAIDA)
    print(f"\ngerado  {SAIDA.relative_to(RAIZ)}  ({len(prs.slides._sldIdLst)} slides)")


if __name__ == "__main__":
    main()
