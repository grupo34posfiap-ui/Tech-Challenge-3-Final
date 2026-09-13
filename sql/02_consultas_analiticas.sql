-- ===========================================================================
-- Tech Challenge Fase 3 — Consultas analíticas (Amazon Athena / Trino)
-- ===========================================================================
--
-- Cada bloco responde diretamente a uma das perguntas de negócio do
-- enunciado. As consultas rodam sobre a camada Silver (grão de respondente,
-- máxima flexibilidade) ou Gold (agregado, leitura barata) conforme o caso.
--
-- Convenções aplicadas em todo o arquivo:
--   * mediana (approx_percentile 0.5) além da média — a distribuição salarial
--     é assimétrica à direita e a média sozinha engana;
--   * recortes com menos de 30 respondentes são filtrados ou sinalizados;
--   * respondentes sem salário informado ficam fora das estatísticas de
--     remuneração, nunca são tratados como zero.
--
-- ARMADILHA DE TIPO — confirmada rodando de verdade no Athena: o Glue Crawler
-- tipa `survey_year` como VARCHAR em `state_of_data.silver` (é coluna de
-- PARTIÇÃO ali, e o Crawler infere partição pelo nome da pasta como string).
-- Nas tabelas `gold_*`, `survey_year` é uma coluna comum dentro do Parquet
-- (não é partição), e o Crawler lê o tipo certo do schema do arquivo — int.
-- Por isso: `state_of_data.silver` compara com `survey_year = '2025'`
-- (aspas), e todo `gold_*` compara com `survey_year = 2025` (sem aspas). Ver
-- docs/evidencia_execucao_aws.md para o erro real que motivou isso
-- (TYPE_MISMATCH: Cannot apply operator: varchar = integer).
-- ===========================================================================


-- ###########################################################################
-- P1. COMO ESTÁ ESTRUTURADO O MERCADO BRASILEIRO DE DADOS?
-- ###########################################################################

-- 1.1 — Retrato geral de cada edição: tamanho da amostra e indicadores-chave
SELECT
    survey_year                         AS ano,
    total_respondentes,
    idade_media,
    salario_mediano_geral,
    pct_mulheres,
    pct_remoto,
    pct_hibrido,
    pct_presencial,
    pct_usa_ia_generativa
FROM state_of_data.gold_evolucao_anual
ORDER BY survey_year;


-- 1.2 — Composição por família de carreira: quem forma o mercado
SELECT
    cargo,
    SUM(CASE WHEN survey_year = 2023 THEN respondentes ELSE 0 END) AS resp_2023,
    SUM(CASE WHEN survey_year = 2024 THEN respondentes ELSE 0 END) AS resp_2024,
    SUM(CASE WHEN survey_year = 2025 THEN respondentes ELSE 0 END) AS resp_2025,
    ROUND(SUM(CASE WHEN survey_year = 2025 THEN pct_do_ano ELSE 0 END), 2)
        AS pct_mercado_2025
FROM state_of_data.gold_perfil_mercado
WHERE cargo IS NOT NULL
GROUP BY cargo
ORDER BY resp_2025 DESC;


-- 1.3 — Pirâmide de senioridade: o mercado é maduro ou concentrado na base?
SELECT
    survey_year                                             AS ano,
    senioridade,
    COUNT(*)                                                AS respondentes,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY survey_year), 2)
        AS pct_do_ano
FROM state_of_data.silver
WHERE senioridade IN ('Júnior', 'Pleno', 'Sênior', 'Liderança')
GROUP BY survey_year, senioridade
ORDER BY survey_year,
         CASE senioridade
             WHEN 'Júnior' THEN 1 WHEN 'Pleno' THEN 2
             WHEN 'Sênior' THEN 3 ELSE 4
         END;


-- 1.4 — Concentração geográfica: o mercado é nacional ou paulista?
SELECT
    survey_year                                             AS ano,
    regiao,
    COUNT(*)                                                AS respondentes,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY survey_year), 2)
        AS pct_do_ano,
    ROUND(approx_percentile(salario_medio_mensal, 0.5), 2)  AS salario_mediano
FROM state_of_data.silver
WHERE regiao IS NOT NULL AND regiao <> 'Não informado'
GROUP BY survey_year, regiao
ORDER BY survey_year, respondentes DESC;


-- ###########################################################################
-- P2. QUAIS PERFIS PROFISSIONAIS SÃO MAIS VALORIZADOS PELO MERCADO?
-- ###########################################################################

