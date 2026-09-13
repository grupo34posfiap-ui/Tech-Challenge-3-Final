"""
Schema canônico da camada Silver e regras de harmonização das 3 edições.

O problema central deste Tech Challenge não é volume — é *heterogeneidade*. As
três edições do State of Data Brasil divergem em três níveis, e cada um exige
um tratamento diferente:

  1. **Formato do cabeçalho.** 2023 usa tupla serializada (``('P1_a ', 'Idade')``);
     2024 e 2025 usam código pontuado (``1.a_idade``). Resolvido em
     ``schema_utils``, que converte ambos para ``p1_a_idade``.

  2. **Deslocamento dos códigos de pergunta.** A MESMA pergunta muda de letra
     entre edições — "modelo de trabalho atual" é ``p2_r`` em 2024 e ``p2_q``
     em 2025; "banco de dados do dia a dia" é ``p4_g`` em 2023/2024 e ``p4_d``
     em 2025. Por isso o mapeamento aqui é feito pela **semântica do enunciado**,
     nunca pelo código da pergunta.

  3. **Perguntas que nascem e morrem.** 2025 removeu o bloco "linguagens que
     você usa no dia a dia"; 2023 não tem "cloud do dia a dia" nem "planos de
     mudar de emprego". Isso é fato do negócio, não bug — o pipeline preenche
     com NULL e registra a ausência em log.

Armadilhas reais que o dicionário abaixo evita:
  * ``modelo_de_trabalho_atual`` vs ``modelo_de_trabalho_ideal`` — casar o
    padrão errado inverteria a leitura sobre trabalho remoto;
  * ``linguagem_de_programacao_dia_a_dia`` vs ``linguagem_mais_usada`` /
    ``linguagem_preferida`` — só o primeiro é multi-seleção;
  * blocos one-hot (``p2_o_10_...``) sendo confundidos com a pergunta-mãe.
"""
from __future__ import annotations

import re
from typing import Dict, List

# ===========================================================================
# 1. SCHEMA CANÔNICO
#
# Cada campo declara:
#   padroes — regex, em ordem de prioridade, que localizam a coluna
#   excluir — regex que DESQUALIFICAM uma candidata (o antídoto para
#             "ideal" vs "atual" e para as colunas one-hot filhas)
#
# Ordem importa: o primeiro padrão que casar (e não for excluído) vence.
# ===========================================================================
Campo = Dict[str, List[str]]

# Sufixo numérico = coluna one-hot filha de um bloco, nunca a pergunta-mãe.
ONE_HOT = r"_\d+_"

