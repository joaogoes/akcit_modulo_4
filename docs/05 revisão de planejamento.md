# Revisão de planejamento – escopo e backlog

Análise de [01 escopo-mvp.md](01%20escopo-mvp.md) e [02 backlog.md](02%20backlog.md). Cada ponto traz a decisão aplicada nos documentos.

## 1. O que está grande demais para a Release 1

| Ponto | Decisão aplicada |
|---|---|
| Banco com Alembic e três tabelas. | Release 1 com SQLite, esquema criado pelo ORM e duas tabelas (repositórios, relatórios). Alembic e a tabela de execuções passam para a Release 2 (RT-R2-01). |
| Cadastro com remoção, URL e `owner/repo`. | Release 1 aceita só `owner/repo` e não remove. Remoção, URL completa e mensagens de erro específicas passam para a Release 2 (RF-R2-01). |
| Cinco fases de uma vez. | Release 1 entrega só Requirements, de ponta a ponta. As fases são linhas de uma tabela de configuração; as outras quatro entram na Release 2 (RF-R2-02) sem nova lógica. |
| Esqueleto web e separação de camadas como itens separados. | Fundidos em RT-R1-03, já com o endpoint JSON. |
| Ordem de veredito só na Release 3, mas o gráfico da Release 1 já precisa dela. | Regra fixa desde a Release 1: alfabética, "Inválido" por último (RF-R1-04). A ordem semântica virou melhoria opcional (RF-R3-01). |

## 2. O que faltava para testabilidade

| Lacuna | Decisão aplicada |
|---|---|
| Sem repositório de fixtures com contagem esperada. | RNF-12 e RT-R0-03: fixtures versionadas com tabela de contagem esperada e casos sintéticos. O critério de aceite 2 passa a ser automatizado. |
| Cliente GitHub sem abstração para troca por um falso. | RNF-13 e RT-R1-01: interface `GitHubClient` com implementação real e falsa. |
| Formato dos campos indefinido (P-01, P-02). | Pré-requisito RT-R0-01: 3 a 5 relatórios reais antes de implementar. |
| Datas sem casos de borda. | P-04 define ISO 8601, UTC por padrão e data futura aceita; RF-R1-03 CA4 e as fixtures cobrem os casos. |
| Sem teste da API do dashboard. | RNF-14 e RT-R1-03: endpoint JSON separado da página; teste sem navegador (RT-R1-04). |
| Desempenho e acessibilidade sem método de medição. | RNF-15: tempo medido pelo log de coleta sobre repositório sintético (RT-R3-01); contraste WCAG calculado em teste (RT-R3-02). |

## 3. Riscos técnicos a mitigar antes da implementação

| # | Risco | Mitigação |
|---|---|---|
| R-01 | Limite de requisições da API do GitHub: 10 repositórios × 200 relatórios geram milhares de chamadas, contra 5.000/hora com token. | API de árvore do Git (uma chamada por repositório), `ETag` e tratamento de rate limit. Protótipo medido antes da implementação (RT-R0-02). |
| R-02 | Formato dos relatórios e dos caminhos diferente do assumido (P-01, P-02, P-07). | Validação contra um repositório real e relatórios reais (RT-R0-01, RT-R0-02). |
| R-03 | Substituição dos dados a cada coleta deixa o dashboard vazio ou inconsistente se a coleta falhar no meio. | Gravação transacional por repositório (RF-11, RT-R1-02), com teste de falha injetada (critério de aceite 7). |

## 4. Registro dos resultados dos pré-requisitos

Preencher ao concluir RT-R0-01 e RT-R0-02.

- [ ] P-01 (caminho de Tests): _pendente_
- [ ] P-02 (formato dos campos): _pendente_
- [ ] Chamadas à API por repositório e extrapolação para 10 × 200: _pendente_