-- 2.1 — Ranking salarial por família de carreira (edição mais recente)
SELECT
    categoria                   AS cargo,
    respondentes,
    salario_mediano,
    salario_p25,
    salario_p75,
    ROUND(salario_p75 - salario_p25, 2) AS amplitude_interquartil
FROM state_of_data.gold_remuneracao
WHERE dimensao = 'cargo'
  AND survey_year = 2025
  AND amostra_suficiente
ORDER BY salario_mediano DESC;


-- 2.2 — Prêmio de senioridade: quanto o mercado paga para subir de nível
WITH por_nivel AS (
    SELECT
        survey_year,
        senioridade,
        approx_percentile(salario_medio_mensal, 0.5) AS mediana
    FROM state_of_data.silver
    WHERE salario_medio_mensal IS NOT NULL
      AND senioridade IN ('Júnior', 'Pleno', 'Sênior', 'Liderança')
    GROUP BY survey_year, senioridade
    HAVING COUNT(*) >= 30
)
SELECT
    survey_year AS ano,
    senioridade,
    ROUND(mediana, 2) AS salario_mediano,
    ROUND(
        100.0 * (mediana - FIRST_VALUE(mediana) OVER (
            PARTITION BY survey_year
            ORDER BY CASE senioridade
                WHEN 'Júnior' THEN 1 WHEN 'Pleno' THEN 2
                WHEN 'Sênior' THEN 3 ELSE 4 END
        )) / FIRST_VALUE(mediana) OVER (
            PARTITION BY survey_year
            ORDER BY CASE senioridade
                WHEN 'Júnior' THEN 1 WHEN 'Pleno' THEN 2
                WHEN 'Sênior' THEN 3 ELSE 4 END
        ), 1
    ) AS premio_vs_junior_pct
FROM por_nivel
ORDER BY survey_year,
         CASE senioridade
             WHEN 'Júnior' THEN 1 WHEN 'Pleno' THEN 2
             WHEN 'Sênior' THEN 3 ELSE 4
         END;


-- 2.3 — Cargo × senioridade: onde estão os salários mais altos do mercado
SELECT
    cargo,
    senioridade,
    respondentes,
    salario_mediano
FROM state_of_data.gold_perfil_mercado
WHERE survey_year = 2025
  AND amostra_suficiente
  AND salario_mediano IS NOT NULL
ORDER BY salario_mediano DESC
LIMIT 20;


-- 2.4 — Retorno da formação acadêmica sobre a remuneração
SELECT
    categoria       AS nivel_ensino,
    respondentes,
    salario_mediano
FROM state_of_data.gold_remuneracao
WHERE dimensao = 'nivel_ensino'
  AND survey_year = 2025
  AND amostra_suficiente
ORDER BY salario_mediano DESC;


-- ###########################################################################
-- P3. QUAL É O CENÁRIO DE DIVERSIDADE DE GÊNERO?
-- ###########################################################################

-- 3.1 — Representatividade feminina ao longo das 3 edições
SELECT
    survey_year AS ano,
    genero,
    SUM(respondentes) AS respondentes,
    ROUND(
        100.0 * SUM(respondentes)
        / SUM(SUM(respondentes)) OVER (PARTITION BY survey_year), 2
    ) AS pct
FROM state_of_data.gold_diversidade_genero
GROUP BY survey_year, genero
ORDER BY survey_year, respondentes DESC;


-- 3.2 — O funil: a representatividade feminina cai conforme a senioridade sobe?
SELECT
    senioridade,
    ROUND(MAX(CASE WHEN survey_year = 2023 AND genero = 'Feminino'
                   THEN pct_representatividade END), 2) AS pct_fem_2023,
    ROUND(MAX(CASE WHEN survey_year = 2024 AND genero = 'Feminino'
                   THEN pct_representatividade END), 2) AS pct_fem_2024,
    ROUND(MAX(CASE WHEN survey_year = 2025 AND genero = 'Feminino'
                   THEN pct_representatividade END), 2) AS pct_fem_2025
FROM state_of_data.gold_diversidade_genero
WHERE senioridade IN ('Júnior', 'Pleno', 'Sênior', 'Liderança')
GROUP BY senioridade
ORDER BY CASE senioridade
             WHEN 'Júnior' THEN 1 WHEN 'Pleno' THEN 2
             WHEN 'Sênior' THEN 3 ELSE 4
         END;