CANONICAL_FIELDS: dict[str, Campo] = {
    # ---------------------------------------------------------------- perfil
    "respondente_id": {"padroes": [r"^p0_id$", r"^p0_a_token$"]},
    "idade": {"padroes": [r"^p1_a_idade$"]},
    "faixa_idade": {"padroes": [r"^p1_a_1_faixa_idade$"]},
    "genero": {"padroes": [r"^p1_b_genero$"]},
    "cor_raca_etnia": {"padroes": [r"^p1_c_cor_raca_etnia$"]},
    "pcd": {"padroes": [r"^p1_d_pcd$"]},

    # ------------------------------------------------------------ localização
    "uf_residencia": {"padroes": [r"uf_onde_mora"]},
    "regiao_declarada": {"padroes": [r"regiao_onde_mora"]},

    # -------------------------------------------------------------- formação
    "nivel_ensino": {"padroes": [r"nivel_de_ensino"]},
    "area_formacao": {"padroes": [r"area_de_formacao"]},

    # ------------------------------------------------------------- ocupação
    # 2023: "qual_sua_situacao_atual_de_trabalho" | 2024+: "situacao_de_trabalho"
    "situacao_trabalho": {
        "padroes": [r"situacao_(atual_)?de_trabalho", r"^p2_a_"],
        "excluir": [ONE_HOT],
    },
    "setor_empresa": {"padroes": [r"^p2_b_setor$"]},
    "porte_empresa": {"padroes": [r"numero_de_funcionarios"]},
    # 2023: "p2_d_gestor" | 2024+: "p2_d_atua_como_gestor"
    "gestor": {
        "padroes": [r"^p2_d_(atua_como_)?gestor$"],
        "excluir": [ONE_HOT],
    },
    "cargo": {"padroes": [r"^p2_f_cargo_atual$"]},
    # 2023: p2_g_nivel / p2_h_faixa_salarial | 2024+: código desloca uma
    # letra (p2_h_nivel / p2_i_faixa_salarial) — mesmo enunciado, código
    # diferente. Casar só pelo código de 2023 (como estava antes) derrubava
    # os dois campos pra NULL em 2024 e 2025, que são a maioria da amostra.
    "senioridade": {
        "padroes": [r"^p2_[a-z]_nivel$"],
        "excluir": [ONE_HOT],
    },
    "faixa_salarial": {
        "padroes": [r"^p2_[a-z]_faixa_salarial$"],
        "excluir": [ONE_HOT],
    },
    # 2023: "quanto_tempo_de_experiencia_na_area_de_dados_voce_tem"
    # 2024+: "tempo_de_experiencia_em_dados"
    "tempo_experiencia_dados": {
        "padroes": [
            r"tempo_de_experiencia_(em|na_area_de)_dados",
            r"experiencia_na_area_de_dados",
        ],
        "excluir": [ONE_HOT],
    },
    "tempo_experiencia_ti": {
        "padroes": [
            r"tempo_de_experiencia_em_ti",
            r"experiencia_na_area_de_ti",
        ],
        "excluir": [ONE_HOT],
    },
    # ARMADILHA: toda edição tem também o modelo IDEAL. Casar o ideal inverteria
    # completamente a leitura sobre trabalho remoto — daí a exclusão explícita.
    "modelo_trabalho": {
        "padroes": [
            r"modelo_de_trabalho_atual",
            r"atualmente_qual_a_sua_forma_de_trabalho",
            r"forma_de_trabalho",
        ],
        "excluir": [r"ideal", r"retorno_presencial", r"atitude", ONE_HOT],
    },
    "satisfacao_empresa": {
        "padroes": [r"^p2_k_(voce_esta_)?satisfeito"],
        "excluir": [ONE_HOT],
    },
    "motivo_insatisfacao": {
        "padroes": [r"motivo_insatisfacao", r"principal_motivo_da_sua_insatisfacao"],
        "excluir": [ONE_HOT],
    },
    # Só existe a partir de 2024
    "busca_nova_oportunidade": {
        "padroes": [r"planos_de_mudar_de_emprego"],
        "excluir": [ONE_HOT],
    },
    "empresa_teve_layoff": {
        "padroes": [r"passou_por_layoff"],
        "excluir": [ONE_HOT],
    },

    # --------------------------------------------------------- IA generativa
    # 2023: "utiliza_chatgpt_ou_llms_no_trabalho"
    # 2024/25: "usa_chatgpt_ou_copilot_no_trabalho"
    "tipo_uso_ia": {
        "padroes": [r"(usa|utiliza)_chatgpt"],
        "excluir": [ONE_HOT],
    },
    # Prioridade de IA generativa na empresa — presente nas 3 edições
    "prioridade_ia_empresa": {
        "padroes": [r"ai_generativa.*prioridade"],
        "excluir": [ONE_HOT],
    },
    # Só 2025: a empresa está conseguindo resultado com LLMs?
    "resultado_ia_empresa": {
        "padroes": [r"bons_resultados_com_llms"],
        "excluir": [ONE_HOT],
    },

    # ------------------------------------------------------------- ambiente
    "cloud_preferida": {
        "padroes": [r"^p4_[a-z]_cloud_preferida$", r"cloud_preferida"],
        "excluir": [ONE_HOT, r"dentre_as_opcoes"],
    },
    "possui_data_lake": {
        "padroes": [r"possui_data_lake", r"organizacao_possui_um_data_lake"],
        "excluir": [ONE_HOT],
    },
}


