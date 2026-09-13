# Tech Challenge — Fase 3
## O mercado brasileiro de Dados e IA — pipeline de Big Data & Analytics na AWS

**Grupo 34** — Arthur Dalbello Vicentini, Giovani dos Reis Gil, Pedro Henrique
Bitencourt Dias, Luiz Henrique Gusmão Souto e Silva, Enrique Jorge Matuoka

Solução de Engenharia de Dados e Analytics sobre as **três últimas edições** da
pesquisa State of Data Brasil (Data Hackers + Bain), do dado bruto à
recomendação executiva.

**14.002 respondentes** consolidados · **3 edições** (2023-24, 2024-25, 2025-26)
· **9 tabelas analíticas** · **28 consultas Athena** · **12 gráficos**

---

## Entregáveis

| Entregável exigido | Onde está |
|---|---|
| **1. Material executivo com DataViz e Storytelling** | [`output/Tech_Challenge_Fase3_Material_Executivo.pptx`](output/) — 26 slides |
| **2. Diagrama da arquitetura AWS (Draw.io)** | [`architecture/arquitetura_aws.drawio`](architecture/) — editável · versão PNG em [`output/charts/00_arquitetura.png`](output/charts/) |
| **3. Scripts e códigos** | [`src/glue_jobs/`](src/glue_jobs/) (PySpark, o que roda de fato no Glue) · [`notebooks/`](notebooks/) (os mesmos 3 jobs em `.ipynb`, já executados, com a saída real) · [`sql/`](sql/) (Athena) · [`scripts/`](scripts/) (deploy AWS) |

O pipeline rodou de fato no AWS Academy Lab, com as **28 consultas do Athena
executadas via CLI direto contra o Trino real** (não simulação local) — 0
falhas. Evidência com run IDs dos Glue Jobs, tabelas catalogadas pelo
Crawler e a reprodutibilidade cruzada (mesmo resultado local e na AWS) está
em [`docs/evidencia_execucao_aws.md`](docs/evidencia_execucao_aws.md).

---

## Por que estas três edições

O enunciado pede as **3 últimas pesquisas disponíveis** no Data Hackers. Em
agosto de 2026, são:

| Edição | Respondentes | Kaggle |
|---|---|---|
| State of Data Brasil 2023-2024 | 5.293 | `datahackers/state-of-data-brazil-2023` |
| State of Data Brasil 2024-2025 | 5.217 | `datahackers/state-of-data-brazil-20242025` |
| State of Data Brasil 2025-2026 | 3.495 | `datahackers/state-of-data-brazil-2025-2026` |

Os números acima são a **base bruta** (CSV como baixado do Kaggle). O
pipeline remove 3 duplicatas na consolidação Bronze → Silver, então a base
**deduplicada** que efetivamente vira Silver/Gold tem 5.215 (2024-25) e 3.494
(2025-26) respondentes — os totais citados no resto deste README e no
material executivo já são pós-deduplicação.

Os CSVs vão em `data/raw/`. O nome do arquivo precisa conter o ano de início da
coleta — o pipeline usa isso para definir a partição `survey_year`.

---

## O desafio técnico real

O volume é pequeno; o problema é **heterogeneidade**. As três edições divergem
em três níveis, e cada um é uma armadilha que produz erro silencioso:

**1. O formato do cabeçalho mudou.**
A edição 2023 usa tuplas serializadas como nome de coluna —
`"('P1_a ', 'Idade')"` — enquanto 2024 e 2025 usam código pontuado —
`1.a_idade`. [`src/schema_utils.py`](src/schema_utils.py) converte os dois para
o mesmo identificador (`p1_a_idade`). Sem isso, praticamente nenhuma coluna
alinharia entre 2023 e as edições seguintes; com isso, **185 colunas passam a
coincidir nas três**.

**2. Os códigos das perguntas se deslocam entre edições.**
A mesma pergunta muda de letra: "modelo de trabalho atual" é `P2_r` em 2024 e
`P2_q` em 2025; o bloco de bancos de dados migrou de `P4_g` para `P4_d`. Por
isso o mapeamento em [`src/mappings.py`](src/mappings.py) é feito pela
**semântica do enunciado**, nunca pelo código — com exclusões explícitas.

> A armadilha mais cara: toda edição pergunta o modelo de trabalho **atual** e
> o **ideal**. Casar o padrão errado inverteria completamente a leitura sobre
> trabalho remoto.

**3. Perguntas nascem e morrem.**
2025 removeu o bloco "linguagens que você usa"; 2023 não pergunta sobre "cloud
do dia a dia"; "planos de mudar de emprego" só existe a partir de 2024. Isso é
fato do negócio, não bug — vira `NULL`, é registrado em log e os gráficos
indicam a ausência em vez de plotar zero.

---

## Arquitetura