-- 3.3 — Gap salarial de gênero, controlado por senioridade
--       Controlar por senioridade separa "diferença de remuneração" de
--       "diferença de composição" — sem isso o gap agregado é inconclusivo.
SELECT
    survey_year         AS ano,
    senioridade,
    genero,
    respondentes,
    salario_mediano,
    gap_salarial_pct
FROM state_of_data.gold_diversidade_genero
WHERE genero IN ('Masculino', 'Feminino')
  AND amostra_suficiente
ORDER BY survey_year, senioridade, genero;


-- ###########################################################################
-- P4. QUAIS TECNOLOGIAS APRESENTAM MAIOR ADOÇÃO?
-- ###########################################################################

-- 4.1 — Top 15 tecnologias da edição mais recente, por categoria
SELECT
    categoria,
    tecnologia,
    usuarios,
    base_respondentes,
    pct_adocao
FROM state_of_data.gold_tecnologias
WHERE survey_year = 2025
ORDER BY categoria, pct_adocao DESC;


-- 4.2 — Quem está ganhando e quem está perdendo espaço (2023 -> 2025)
WITH pivot AS (
    SELECT
        categoria,
        tecnologia,
        MAX(CASE WHEN survey_year = 2023 THEN pct_adocao END) AS pct_2023,
        MAX(CASE WHEN survey_year = 2025 THEN pct_adocao END) AS pct_2025
    FROM state_of_data.gold_tecnologias
    GROUP BY categoria, tecnologia
)
SELECT
    categoria,
    tecnologia,
    pct_2023,
    pct_2025,
    ROUND(pct_2025 - pct_2023, 2) AS variacao_pp
FROM pivot
WHERE pct_2023 IS NOT NULL AND pct_2025 IS NOT NULL
ORDER BY variacao_pp DESC;


-- 4.3 — Prêmio salarial por tecnologia: dominar o quê paga mais?
--       Trabalha direto na Silver, explodindo o array de linguagens.
--
--       ATENÇÃO ao ano: a edição 2025-26 REMOVEU o bloco "linguagens que você
--       usa no dia a dia" do questionário — sobrou apenas "linguagem
--       preferida", que é escolha única. Por isso esta consulta usa 2024, a
--       última edição em que a pergunta existiu. Filtrar por 2025 aqui
--       devolveria zero linhas, e não "nenhum prêmio salarial".
--
--       RESOLUÇÃO DA MEDIANA: salario_medio_mensal é o ponto médio da faixa
--       salarial declarada (a pesquisa é por faixas, não valor livre — ver
--       parse_faixa_salarial em src/mappings.py). Com poucas faixas possíveis
--       no questionário inteiro, é esperado que a mediana de várias
--       linguagens diferentes caia no mesmo ponto médio (o da faixa mais
--       populosa do mercado) — não é um erro de cálculo, é a resolução
--       máxima que um dado em faixas permite.
SELECT
    linguagem,
    COUNT(*)                                                AS profissionais,
    ROUND(approx_percentile(salario_medio_mensal, 0.5), 2)  AS salario_mediano
FROM state_of_data.silver
CROSS JOIN UNNEST(linguagens) AS t (linguagem)
WHERE survey_year = '2024'
  AND salario_medio_mensal IS NOT NULL
GROUP BY linguagem
HAVING COUNT(*) >= 30
ORDER BY salario_mediano DESC;


-- 4.4 — Stack de nuvem: qual provedor domina o mercado brasileiro
SELECT
    survey_year AS ano,
    tecnologia  AS provedor_cloud,
    pct_adocao
FROM state_of_data.gold_tecnologias
WHERE categoria = 'Cloud'
ORDER BY survey_year, pct_adocao DESC;


-- ###########################################################################
-- P5. QUAL É O ÍNDICE DE ADOÇÃO DE IA E SEU IMPACTO?
-- ###########################################################################

-- 5.1 — Curva de adoção de IA generativa: profissional vs. empresa
--       A lacuna é o achado: o profissional adota antes da empresa priorizar.
SELECT
    survey_year               AS ano,
    pct_usa_ia_generativa     AS pct_profissionais_usam,
    pct_empresa_prioriza_ia   AS pct_empresas_priorizam,
    ROUND(pct_usa_ia_generativa - pct_empresa_prioriza_ia, 2)
        AS lacuna_pp_profissional_vs_empresa
FROM state_of_data.gold_evolucao_anual
WHERE pct_usa_ia_generativa IS NOT NULL
ORDER BY survey_year;