# ===========================================================================
# 2. GRUPOS MULTI-SELEÇÃO (colunas one-hot -> array<string>)
#
# A pesquisa registra "quais linguagens você usa" como dezenas de colunas
# binárias. Os nomes dessas colunas filhas trazem APENAS o nome da tecnologia
# (``p4_d_1_sql``) — a semântica do bloco vive só na pergunta-mãe
# (``p4_d_linguagem_de_programacao_dia_a_dia``).
#
# Por isso a resolução é em dois passos: localizar a pergunta-mãe pela
# semântica, extrair o código dela, e então coletar as filhas por esse código.
# É o que sobrevive ao deslocamento das letras entre edições.
# ===========================================================================
MULTI_SELECT_GROUPS: dict[str, Campo] = {
    "linguagens": {
        "padroes": [
            r"linguagem_de_programacao_dia_a_dia",
            r"quais_das_linguagens_listadas.*utiliza_no_trabalho",
        ],
        # "linguagem mais usada" e "linguagem preferida" são escolha única
        "excluir": [r"mais_utiliza", r"preferida", r"qual_e_a_que", ONE_HOT],
    },
    "bancos_dados": {
        "padroes": [
            r"banco_de_dados_dia_a_dia",
            r"quais_dos_bancos_de_dados.*utiliza_no_trabalho",
        ],
        "excluir": [r"preferid", ONE_HOT],
    },
    "cloud_utilizada": {
        # Não existe em 2023 — aquela edição só perguntou a cloud preferida
        "padroes": [r"^p4_[a-z]_cloud_dia_a_dia$", r"cloud_dia_a_dia"],
        "excluir": [r"preferida", ONE_HOT],
    },
    "ferramentas_bi": {
        "padroes": [
            r"ferramenta_de_bi_dia_a_dia",
            r"ferramenta_de_bi_utilizada_no_dia_a_dia",
        ],
        "excluir": [r"preferida", ONE_HOT],
    },
}


# ===========================================================================
# 3. NORMALIZADORES DE VALOR
# ===========================================================================

# --- UF -> Região -----------------------------------------------------------
UF_PARA_REGIAO: dict[str, str] = {
    "AC": "Norte", "AP": "Norte", "AM": "Norte", "PA": "Norte",
    "RO": "Norte", "RR": "Norte", "TO": "Norte",
    "AL": "Nordeste", "BA": "Nordeste", "CE": "Nordeste", "MA": "Nordeste",
    "PB": "Nordeste", "PE": "Nordeste", "PI": "Nordeste", "RN": "Nordeste",
    "SE": "Nordeste",
    "DF": "Centro-Oeste", "GO": "Centro-Oeste",
    "MT": "Centro-Oeste", "MS": "Centro-Oeste",
    "ES": "Sudeste", "MG": "Sudeste", "RJ": "Sudeste", "SP": "Sudeste",
    "PR": "Sul", "RS": "Sul", "SC": "Sul",
}

# --- Senioridade ------------------------------------------------------------
# A pesquisa pergunta o nível (p2_g_nivel) separado de "é gestor?" (p2_d), então
# liderança NÃO aparece aqui. "Especialista/Staff+" surge apenas em 2025 e é
# mantido como categoria própria: fundi-lo em "Sênior" apagaria justamente a
# novidade que a edição quis capturar.
SENIORIDADE_CANONICA: list[tuple[str, str]] = [
    (r"junior|trainee|est[aá]gi", "Júnior"),
    (r"pleno", "Pleno"),
    (r"especialista|staff", "Especialista/Staff+"),
    (r"s[eê]nior", "Sênior"),
]
ORDEM_SENIORIDADE = ["Júnior", "Pleno", "Sênior", "Especialista/Staff+"]

# --- Modelo de trabalho -----------------------------------------------------
# As duas variações de híbrido (flexível e com dias fixos) são colapsadas: a
# distinção não muda nenhuma das conclusões de negócio e fragmentaria os
# gráficos. A regra de híbrido vem ANTES de presencial porque o rótulo
# "Modelo híbrido com dias fixos de trabalho presencial" contém as duas palavras.
MODELO_TRABALHO_CANONICO: list[tuple[str, str]] = [
    (r"h[ií]brido", "Híbrido"),
    (r"100%\s*remoto|totalmente\s+remoto|^remoto", "Remoto"),
    (r"presencial", "Presencial"),
]
ORDEM_MODELO = ["Presencial", "Híbrido", "Remoto"]

