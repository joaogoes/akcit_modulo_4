# Escopo do MVP – Dashboard de Atividades por Fase de Projeto

## 1. Objetivo

Fornecer um dashboard que consolide, por fase de projeto e por veredito, o total de features registradas em relatórios `*.md` armazenados em repositórios GitHub. Os repositórios são cadastrados pelo usuário em tempo de execução.

O MVP responde a uma pergunta: **quantas features estão em cada veredito, em cada fase, nos repositórios selecionados?**

## 2. Contexto

Cada repositório segue uma estrutura de pastas por fase. Dentro de cada pasta há um subdiretório por feature, que contém os relatórios.

| Fase | Caminho dos relatórios |
|---|---|
| Requirements | `200 Requirements\230 Output\<feature>\reports\req-validation` |
| FSpec | `300 Specs\320 F-Specs\Output\<feature>\reports\fspec-validation` |
| DSpec | `300 Specs\330 D-Specs\Output\<feature>\reports\dspec-validation` |
| Code | `400 Code\Output\<feature>\reports\code-validation` |
| Tests | `500 Tests\Output\<feature>\reports\code-tests` |

Cada relatório contém dois campos, lidos do conteúdo do arquivo:

- `generated: <data do relatório>`
- `verdict: <resultado>`

## 3. Requisitos funcionais

### 3.1 Gestão de repositórios

- **RF-01** O usuário cadastra um repositório GitHub em tempo de execução, informando `owner/repo` e, quando necessário, branch. URL completa do GitHub é aceita e normalizada para `owner/repo` (a partir da Release 2).
- **RF-02** O usuário lista e remove repositórios cadastrados.
- **RF-03** O sistema valida o cadastro: o repositório deve existir e ser acessível com as credenciais configuradas. Em caso de falha, exibe mensagem de erro específica (não encontrado, sem permissão, limite de requisições).
- **RF-04** O cadastro é gravado no banco de dados e persiste entre sessões e reinícios da aplicação.

### 3.2 Coleta e interpretação dos relatórios

- **RF-05** Para cada repositório, o sistema lê as cinco pastas de fase definidas na seção 2 e identifica as features a partir do nome do subdiretório `<feature>`.
- **RF-06** O sistema considera apenas arquivos `*.md` localizados diretamente na pasta de relatórios de cada fase. Subpastas não são percorridas.
- **RF-07** O sistema extrai de cada relatório os campos `generated` e `verdict`. Um relatório é **válido** quando possui `verdict` não vazio e `generated` interpretável como data.
- **RF-08** Se uma feature tiver mais de um relatório válido na mesma fase, vale o de `generated` mais recente. Com isso, cada feature tem no máximo um veredito por fase.
- **RF-09** Relatório inválido (sem `verdict` ou com `generated` ilegível) é sinalizado ao usuário e não interrompe o processamento dos demais. A feature só é contabilizada na categoria "Inválido" quando **todos** os seus relatórios naquela fase forem inválidos; se houver ao menos um válido, aplica-se RF-08 sobre os válidos.
- **RF-10** Fase ou pasta inexistente em um repositório conta como zero features nessa fase. Não é erro.
- **RF-10a** A unidade de contagem é o par (repositório, feature, fase). Features de mesmo nome em repositórios diferentes são contadas separadamente.
- **RF-11** O usuário aciona a atualização dos dados sob demanda, para todos os repositórios ou para um específico. Cada coleta substitui os relatórios armazenados do repositório coletado de forma **atômica**: os novos dados são gravados em uma única transação, que só é confirmada se a coleta do repositório terminar com sucesso. O sistema exibe a data/hora e o status da última coleta de cada repositório. Uma coleta que falha, total ou parcialmente no meio da gravação, preserva os dados da coleta anterior.

### 3.3 Dashboard

- **RF-12** O dashboard exibe um gráfico de barras **empilhadas horizontalmente**. Cada barra representa uma fase, na ordem Requirements → FSpec → DSpec → Code → Tests.
- **RF-13** Os segmentos de cada barra representam os vereditos. O comprimento de cada segmento é o total de features naquele veredito.
- **RF-14** Cada veredito tem cor fixa e consistente entre as barras. Existe uma legenda.
- **RF-15** O valor absoluto de cada segmento é visível, no rótulo ou em tooltip.
- **RF-16** O gráfico agrega os dados de todos os repositórios cadastrados. O usuário pode filtrar por um ou mais repositórios.
- **RF-17** A lista de vereditos é derivada dos valores encontrados nos relatórios. O sistema não depende de um conjunto fixo de valores. O rótulo "Inválido" é reservado ao sistema (RF-09) e exibido sempre como último segmento da barra.
- **RF-18** Normalização de vereditos: comparação sem diferenciar maiúsculas/minúsculas e sem espaços nas extremidades. O rótulo exibido é a primeira grafia encontrada.

## 4. Requisitos não funcionais

