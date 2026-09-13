# Execução das 28 consultas — verificação atual

Rodado via `python3 scripts/05_verificar_athena.py` contra o Athena real (banco `state_of_data`).

| Consulta | Status | Query Execution ID |
|---|---|---|
| 1.1 — Retrato geral de cada edição: tamanho da amostra e indicadores-chave | SUCCEEDED | `0db061ee-bca7-44a4-893d-fba984c1f350` |
| 1.2 — Composição por família de carreira: quem forma o mercado | SUCCEEDED | `e39db25c-36bb-4324-b35e-80f0cbcadf20` |
| 1.3 — Pirâmide de senioridade: o mercado é maduro ou concentrado na base? | SUCCEEDED | `64f03d20-b671-4fe0-a740-05661e87f609` |
| 1.4 — Concentração geográfica: o mercado é nacional ou paulista? | SUCCEEDED | `99fd51e8-ae19-4da8-9c95-5ccd5160fc5e` |
| 2.1 — Ranking salarial por família de carreira (edição mais recente) | SUCCEEDED | `e4ceed01-2dc7-4766-bb01-95433d9a439e` |
| 2.2 — Prêmio de senioridade: quanto o mercado paga para subir de nível | SUCCEEDED | `e0f1d985-9ade-4253-b7a9-ae8beee91b97` |
| 2.3 — Cargo × senioridade: onde estão os salários mais altos do mercado | SUCCEEDED | `00784f25-8dcd-496c-aea2-2fdb15a40ba7` |
| 2.4 — Retorno da formação acadêmica sobre a remuneração | SUCCEEDED | `ec78b17f-9d66-4bd9-96ea-ec26e16737fe` |
| 3.1 — Representatividade feminina ao longo das 3 edições | SUCCEEDED | `1e934113-fed1-40db-800c-807c4e9cc4c3` |
| 3.2 — O funil: a representatividade feminina cai conforme a senioridade sobe? | SUCCEEDED | `ae5ab25f-5b1e-4080-bc03-13af94841ba1` |
| 3.3 — Gap salarial de gênero, controlado por senioridade | SUCCEEDED | `d0ea6c51-9e66-4f2d-9caf-ee39f755f3de` |
| 4.1 — Top 15 tecnologias da edição mais recente, por categoria | SUCCEEDED | `6424a205-f16c-4933-8c05-ed0b9d993544` |
| 4.2 — Quem está ganhando e quem está perdendo espaço (2023 -> 2025) | SUCCEEDED | `9e1d080b-1e72-4bea-92c9-e2e996638382` |
| 4.3 — Prêmio salarial por tecnologia: dominar o quê paga mais? | SUCCEEDED | `4f2f4247-0e02-49cd-888e-fe0c9bcd0b76` |
| 4.4 — Stack de nuvem: qual provedor domina o mercado brasileiro | SUCCEEDED | `4a942fcf-9a51-4ba2-bd3b-70adbca6f844` |
| 5.1 — Curva de adoção de IA generativa: profissional vs. empresa | SUCCEEDED | `88ca54c4-2e03-4ea8-8c77-f62182f4e7ff` |
| 5.2 — Adoção de IA por família de carreira (edição mais recente) | SUCCEEDED | `786d60ee-0e47-44c5-9f0d-fe963fa88a87` |
| 5.3 — Existe prêmio salarial para quem usa IA generativa? | SUCCEEDED | `e22d5e7b-1120-41ec-991d-94be448d537c` |
| 5.4 — Como a IA é consumida: quem paga a conta? | SUCCEEDED | `64dfaca8-e5b7-4c40-8fcc-d76ea49c9a8a` |
| 5.5 — A empresa está obtendo resultado com LLMs? (adoção ≠ impacto) | SUCCEEDED | `9b6656e6-ddf4-48b5-993f-0502e9965788` |
| 6.1 — Evolução dos modelos de trabalho: o remoto recuou? | SUCCEEDED | `b69d8f33-fee0-48cb-a406-ca2a1fb36b68` |
| 6.2 — Modelo de trabalho por região: o remoto é o que interioriza o mercado? | SUCCEEDED | `c029e5d3-313a-442d-a5cc-7580e13f5f8e` |
| 6.3 — Salário mediano por região e modelo de trabalho | SUCCEEDED | `fbbac347-7189-401f-9541-5c3cbc86fe68` |
| 6.4 — Custo relativo por região, CONTROLADO POR SENIORIDADE | SUCCEEDED | `2116d344-4b0e-493e-ab25-f75896fe8cfc` |
| 7.1 — Risco de turnover: quem está buscando recolocação | SUCCEEDED | `8c2b90d0-f456-4cfb-9426-c30f4307de07` |
| 7.2 — Escassez relativa: razão sênior/júnior por família de carreira | SUCCEEDED | `d28270f4-2be0-4237-ae78-25eb8f4492f9` |
| 7.3 — Setor financeiro vs. demais setores: o benchmark do nosso cliente | SUCCEEDED | `a9a39fb6-e2f8-4537-abf9-e14530b36f18` |
| 7.4 — Onde contratar sênior gastando menos: região × cargo | SUCCEEDED | `26e7c609-69ed-4297-9e92-3fa1d13a9907` |

**Resultado: 28/28 SUCCEEDED, 0 falhas.**