# --- Cargo ------------------------------------------------------------------
# Ordem importa: "Engenheiro de Machine Learning" deve cair em ML Engineer,
# não em Engenharia de Dados.
CARGO_CANONICO: list[tuple[str, str]] = [
    (r"engenheiro.*machine\s*learning|ml\s*engineer|mlops", "ML Engineer / MLOps"),
    (r"cientista\s*de\s*dados|data\s*scientist", "Cientista de Dados"),
    (r"engenheiro\s*de\s*dados|data\s*engineer|arquiteto\s*de\s*dados|data\s*architect",
     "Engenheiro de Dados"),
    (r"analista\s*de\s*bi|bi\s*analyst|business\s*intelligence", "Analista de BI"),
    (r"analytics\s*engineer", "Analytics Engineer"),
    (r"analista\s*de\s*dados|data\s*analyst", "Analista de Dados"),
    (r"product\s*manager|gerente\s*de\s*produto|product\s*owner", "Produto"),
    (r"analista\s*de\s*neg[oó]cios|business\s*analyst", "Analista de Negócios"),
    (r"desenvolvedor|software\s*engineer|engenheiro\s*de\s*software", "Engenharia de Software"),
    (r"estat[ií]stic|economista", "Estatística / Economia"),
    (r"professor|pesquisador", "Academia / Pesquisa"),
    (r"dba|administrador\s*de\s*banco", "DBA"),
    (r"outra\s*op[cç][aã]o|outro", "Outros"),
]

# --- Gênero -----------------------------------------------------------------
GENERO_CANONICO: list[tuple[str, str]] = [
    (r"^masculino|^homem", "Masculino"),
    (r"^feminino|^mulher", "Feminino"),
    (r"outro|prefiro\s*n[aã]o|n[aã]o\s*bin[aá]ri", "Outro / Não informado"),
]

# --- Uso de IA generativa ---------------------------------------------------
# A resposta é texto descritivo, não sim/não. Em 2025 o respondente pode marcar
# mais de uma opção, e elas vêm concatenadas por vírgula — por isso as regras
# de maior comprometimento (pago pela empresa, ferramenta de código) são
# avaliadas ANTES das de menor.
TIPO_USO_IA_CANONICO: list[tuple[str, str]] = [
    (r"n[aã]o\s+utilizo\s+nenhum", "Não utiliza"),
    (r"empresa\s+em\s+que\s+trabalho\s+paga", "Paga — custeada pela empresa"),
    (r"pago\s+do\s+meu\s+pr[oó]prio\s+bolso", "Paga — custeada pelo profissional"),
    (r"copilot|ai\s+para\s+c[oó]digo|github\s+copilot|cursor", "Ferramentas de código (Copilot)"),
    (r"solu[cç][oõ]es\s+gratuitas|apenas.*gratuit", "Apenas soluções gratuitas"),
]

# --- Prioridade de IA na empresa --------------------------------------------
PRIORIDADE_IA_CANONICA: list[tuple[str, str]] = [
    (r"^sim,?\s*[eé]\s*nossa\s*principal\s*prioridade", "Prioridade máxima"),
    (r"^sim", "Alta prioridade"),
    (r"^mais\s*ou\s*menos", "Iniciativa isolada"),
    (r"n[aã]o\s*[eé]\s*uma\s*iniciativa", "Não é prioridade"),
    (r"n[aã]o\s*sei\s*opinar", "Não sabe opinar"),
]

# --- Resultado obtido com IA generativa (só existe na edição 2025-26) ------
# Responde à parte do enunciado que a adoção sozinha não cobre: "qual o
# índice de adoção de IA generativa E SEU IMPACTO". Ordem importa — "não sei
# opinar" e "ainda não começamos" têm que ser checados antes do padrão
# genérico de investigação, senão "não" captura os dois por engano.
RESULTADO_IA_CANONICA: list[tuple[str, str]] = [
    (r"n[aã]o\s*sei\s*opinar", "Não sabe opinar"),
    (r"^sim.*produ[cç][aã]o", "Em produção, com resultado"),
    (r"em\s+partes|piloto", "Piloto, sem resultado ainda"),
    (r"ainda\s+n[aã]o\s+come[cç]amos", "Não começou"),
    (r"investiga[cç][aã]o", "Em investigação/planejamento"),
]

# --- Respostas booleanas ----------------------------------------------------
VALORES_VERDADEIROS = {"1", "1.0", "true", "sim", "yes", "s", "verdadeiro"}
VALORES_FALSOS = {"0", "0.0", "false", "nao", "não", "no", "n", "falso"}