- **RNF-01 Acesso ao GitHub:** leitura via API do GitHub (REST ou GraphQL). Autenticação por Personal Access Token com escopo mínimo de leitura (`repo:read` / `contents:read`), configurado fora do código-fonte (variável de ambiente ou arquivo de configuração local).
- **RNF-02 Segurança:** o token nunca é exibido na interface, nem gravado em logs ou no repositório de código da aplicação. Operações exclusivamente de leitura nos repositórios consultados.
- **RNF-03 Desempenho:** a coleta de até 10 repositórios, com até 200 relatórios cada, termina em até 60 s em rede corporativa típica. A coleta usa requisições em paralelo, respeitando o limite de taxa da API. Para caber no limite de 5.000 requisições/hora da API REST com token, a descoberta de arquivos usa a API de árvore do Git (uma chamada por repositório, em modo recursivo) e a leitura de conteúdo usa requisições condicionais (`ETag`/`If-None-Match`), que não consomem cota quando o arquivo não mudou. A viabilidade dessa estratégia é validada em protótipo antes da implementação (seção 8, R-01). A medição usa um repositório sintético com a carga do requisito (RNF-12).
- **RNF-04 Resiliência:** a falha de um repositório ou arquivo não impede a exibição dos demais. Os erros são reportados por repositório.
- **RNF-05 Limite de taxa:** o sistema detecta resposta de rate limit, informa o usuário e indica quando tentar novamente.
- **RNF-06 Persistência dos resultados:** os resultados da coleta são gravados no banco de dados. O dashboard lê do banco; a reabertura do dashboard não dispara nova coleta.
- **RNF-07 Banco de dados:** banco relacional acessado via ORM (SQLAlchemy) com migrações (Alembic a partir da Release 2; na Release 1 o esquema é criado diretamente pelo ORM). SQLite é o banco padrão do MVP; a troca por PostgreSQL deve exigir apenas mudança de string de conexão. O banco armazena no mínimo: repositórios cadastrados; relatórios coletados (repositório, fase, feature, caminho, `generated`, `verdict`, validade); e execuções de coleta (início, fim, status, erros).
- **RNF-08 Plataforma:** aplicação web em Python 3.11+, com framework web (FastAPI ou Flask) e interface servida no navegador. O gráfico é renderizado no cliente com biblioteca JavaScript de gráficos (ex.: Chart.js ou Plotly). Ambiente de referência: Windows 11, execução local; as dependências são declaradas em `requirements.txt` ou `pyproject.toml`.
- **RNF-09 Usabilidade:** o dashboard é legível a partir de 1280 px de largura. As cores dos vereditos atendem contraste mínimo WCAG AA.
- **RNF-10 Observabilidade:** log de coleta com repositório, número de arquivos lidos, número de erros e duração.
- **RNF-11 Testabilidade:** o parser de relatórios (`generated`/`verdict`) é isolado da camada de acesso ao GitHub e da camada de persistência, para teste unitário com fixtures de relatórios (`pytest`). A agregação do dashboard é testável contra um banco SQLite em memória.
- **RNF-12 Fixtures e dados de teste:**
  - Repositório (ou pasta) de fixtures versionado no projeto, com a estrutura das 5 fases e **contagem esperada por fase e veredito documentada**. É a base do critério de aceite 2.
  - Fixtures de relatórios construídas a partir de 3 a 5 relatórios reais (P-01, P-02), mais casos sintéticos: sem `verdict`, sem `generated`, data inválida, veredito com variação de caixa e espaços, duplicatas na mesma fase.
  - Repositório sintético em escala (10 repositórios × 200 relatórios) para medir o RNF-03.
- **RNF-13 Cliente GitHub substituível:** o acesso ao GitHub fica atrás de uma interface (ex.: `GitHubClient` com `list_tree` e `get_file`). Testes usam uma implementação falsa em memória e, para o cliente real, respostas simuladas (404, 403, rate limit, ETag 304).
- **RNF-14 API de dados:** a agregação é exposta por endpoint JSON (ex.: `GET /api/dashboard?repos=...`), separado da página HTML. Os testes validam o JSON, sem navegador.
- **RNF-15 Verificação dos requisitos de qualidade:** o contraste WCAG AA (RNF-09) é verificado por ferramenta automatizada (ex.: cálculo de razão de contraste sobre a paleta de vereditos, em teste); o tempo de coleta (RNF-03) é medido pelo log de coleta (RNF-10) sobre o repositório sintético.

## 5. Premissas e pontos em aberto