-- 5.2 — Adoção de IA por família de carreira (edição mais recente)
SELECT
    cargo,
    SUM(respondentes)                                       AS respondentes,
    ROUND(100.0 * SUM(usam_ia) / NULLIF(SUM(base_uso_pessoal), 0), 2)
        AS pct_uso_pessoal,
    ROUND(100.0 * SUM(empresas_usam_ia) / NULLIF(SUM(base_uso_empresa), 0), 2)
        AS pct_uso_empresa
FROM state_of_data.gold_adocao_ia
WHERE survey_year = 2025
GROUP BY cargo
HAVING SUM(respondentes) >= 30
ORDER BY pct_uso_pessoal DESC;


-- 5.3 — Existe prêmio salarial para quem usa IA generativa?
--       Controlado por senioridade, senão o resultado só refletiria que
--       profissionais mais experientes adotam mais.
SELECT
    senioridade,
    usa_ia_generativa,
    COUNT(*)                                                AS profissionais,
    ROUND(approx_percentile(salario_medio_mensal, 0.5), 2)  AS salario_mediano
FROM state_of_data.silver
WHERE survey_year = '2025'
  AND usa_ia_generativa IS NOT NULL
  AND salario_medio_mensal IS NOT NULL
  AND senioridade IN ('Júnior', 'Pleno', 'Sênior', 'Liderança')
GROUP BY senioridade, usa_ia_generativa
HAVING COUNT(*) >= 30
ORDER BY senioridade, usa_ia_generativa;


-- 5.4 — Como a IA é consumida: quem paga a conta?
--       Distingue uso gratuito, custeado pelo profissional e custeado pela
--       empresa. Uso pago do próprio bolso é sinal de ferramenta não
--       homologada circulando dado corporativo — relevante para o cliente.
SELECT
    survey_year AS ano,
    tipo_uso_ia,
    COUNT(*)    AS respondentes,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY survey_year), 2)
        AS pct
FROM state_of_data.silver
WHERE tipo_uso_ia IS NOT NULL
GROUP BY survey_year, tipo_uso_ia
ORDER BY survey_year, respondentes DESC;


-- 5.5 — A empresa está obtendo resultado com LLMs? (adoção ≠ impacto)
--       Responde à parte do enunciado que a adoção sozinha não cobre:
--       "índice de adoção de IA E SEU IMPACTO". Pergunta exclusiva da edição
--       2025-26 — a adoção já saturou, e o que passa a diferenciar empresas
--       é resultado obtido, não uso.
SELECT
    resultado_ia_empresa,
    respondentes,
    pct
FROM state_of_data.gold_impacto_ia
WHERE survey_year = 2025
ORDER BY respondentes DESC;


-- ###########################################################################
-- P6. DIFERENÇAS ENTRE REGIÕES, SENIORIDADES E MODELOS DE TRABALHO
-- ###########################################################################

-- 6.1 — Evolução dos modelos de trabalho: o remoto recuou?
SELECT
    survey_year AS ano,
    pct_remoto,
    pct_hibrido,
    pct_presencial
FROM state_of_data.gold_evolucao_anual
ORDER BY survey_year;


-- 6.2 — Modelo de trabalho por região: o remoto é o que interioriza o mercado?
SELECT
    regiao,
    modelo_trabalho,
    ROUND(MAX(CASE WHEN survey_year = 2023 THEN pct_na_regiao END), 2) AS pct_2023,
    ROUND(MAX(CASE WHEN survey_year = 2025 THEN pct_na_regiao END), 2) AS pct_2025
FROM state_of_data.gold_modelo_trabalho
WHERE regiao <> 'Não informado'
GROUP BY regiao, modelo_trabalho
ORDER BY regiao, modelo_trabalho;


-- 6.3 — Salário mediano por região e modelo de trabalho
--       Responde à pergunta prática: contratar remoto no Nordeste custa menos?
SELECT
    regiao,
    modelo_trabalho,
    respondentes,
    salario_mediano
FROM state_of_data.gold_modelo_trabalho
WHERE survey_year = 2025
  AND amostra_suficiente
  AND regiao <> 'Não informado'
ORDER BY regiao, salario_mediano DESC;