def parse_faixa_salarial(faixa: str | None) -> float | None:
    """
    Converte a faixa salarial textual no seu ponto médio mensal, em reais.

    A pesquisa reporta salário em faixas ("de R$ 4.001/mês a R$ 6.000/mês"),
    o que impede média e mediana diretas. Usamos o ponto médio da faixa — a
    convenção padrão para dados intervalares.

    Faixas abertas recebem tratamento explícito: "Menos de R$ 1.000" vira a
    metade do teto, e "Acima de R$ 40.001" vira 1,25x o piso (estimativa
    conservadora: a cauda superior é longa, mas rala).

    >>> parse_faixa_salarial("de R$ 4.001/mês a R$ 6.000/mês")
    5000.5
    >>> parse_faixa_salarial("Acima de R$ 40.001/mês")
    50001.25
    >>> parse_faixa_salarial("Menos de R$ 1.000/mês")
    500.0
    """
    if not faixa:
        return None

    texto = str(faixa).strip().lower()
    if not texto or texto in {"nan", "none", "null"}:
        return None

    # Quem não recebe não entra na estatística salarial — tratar como zero
    # rebaixaria artificialmente todas as medianas.
    if "não recebo" in texto or "nao recebo" in texto or "sem renda" in texto:
        return None

    numeros = [
        float(n.replace(".", "").replace(",", "."))
        for n in re.findall(r"\d{1,3}(?:\.\d{3})*(?:,\d+)?|\d+", texto)
    ]
    numeros = [n for n in numeros if n >= 100]

    if not numeros:
        return None

    if len(numeros) >= 2:
        return (numeros[0] + numeros[1]) / 2

    valor = numeros[0]
    if "menos de" in texto or "até" in texto or "ate" in texto:
        return valor / 2
    if "acima" in texto or "mais de" in texto or "maior" in texto:
        return valor * 1.25
    return valor


def canonicalizar(valor: str | None, regras: list[tuple[str, str]],
                  default: str | None = None) -> str | None:
    """
    Aplica a primeira regra regex que casar com o valor (case-insensitive).

    Ausência devolve ``default`` — que é NULL por padrão, e não um rótulo. Um
    "Não informado" textual atravessaria todos os ``GROUP BY`` como se fosse
    uma categoria real do mercado.
    """
    if not valor:
        return default
    texto = str(valor).strip().lower()
    if not texto or texto in {"nan", "none", "null"}:
        return default
    for padrao, canonico in regras:
        if re.search(padrao, texto):
            return canonico
    return valor.strip()


def parse_booleano(valor: str | None) -> bool | None:
    """Interpreta as várias grafias de sim/não usadas na pesquisa."""
    if valor is None:
        return None
    texto = str(valor).strip().lower()
    if texto in VALORES_VERDADEIROS:
        return True
    if texto in VALORES_FALSOS:
        return False
    if texto.startswith("sim"):
        return True
    if texto.startswith("n") and not texto.startswith("não sei"):
        return False
    return None


def usa_ia_generativa(tipo_uso: str | None) -> bool | None:
    """
    Deriva o booleano de adoção a partir da resposta descritiva.

    A pergunta não é sim/não: o respondente escolhe COMO usa. Quem marcou
    "Não utilizo nenhum tipo de solução" é o único não-adotante; qualquer
    outra resposta preenchida indica uso.
    """
    if not tipo_uso:
        return None
    texto = str(tipo_uso).strip().lower()
    if not texto or texto in {"nan", "none", "null"}:
        return None
    if re.search(r"n[aã]o\s+utilizo\s+nenhum", texto):
        return False
    return True


def empresa_prioriza_ia(prioridade: str | None) -> bool | None:
    """
    True quando a empresa declara IA generativa como prioridade real.

    "Mais ou menos / iniciativas isoladas" conta como NÃO prioridade: o texto
    da própria alternativa diz "mas não é uma prioridade". "Não sei opinar"
    vira NULL, não False — desconhecimento não é negação.
    """
    if not prioridade:
        return None
    texto = str(prioridade).strip().lower()
    if not texto or texto in {"nan", "none", "null"}:
        return None
    if re.match(r"n[aã]o\s*sei\s*opinar", texto):
        return None
    return bool(re.match(r"^sim", texto))