| # | Item | Tratamento no MVP |
|---|---|---|
| P-01 | O caminho de Tests foi informado como `<feature>reports\code-tests`, sem separador. | Assume-se `<feature>\reports\code-tests`, por consistência com as demais fases. **Confirmar antes da implementação** (pré-requisito, seção 8, R-02). |
| P-02 | O formato exato dos campos (front matter YAML ou linha no corpo) não foi especificado. | O parser aceita `generated:` e `verdict:` como linhas `chave: valor`, no front matter ou no corpo. Considera-se a primeira ocorrência. **Confirmar antes da implementação**, com 3 a 5 relatórios reais (seção 8, R-02). |
| P-03 | O conjunto de valores de `verdict` não foi definido. | Derivado dos dados (RF-17). |
| P-04 | Formato da data em `generated`. | Aceita ISO 8601, como data (`2026-10-10`) ou data e hora (`2026-10-10T14:30:00Z`). Sem fuso horário, assume-se UTC. Data futura é aceita. Outros formatos tornam o relatório inválido até serem definidos. Esses casos têm teste (RNF-12). |
| P-05 | Repositórios privados. | Suportados via token. Repositórios públicos funcionam sem token, com limite de taxa menor. |
| P-06 | Branch lido. | Branch padrão do repositório, salvo indicação no cadastro. |
| P-07 | Os caminhos da seção 2 usam `\` (notação Windows). | A API do GitHub usa `/`. O sistema normaliza os separadores; nomes de pastas com espaços (`200 Requirements`) são preservados literalmente. |
| P-08 | A ordem dos segmentos de veredito dentro da barra não foi definida. | Regra fixa desde a Release 1: ordem alfabética do rótulo normalizado, com "Inválido" por último. Ordem semântica (ex.: aprovado → reprovado) é melhoria opcional, a confirmar com o patrocinador. |

## 6. Fora de escopo

- Escrita nos repositórios (commits, PRs, issues, comentários).
- Autenticação e autorização de usuários da aplicação, multiusuário, perfis de acesso.
- Evolução temporal: séries históricas, tendências e comparação entre períodos. O campo `generated` é lido, mas só serve para escolher o relatório mais recente.
- Outros tipos de gráfico, drill-down até o conteúdo do relatório, e navegação por feature individual.
- Visualização do conteúdo dos relatórios `.md`.
- Exportação (PDF, imagem, CSV) e impressão.
- Notificações, alertas e agendamento automático de coleta.
- Webhooks do GitHub e atualização em tempo real.
- Provedores que não sejam o GitHub (GitLab, Azure DevOps, Bitbucket).
- Validação de conteúdo ou de qualidade dos relatórios além da extração de `generated` e `verdict`.
- Execução dos pipelines de validação que geram os relatórios.
- Implantação em nuvem, alta disponibilidade e escalabilidade horizontal.
- Migração de dados entre bancos e administração do banco (backup, tuning, replicação).
- Internacionalização. A interface é apenas em português.

## 7. Critérios de aceite do MVP

1. Cadastrar 2 repositórios válidos e 1 inválido: os 2 válidos aparecem no dashboard e o inválido mostra erro específico.
2. O repositório de fixtures (RNF-12), com features e vereditos conhecidos nas 5 fases, gera um gráfico cujos totais coincidem com a contagem esperada documentada. O teste é automatizado sobre o endpoint JSON (RNF-14).
3. Uma feature com 2 relatórios válidos na mesma fase conta uma única vez, com o veredito do relatório mais recente.
4. Uma feature com 1 relatório válido e 1 inválido na mesma fase conta com o veredito do válido; uma feature cujo único relatório é inválido aparece como "Inválido". Em ambos os casos a coleta não é interrompida.
4a. Uma feature de mesmo nome em 2 repositórios conta duas vezes.
5. Remover um repositório atualiza o gráfico sem nova coleta e apaga seus relatórios do banco.
5a. Após reiniciar a aplicação, repositórios cadastrados e o último resultado coletado continuam disponíveis no dashboard.
6. O token do GitHub não aparece em tela, logs ou banco de dados.
7. Uma coleta interrompida no meio da gravação deixa os dados do repositório iguais aos da coleta anterior.

## 8. Riscos técnicos e mitigações

Devem ser tratados antes da implementação (ver "Pré-requisitos" em [02 backlog.md](02%20backlog.md)). Análise completa em [05 revisão de planejamento.md](05%20revis%C3%A3o%20de%20planejamento.md).

| # | Risco | Mitigação |
|---|---|---|
| R-01 | Limite de requisições da API do GitHub: 10 repositórios × 200 relatórios geram milhares de chamadas, contra 5.000/hora com token. | API de árvore do Git (uma chamada por repositório), requisições condicionais com `ETag` e tratamento de rate limit (RNF-05). Protótipo de coleta, medido contra a carga do RNF-03, antes de fixar a arquitetura. |
| R-02 | Formato dos relatórios e dos caminhos diferente do assumido (P-01, P-02, P-07): afeta a descoberta de features e o parser. | Validar o protótipo contra um repositório real e 3 a 5 relatórios reais; registrar o resultado em P-01 e P-02. |
| R-03 | Substituição dos dados a cada coleta deixa o dashboard vazio ou inconsistente se a coleta falhar no meio. | Gravação transacional por repositório (RF-11), com teste de falha injetada (critério de aceite 7). |