-- 6.4 — Custo relativo por região, CONTROLADO POR SENIORIDADE
--
--       A comparação ingênua (todo mundo de uma região contra a outra) mistura
--       duas coisas: diferença de mercado regional e diferença de COMPOSIÇÃO.
--       O Sudeste concentra bem mais Especialista/Staff+ que o Nordeste
--       (15,8% vs. 6,4% em 2025) — sozinho, isso já infla a média bruta do
--       Sudeste sem dizer nada sobre quanto custa contratar um Sênior
--       especificamente em cada lugar. Comparar dentro do mesmo nível de
--       senioridade isola o efeito regional do efeito de composição.
--
--       Use esta consulta, não uma comparação de médias brutas por região,
--       para qualquer alegação de "contratar em X custa Y% menos".
SELECT
    regiao,
    senioridade,
    respondentes,
    salario_medio,
    ROUND(
        100.0 * salario_medio
        / MAX(CASE WHEN regiao = 'Sudeste' THEN salario_medio END)
            OVER (PARTITION BY senioridade),
        1
    ) AS indice_vs_sudeste_mesma_senioridade,
    amostra_suficiente
FROM state_of_data.gold_remuneracao_regional
WHERE survey_year = 2025
  AND regiao IN ('Nordeste', 'Sudeste')
ORDER BY senioridade,
         CASE senioridade
             WHEN 'Júnior' THEN 1 WHEN 'Pleno' THEN 2
             WHEN 'Sênior' THEN 3 ELSE 4
         END,
         regiao;


-- ###########################################################################
-- P7. OPORTUNIDADES E DESAFIOS PARA QUEM QUER INVESTIR EM DADOS E IA
-- ###########################################################################

-- 7.1 — Risco de turnover: quem está buscando recolocação
SELECT
    senioridade,
    COUNT(*)                                                        AS respondentes,
    ROUND(100.0 * SUM(CASE WHEN busca_nova_oportunidade THEN 1 ELSE 0 END)
          / COUNT(*), 2)                                            AS pct_buscando
FROM state_of_data.silver
WHERE survey_year = '2025'
  AND busca_nova_oportunidade IS NOT NULL
  AND senioridade IN ('Júnior', 'Pleno', 'Sênior', 'Liderança')
GROUP BY senioridade
ORDER BY pct_buscando DESC;


-- 7.2 — Escassez relativa: razão sênior/júnior por família de carreira
--       Razão alta = talento maduro escasso e caro de contratar.
WITH niveis AS (
    SELECT
        cargo,
        SUM(CASE WHEN senioridade = 'Júnior' THEN respondentes ELSE 0 END) AS juniores,
        SUM(CASE WHEN senioridade = 'Sênior' THEN respondentes ELSE 0 END) AS seniores
    FROM state_of_data.gold_perfil_mercado
    WHERE survey_year = 2025
    GROUP BY cargo
)
SELECT
    cargo,
    juniores,
    seniores,
    ROUND(1.0 * seniores / NULLIF(juniores, 0), 2) AS razao_senior_junior
FROM niveis
WHERE juniores + seniores >= 30
ORDER BY razao_senior_junior DESC;


-- 7.3 — Setor financeiro vs. demais setores: o benchmark do nosso cliente
SELECT
    CASE
        WHEN LOWER(setor_empresa) LIKE '%financ%'
          OR LOWER(setor_empresa) LIKE '%banco%'
          OR LOWER(setor_empresa) LIKE '%seguro%' THEN 'Setor Financeiro'
        ELSE 'Demais setores'
    END                                                     AS grupo_setor,
    COUNT(*)                                                AS respondentes,
    ROUND(approx_percentile(salario_medio_mensal, 0.5), 2)  AS salario_mediano,
    ROUND(100.0 * AVG(CASE WHEN usa_ia_generativa THEN 1.0 ELSE 0.0 END), 2)
        AS pct_usa_ia,
    ROUND(100.0 * AVG(CASE WHEN modelo_trabalho = 'Remoto' THEN 1.0 ELSE 0.0 END), 2)
        AS pct_remoto
FROM state_of_data.silver
WHERE survey_year = '2025'
  AND setor_empresa IS NOT NULL
GROUP BY 1
ORDER BY salario_mediano DESC;


-- 7.4 — Onde contratar sênior gastando menos: região × cargo
SELECT
    regiao,
    cargo,
    COUNT(*)                                                AS disponibilidade,
    ROUND(approx_percentile(salario_medio_mensal, 0.5), 2)  AS salario_mediano
FROM state_of_data.silver
WHERE survey_year = '2025'
  AND senioridade = 'Sênior'
  AND salario_medio_mensal IS NOT NULL
  AND regiao <> 'Não informado'
GROUP BY regiao, cargo
HAVING COUNT(*) >= 30
ORDER BY salario_mediano ASC;