# ===========================================================================
# 4. NOMES DE EXIBIÇÃO DAS TECNOLOGIAS
# ===========================================================================
NOME_EXIBICAO_TECNOLOGIA: dict[str, str] = {
    "sql": "SQL", "nosql": "NoSQL", "r": "R", "php": "PHP",
    "c c mais mais c": "C/C++/C#", "net": ".NET", "dotnet": ".NET",
    "js": "JavaScript", "javascript": "JavaScript", "typescript": "TypeScript",
    "sas stata": "SAS/Stata", "visual basic vba": "Visual Basic/VBA",
    "power bi": "Power BI", "powerbi": "Power BI",
    "looker studio": "Looker Studio", "looker": "Looker",
    "google data studio": "Google Data Studio",
    "qlik view": "QlikView", "qlik sense": "Qlik Sense",
    "amazon web services aws": "AWS", "google cloud gcp": "Google Cloud",
    "azure microsoft": "Azure", "oracle cloud": "Oracle Cloud", "ibm": "IBM",
    "servidores on premise nao utilizamos cloud": "On-premise",
    "cloud propria": "Cloud própria",
    "aws": "AWS", "gcp": "Google Cloud", "azure": "Azure",
    "amazon athena": "Amazon Athena", "amazon redshift": "Amazon Redshift",
    "google bigquery": "BigQuery", "bigquery": "BigQuery",
    "amazon aurora ou rds": "Amazon Aurora/RDS", "dynamodb": "DynamoDB",
    "sql server": "SQL Server", "mysql": "MySQL", "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL", "mongodb": "MongoDB", "sqlite": "SQLite",
    "oracle": "Oracle", "db2": "Db2", "mariadb": "MariaDB",
    "elasticsearch": "Elasticsearch", "cassandra": "Cassandra",
    "hbase": "HBase", "coachdb": "CouchDB", "couchdb": "CouchDB",
    "databricks": "Databricks", "snowflake": "Snowflake",
    "sap hana": "SAP HANA", "teradata": "Teradata", "firebase": "Firebase",
    "excel": "Excel", "tableau": "Tableau", "metabase": "Metabase",
    "superset": "Superset", "pentaho": "Pentaho",
    "microstrategy": "MicroStrategy", "grafana": "Grafana", "redash": "Redash",

    # Rótulos longos que a pesquisa usa para nomear a mesma ferramenta —
    # sem esta tradução o eixo do gráfico fica ilegível.
    "microsoft powerbi": "Power BI",
    "looker studio google data studio": "Looker Studio",
    "qlik view qlik sense": "Qlik",
    "ibm analytics cognos": "IBM Cognos",
    "sap business objects sap analytics": "SAP BusinessObjects",
    "sas visual analytics": "SAS Visual Analytics",
    "salesforce einstein analytics": "Salesforce Einstein",
    "oracle business intelligence": "Oracle BI",
    "amazon quicksight": "Amazon QuickSight",
    "tibco spotfire": "TIBCO Spotfire",
    "microsoft access": "Microsoft Access",
    "google firestore": "Google Firestore",
    # Resposta que significa "nenhuma ferramenta de BI, só planilha" — é um
    # achado de negócio relevante, então fica no ranking com nome curto.
    "fazemos todas as analises utilizando apenas excel ou planilhas do google":
        "Apenas Excel/Planilhas",
}


def nome_exibicao(rotulo: str) -> str:
    """
    Converte o rótulo cru da coluna na grafia comercial da tecnologia.

    Cai em Title Case quando a tecnologia não está no dicionário — melhor um
    "Kotlin" do que um "kotlin" no slide.

    >>> nome_exibicao("power bi")
    'Power BI'
    >>> nome_exibicao("kotlin")
    'Kotlin'
    """
    chave = rotulo.strip().lower()
    if chave in NOME_EXIBICAO_TECNOLOGIA:
        return NOME_EXIBICAO_TECNOLOGIA[chave]
    return " ".join(p.capitalize() for p in chave.split())