```
CSVs (Kaggle)  →  S3 raw  →  Glue job_bronze  →  S3 bronze
                                                     ↓
                              Glue job_silver  →  S3 silver
                                                     ↓
                                Glue job_gold  →  S3 gold
                                                     ↓
                 2 Glue Crawlers (Silver e Gold) → Data Catalog
                                                     ↓
                                    Athena → gráficos e deck
```

Dois crawlers, não um: a config certa para a Gold (várias subpastas = várias
tabelas) quebra a Silver (uma tabela só, particionada) se aplicada junto —
ver [`docs/evidencia_execucao_aws.md`](docs/evidencia_execucao_aws.md) para o
bug real que isso causou e como foi corrigido.

| Camada | O que faz |
|---|---|
| **Raw** | CSV original, intocado |
| **Bronze** | Parquet particionado por `survey_year`; cabeçalhos normalizados; **nenhuma** coluna descartada, nenhum tipo convertido |
| **Silver** | Uma linha por respondente, schema canônico único entre as 3 edições; valores normalizados; tecnologias colapsadas em `array<string>` |
| **Gold** | 9 tabelas analíticas agregadas, prontas para Athena e para os gráficos |

Diagrama completo: [`architecture/arquitetura_aws.drawio`](architecture/).

---

## Como rodar localmente

O ambiente local espelha o **AWS Glue 5.0** (Python 3.11 + Spark 3.5 + Java 17),
para que o mesmo código PySpark rode nos dois lugares sem alteração.

**Pré-requisitos** (macOS com Homebrew):

```bash
brew install openjdk@17 python@3.11
```

Em Linux (Debian/Ubuntu), o equivalente é:

```bash
sudo apt-get install openjdk-17-jdk python3.11 python3.11-venv
```

**Instalação:**

```bash
python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

**Execução completa** — bronze → silver → gold → gráficos → deck:

```bash
bash scripts/rodar_local.sh
```

Ou etapa a etapa:

```bash
source env.sh
python src/glue_jobs/job_bronze.py --raw_path data/raw    --bronze_path data/bronze
python src/glue_jobs/job_silver.py --bronze_path data/bronze --silver_path data/silver
python src/glue_jobs/job_gold.py   --silver_path data/silver --gold_path data/gold
python src/gerar_diagrama.py
python src/gerar_graficos.py
python src/gerar_apresentacao.py
```

Os mesmos 3 Glue Jobs também estão em [`notebooks/`](notebooks/) como
`.ipynb` (gerados a partir do `.py` com [jupytext](https://jupytext.readthedocs.io/),
já executados uma vez contra os dados reais — a saída de cada célula é a
saída de verdade, não simulada). O `.py` continua sendo o que roda no Glue;
o notebook é a mesma lógica em formato de leitura passo a passo.

---

## Como subir na AWS (Academy Lab)

Copie as credenciais temporárias do Learner Lab (**AWS Details → AWS CLI**) para
`~/.aws/credentials` e então:

```bash
source scripts/00_configurar.sh
bash scripts/01_provisionar.sh
bash scripts/02_criar_jobs.sh
bash scripts/03_executar_pipeline.sh
bash scripts/04_criar_crawler.sh
python3 scripts/05_verificar_athena.py
```

O último passo roda as 28 consultas de [`sql/02_consultas_analiticas.sql`](sql/)
direto contra o Athena e confirma o status de cada uma — é a forma
reproduzível de reverificar o pipeline depois de qualquer mudança na Silver
ou na Gold (ver `docs/evidencia_execucao_aws.md` para o resultado real).
Se o Crawler não rodar por limitação de role, [`sql/01_ddl_athena.sql`](sql/)
cria as tabelas explicitamente.

**Importante — a coluna `survey_year` da tabela `silver` fica como `VARCHAR`**,
não `INT`, porque o Crawler infere o tipo de coluna de partição a partir do
nome da pasta (`survey_year=2025/`) como texto. As consultas em
`sql/02_consultas_analiticas.sql` já foram escritas considerando isso — a
tabela `silver` compara com `survey_year = '2025'` (aspas), as tabelas
`gold_*` comparam com `survey_year = 2025` (sem aspas, ali é coluna comum
dentro do Parquet, tipada certo). Isso foi confirmado rodando de verdade —
ver [`docs/evidencia_execucao_aws.md`](docs/evidencia_execucao_aws.md).

**Para gerar os gráficos e o deck com os dados que rodaram na AWS** (em vez
dos gerados localmente), sincronize a Gold de volta para a sua máquina — não
tente rodar `gerar_graficos.py`/`gerar_apresentacao.py` dentro do shell do
lab, porque o Python do lab não tem `matplotlib`/`python-pptx` instalados e
essa instalação não sobrevive ao fim da sessão:

```bash
aws s3 sync "s3://${TC3_BUCKET}/gold" data/gold
source env.sh
python src/gerar_graficos.py
python src/gerar_apresentacao.py
```

> As credenciais do Academy Lab expiram em ~4h. Quando os comandos retornarem
> `ExpiredToken`, copie o bloco novamente. Sessões novas do lab também
> provisionam um bucket novo do zero — não há como "continuar" de onde uma
> sessão anterior parou; rode `01_provisionar.sh` em diante outra vez.

---

## Estrutura

```
├── architecture/
│   └── arquitetura_aws.drawio      Diagrama editável (entregável 2)
├── data/
│   ├── raw/                        CSVs do Kaggle (você baixa)
│   └── bronze|silver|gold/         Gerados pelo pipeline
├── output/
│   ├── charts/                     12 gráficos + diagrama em PNG
│   └── ...Material_Executivo.pptx  Deck (entregável 1)
├── scripts/                        Deploy e execução na AWS
├── sql/
│   ├── 01_ddl_athena.sql           DDL do Glue Data Catalog
│   └── 02_consultas_analiticas.sql 28 consultas por pergunta de negócio
├── src/
│   ├── schema_utils.py             Normalização de cabeçalhos
│   ├── mappings.py                 Schema canônico e regras de harmonização
│   ├── glue_jobs/                  job_bronze · job_silver · job_gold
│   ├── viz_style.py                Sistema visual dos gráficos
│   ├── gerar_graficos.py           12 gráficos a partir da Gold
│   ├── gerar_diagrama.py           Diagrama em PNG
│   └── gerar_apresentacao.py       Deck executivo
└── tests/
    ├── gerar_dados_sinteticos.py   Fixture que simula as divergências entre edições
    └── validar_sql.py              Executa as 28 consultas contra o Data Lake local