# ===========================================================================
# 5. RESOLVER — casa o schema canônico contra as colunas reais do Bronze
# ===========================================================================
def _candidatas(colunas: list[str], spec: Campo,
                ja_usadas: set[str] | None = None) -> str | None:
    """Primeira coluna que satisfaz os padrões e escapa das exclusões."""
    ja_usadas = ja_usadas or set()
    excluir = spec.get("excluir", [])

    for padrao in spec["padroes"]:
        achadas = [
            c for c in colunas
            if re.search(padrao, c)
            and not any(re.search(x, c) for x in excluir)
            and c not in ja_usadas
        ]
        if achadas:
            # Entre múltiplas candidatas, a de nome mais curto é a mais provável
            # de ser a pergunta principal — as demais costumam ser desdobramentos
            # ("_outros", "_especifique").
            return min(achadas, key=len)
    return None


def resolve_schema(colunas_bronze: list[str]) -> tuple[dict[str, str], list[str]]:
    """
    Mapeia cada campo canônico para a coluna real do Bronze que o representa.

    Retorna ``(mapeamento, nao_resolvidos)``. Campos não resolvidos são
    devolvidos explicitamente para que o job os registre em log — uma edição
    que não fez determinada pergunta é fato do negócio, não bug, mas precisa
    ficar visível.
    """
    mapeamento: dict[str, str] = {}
    nao_resolvidos: list[str] = []
    ja_usadas: set[str] = set()

    for campo, spec in CANONICAL_FIELDS.items():
        achou = _candidatas(colunas_bronze, spec, ja_usadas)
        if achou:
            mapeamento[campo] = achou
            ja_usadas.add(achou)
        else:
            nao_resolvidos.append(campo)

    return mapeamento, nao_resolvidos


def resolve_multiselect(colunas_bronze: list[str]) -> dict[str, list[str]]:
    """
    Localiza as colunas one-hot de cada grupo multi-seleção.

    Estratégia em dois passos, porque as colunas filhas não carregam a
    semântica do bloco:

      1. acha a pergunta-mãe pelo enunciado (``p4_d_linguagem_..._dia_a_dia``);
      2. extrai o código dela (``p4_d``) e coleta as filhas ``p4_d_<n>_*``.

    É isso que sobrevive ao deslocamento das letras entre edições — em 2025 o
    bloco de bancos de dados migrou de ``p4_g`` para ``p4_d``.
    """
    grupos: dict[str, list[str]] = {}

    for nome, spec in MULTI_SELECT_GROUPS.items():
        mae = _candidatas(colunas_bronze, spec)
        if not mae:
            grupos[nome] = []
            continue

        # O código do bloco são os dois primeiros segmentos: "p4_d"
        partes = mae.split("_")
        if len(partes) < 2:
            grupos[nome] = []
            continue
        prefixo = f"{partes[0]}_{partes[1]}"

        grupos[nome] = sorted(
            c for c in colunas_bronze
            if re.match(rf"^{re.escape(prefixo)}_\d+_", c)
        )

    return grupos


# Dentro dos blocos one-hot existe uma opção "não utilizo nenhuma das
# listadas". Ela é uma resposta legítima, mas não é uma tecnologia — deixá-la
# no array a faria aparecer no ranking de adoção competindo com SQL e Python.
ITEM_NAO_TECNOLOGIA = re.compile(
    r"nao_utilizo|nenhuma_das|nenhum_dos|^outra|^outro|nao_sei_informar",
    re.IGNORECASE,
)


def eh_item_tecnologia(coluna: str) -> bool:
    """False para as opções do one-hot que não nomeiam uma tecnologia."""
    return not ITEM_NAO_TECNOLOGIA.search(coluna)


def rotulo_item_multiselect(coluna: str) -> str:
    """
    Extrai o nome legível da tecnologia a partir do nome da coluna one-hot.

    ``p4_d_1_sql`` -> ``SQL``. O código do bloco e o índice são removidos, e a
    grafia comercial é aplicada.

    >>> rotulo_item_multiselect("p4_d_1_sql")
    'SQL'
    >>> rotulo_item_multiselect("p4_h_1_amazon_web_services_aws")
    'AWS'
    """
    rotulo = re.sub(r"^p\d+_[a-z0-9]+_\d+_", "", coluna)
    rotulo = rotulo.replace("_", " ").strip()
    return nome_exibicao(rotulo) if rotulo else coluna