```

---

## Rigor analítico aplicado

- **Mediana além da média.** A distribuição salarial é assimétrica à direita; a
  média sozinha superestima o salário típico.
- **Média onde a mediana cega.** As faixas salariais da pesquisa são largas: a
  mediana de *todas* as regiões cai na mesma faixa. Nos cortes regionais usa-se
  a média, e o gráfico diz isso.
- **Corte de amostra mínima.** Recortes com menos de 30 respondentes são
  marcados `amostra_suficiente = false` — sinalizados, não descartados em
  silêncio.
- **Ausência nunca vira zero.** Quem pulou um bloco do questionário sai do
  denominador. Sem isso, a adoção de Power BI apareceria como 35% em vez dos
  59% reais.
- **Sem remuneração ≠ remuneração zero.** Desempregados e estudantes saem das
  estatísticas salariais.
- **Nenhum número digitado à mão no deck.** Todo valor citado nos títulos e
  recomendações é lido da camada Gold em tempo de geração.

---

## Verificação

```bash
# Gera um fixture que reproduz as divergências entre edições e roda o pipeline
python tests/gerar_dados_sinteticos.py --destino /tmp/tc3/raw

# Executa as 28 consultas analíticas contra o Data Lake local
python tests/validar_sql.py --gold data/gold --silver data/silver
```

`validar_sql.py` roda as consultas no Spark SQL, que compartilha quase toda a
sintaxe com o Trino do Athena. As poucas construções exclusivas do Trino
(`CROSS JOIN UNNEST`) são traduzidas antes da execução e **reportadas**.

Isso já foi além de simulação: **as 28 consultas foram executadas de verdade
no Athena** via `aws athena start-query-execution` (Trino real, não Spark) —
28 SUCCEEDED, 0 falhas, incluindo a consulta com `UNNEST`. Detalhes e run IDs
em [`docs/evidencia_execucao_aws.md`](docs/evidencia_execucao_aws.md).

---

## Principais achados

| Achado | Número |
|---|---|
| Prêmio de senioridade — o maior retorno da carreira | Sênior ganha **4,0x** o Júnior |
| Salário de Júnior e Pleno, nas 3 edições | **parado** (perda real com inflação) |
| Adoção de IA generativa pelos profissionais | **80% → 98%** (n=2.105 na última edição) |
| Respondentes do bloco organizacional que relatam que a empresa prioriza IA | **62%** (n=638) — bloco diferente do de uso pessoal, sem respondentes em comum |
| Respondentes do bloco organizacional que relatam resultado real com IA generativa (não só uso) | **26%** — 38% ainda em piloto sem retorno |
| Participação feminina | **caiu** de 24,4% para 21,9% |
| Gap salarial de gênero | inexistente na base, **-28,6%** no Sênior |
| Gap regional Nordeste vs. Sudeste, controlado por senioridade | **-14%** no Júnior, **some** no Sênior |
| Trabalho remoto | recuando: 46% → 40% |

---

## Limitações

A pesquisa é respondida por voluntários da comunidade Data Hackers — é uma
amostra **autosselecionada**, que sobre-representa profissionais engajados e a
região Sudeste. Não é uma amostra probabilística do mercado brasileiro. A base
também encolhe entre edições (5.293 → 3.495), então comparações entre anos são
sempre de proporção, nunca de volume absoluto.

**Fonte:** State of Data Brasil — Data Hackers + Bain & Company.
