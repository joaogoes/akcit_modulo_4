# Backlog mínimo – Dashboard de Atividades por Fase

Legenda: **RF** = requisito funcional, **RT** = requisito técnico. A coluna "origem" refere-se aos IDs de [01 escopo-mvp.md](01%20escopo-mvp.md) (RF-xx, RNF-xx, R-xx).
Cada item só é marcado como concluído quando todos os seus critérios de aceite (CA) forem atendidos.
O corte dos releases segue a revisão em [05 revisão de planejamento.md](05%20revis%C3%A3o%20de%20planejamento.md).

## Pré-requisitos (antes da Release 1)

Mitigação dos riscos técnicos R-01, R-02 e R-03. Bloqueiam o início da implementação.

- [ ] **RT-R0-01 – Relatórios e estrutura reais** (origem: R-02, P-01, P-02, P-07)
  - [ ] CA1: 3 a 5 relatórios reais obtidos e versionados como fixtures.
  - [ ] CA2: P-01 (caminho de Tests) e P-02 (front matter ou corpo) confirmados e registrados no escopo.
- [ ] **RT-R0-02 – Protótipo de coleta (spike)** (origem: R-01)
  - [ ] CA1: um script lê a árvore de um repositório real pela API de árvore do Git (1 chamada) e lista features e relatórios de uma fase.
  - [ ] CA2: o número de chamadas à API é medido e extrapolado para 10 repositórios × 200 relatórios; o resultado cabe em 5.000 requisições/hora, ou a estratégia é ajustada (ETag, GraphQL).
  - [ ] CA3: o resultado da medição é registrado em [05 revisão de planejamento.md](05%20revis%C3%A3o%20de%20planejamento.md).
- [ ] **RT-R0-03 – Fixtures com contagem esperada** (origem: RNF-12)
  - [ ] CA1: pasta de fixtures versionada com estrutura das fases e tabela de contagem esperada por fase e veredito.
  - [ ] CA2: casos sintéticos incluídos: sem `verdict`, sem `generated`, data inválida, variação de caixa e espaços, duplicatas na mesma fase.

## Release 1 – Core

Objetivo: **uma fase (Requirements) de ponta a ponta**, do cadastro ao gráfico. As demais fases entram na Release 2, reaproveitando a mesma configuração.

### Requisitos funcionais

- [ ] **RF-R1-01 – Cadastrar repositório** (origem: RF-01, RF-04)
  - [ ] CA1: informar `owner/repo` cria o registro no banco e o exibe na lista.
  - [ ] CA2: após reiniciar a aplicação, os repositórios continuam listados.
- [ ] **RF-R1-02 – Coletar relatórios da fase Requirements** (origem: RF-05, RF-06, RF-10, RF-11)
  - [ ] CA1: a coleta lê a pasta de relatórios de Requirements e identifica a feature pelo subdiretório `<feature>`.
  - [ ] CA2: só `*.md` diretamente na pasta de relatórios são lidos.
  - [ ] CA3: pasta inexistente resulta em zero features, sem erro.
  - [ ] CA4: as fases são definidas por tabela de configuração (nome, caminho, subpasta de relatórios), sem lógica específica por fase.
  - [ ] CA5: a coleta é acionada sob demanda e a data/hora da última coleta é exibida.
- [ ] **RF-R1-03 – Extrair `generated` e `verdict`** (origem: RF-07, RF-08, RF-18, P-04)
  - [ ] CA1: os campos são lidos conforme o formato confirmado em RT-R0-01; vale a primeira ocorrência.
  - [ ] CA2: `verdict` é normalizado (sem diferenciar maiúsculas/minúsculas, sem espaços nas extremidades).
  - [ ] CA3: com mais de um relatório válido para a mesma feature e fase, vale o de `generated` mais recente.
  - [ ] CA4: datas ISO 8601 (data e data/hora, com e sem fuso) são aceitas; sem fuso assume UTC; formato inválido torna o relatório inválido.
- [ ] **RF-R1-04 – Gráfico de barras empilhadas horizontais** (origem: RF-12, RF-13, RF-14, RF-15, RF-17)
  - [ ] CA1: uma barra por fase coletada, na ordem Requirements → FSpec → DSpec → Code → Tests.
  - [ ] CA2: segmentos por veredito, com cor fixa por veredito e legenda.
  - [ ] CA3: ordem dos segmentos fixa: alfabética pelo rótulo normalizado, "Inválido" por último.
  - [ ] CA4: o valor de cada segmento é visível em rótulo ou tooltip.
  - [ ] CA5: os totais coincidem com a contagem esperada das fixtures (RT-R0-03).

### Requisitos técnicos

- [ ] **RT-R1-01 – Acesso ao GitHub atrás de interface** (origem: RNF-01, RNF-02, RNF-13)
  - [ ] CA1: interface `GitHubClient` (`list_tree`, `get_file`) com implementação real e implementação falsa em memória.
  - [ ] CA2: a implementação real usa a API de árvore do Git, conforme validado em RT-R0-02.
  - [ ] CA3: token lido de variável de ambiente; não aparece em tela, logs ou banco.
  - [ ] CA4: nenhuma operação de escrita é feita nos repositórios consultados.
- [ ] **RT-R1-02 – Banco de dados e gravação atômica** (origem: RNF-06, RNF-07, RF-11, R-03)
  - [ ] CA1: `sqlite3` da biblioteca padrão; esquema criado por script SQL idempotente (sem migrações nesta release).
  - [ ] CA2: duas tabelas: repositórios e relatórios (repositório, fase, feature, caminho, `generated`, `verdict`, validade).
  - [ ] CA3: a coleta de um repositório grava em uma única transação; falha injetada no meio da gravação mantém os dados anteriores (teste automatizado).
  - [ ] CA4: o dashboard lê do banco e não dispara coleta ao ser aberto.
- [ ] **RT-R1-03 – Aplicação web em camadas e API de dados** (origem: RNF-08, RNF-11, RNF-14)
  - [ ] CA1: Python 3.11+ com FastAPI ou Flask, executável localmente no Windows 11 com um único comando documentado; dependências declaradas.
  - [ ] CA2: parser, cliente GitHub, persistência e agregação são módulos independentes.
  - [ ] CA3: endpoint JSON (`GET /api/dashboard`) devolve a agregação por fase e veredito; a página consome esse endpoint.
- [ ] **RT-R1-04 – Testes da Release 1** (origem: RNF-11, RNF-12)
  - [ ] CA1: testes unitários do parser com as fixtures de RT-R0-01 e RT-R0-03.
  - [ ] CA2: teste da agregação sobre SQLite em memória, comparando com a contagem esperada.
  - [ ] CA3: teste do endpoint JSON com o cliente GitHub falso.
  - [ ] CA4: todos os testes passam com `pytest`.

## Release 2 – Qualidade

Objetivo: completar as fases e funcionalidades de gestão, e dar robustez e cobertura de testes.

### Requisitos funcionais

- [ ] **RF-R2-01 – Gestão de repositórios completa** (origem: RF-02, RF-03, RF-01)
  - [ ] CA1: remover um repositório apaga o registro e seus relatórios do banco e atualiza o gráfico sem nova coleta.
  - [ ] CA2: repositório inexistente, sem permissão ou acima do limite de requisições gera mensagem de erro específica.
  - [ ] CA3: cadastro inválido não é gravado no banco.
  - [ ] CA4: URL completa do GitHub é aceita e normalizada para `owner/repo`.
- [ ] **RF-R2-02 – Demais fases (FSpec, DSpec, Code, Tests)** (origem: RF-05, RF-10)
  - [ ] CA1: as quatro fases são adicionadas à tabela de configuração, sem nova lógica de coleta.
  - [ ] CA2: as fixtures cobrem as 5 fases e a contagem esperada é atendida.
  - [ ] CA3: o gráfico exibe as 5 barras na ordem definida.
- [ ] **RF-R2-03 – Relatórios inválidos** (origem: RF-09, RF-17)
  - [ ] CA1: relatório sem `verdict` ou com `generated` ilegível é sinalizado ao usuário.
  - [ ] CA2: feature cujos relatórios na fase são todos inválidos aparece como "Inválido".
  - [ ] CA3: feature com ao menos um relatório válido usa o veredito do mais recente entre os válidos.
  - [ ] CA4: relatório inválido não interrompe a coleta dos demais.
- [ ] **RF-R2-04 – Contagem por repositório** (origem: RF-10a)
  - [ ] CA1: feature de mesmo nome em 2 repositórios conta 2 vezes.
- [ ] **RF-R2-05 – Filtro por repositório** (origem: RF-16)
  - [ ] CA1: o gráfico agrega todos os repositórios por padrão.
  - [ ] CA2: o usuário seleciona um ou mais repositórios e o gráfico é recalculado.
- [ ] **RF-R2-06 – Coleta parcial e status** (origem: RF-11, RNF-04)
  - [ ] CA1: a coleta pode ser feita para todos os repositórios ou para um específico.
  - [ ] CA2: o status e a data/hora da última coleta aparecem por repositório.
  - [ ] CA3: coleta que falha por completo preserva os dados da coleta anterior.

- [ ] **RF-R2-07 – Atualizar apenas com novo commit** (origem: RF-19)
  - [ ] CA1: cada painel tem o botão **Atualizar**.
  - [ ] CA2: com o mesmo commit da última coleta bem-sucedida, nada é lido e a mensagem informa que não há novos commits.
  - [ ] CA3: com commit diferente, a coleta ocorre e o novo commit é gravado e exibido no painel.
  - [ ] CA4: coleta que falhou não altera o commit armazenado, e o próximo **Atualizar** tenta de novo.

### Requisitos técnicos

- [ ] **RT-R2-01 – Migrações e execuções de coleta** (origem: RNF-07)
  - [ ] CA1: migrações por scripts SQL versionados, controlados por `PRAGMA user_version`; o esquema da Release 1 vira a migração inicial.
  - [ ] CA2: tabela de execuções de coleta (início, fim, status, erros) criada por migração.
- [ ] **RT-R2-02 – Resiliência e limite de taxa** (origem: RNF-04, RNF-05)
  - [ ] CA1: falha em um repositório ou arquivo não impede a exibição dos demais; erros reportados por repositório.
  - [ ] CA2: resposta de rate limit é detectada e o usuário é informado de quando tentar novamente.
  - [ ] CA3: requisições condicionais com `ETag` evitam consumo de cota para arquivos inalterados.
- [ ] **RT-R2-03 – Logs de coleta** (origem: RNF-10)
  - [ ] CA1: cada coleta registra repositório, número de arquivos lidos, número de erros e duração.
- [ ] **RT-R2-04 – Testes automatizados da Release 2** (origem: RNF-11, RNF-13)
  - [ ] CA1: testes de agregação cobrindo os casos de RF-R2-03 e RF-R2-04.
  - [ ] CA2: testes do cliente GitHub real com respostas simuladas: 404, 403, rate limit e ETag 304.
  - [ ] CA3: todos os testes passam com `pytest`.

## Release 3 – Entrega final

Objetivo: atender aos requisitos não funcionais, validar o aceite e documentar.

### Requisitos funcionais

- [ ] **RF-R3-01 – Ordem semântica dos vereditos (opcional)** (origem: P-08)
  - [ ] CA1: patrocinador confirma se a ordem alfabética atende; se não, a ordem semântica é definida e aplicada.
  - [ ] CA2: o rótulo exibido é a primeira grafia encontrada do veredito (RF-18).
- [ ] **RF-R3-03 – Modo tendência** (origem: RF-20)
  - [ ] CA1: o modo **Ver como tendência** exibe um gráfico de linhas empilhadas por repositório, com seletor de fase (padrão Tests).
  - [ ] CA2: `GET /api/trend` devolve pontos semanais e uma série por veredito, calculados só com o banco e sem chamadas ao GitHub (teste automatizado).
  - [ ] CA3: o veredito vigente em cada data é o do relatório válido mais recente até ela; a soma das séries em cada ponto é o número de features já avaliadas na fase.
  - [ ] CA4: as cores por veredito são as mesmas dos demais gráficos; fase sem relatórios datados mostra um aviso.
- [ ] **RF-R3-02 – Aceite ponta a ponta** (origem: critérios de aceite, seção 7)
  - [ ] CA1: 2 repositórios válidos e 1 inválido: os válidos aparecem e o inválido mostra erro específico.
  - [ ] CA2: após reiniciar a aplicação, repositórios e último resultado continuam disponíveis.
  - [ ] CA3: coleta interrompida no meio da gravação mantém os dados anteriores.

### Requisitos técnicos

- [ ] **RT-R3-01 – Desempenho** (origem: RNF-03, RNF-15)
  - [ ] CA1: repositório sintético de 10 repositórios × 200 relatórios gerado por script.
  - [ ] CA2: coleta completa em até 60 s, medida pelo log de coleta, com requisições em paralelo.
- [ ] **RT-R3-02 – Usabilidade e acessibilidade** (origem: RNF-09, RNF-15)
  - [ ] CA1: dashboard legível a partir de 1280 px de largura.
  - [ ] CA2: teste automatizado calcula a razão de contraste da paleta de vereditos e exige WCAG AA.
- [ ] **RT-R3-03 – Segurança verificada** (origem: RNF-02)
  - [ ] CA1: revisão confirma que o token não aparece em tela, logs, banco ou repositório de código.
- [ ] **RT-R3-04 – Documentação de entrega** (origem: RNF-08)
  - [ ] CA1: README com pré-requisitos, configuração do token, execução e testes.
  - [ ] CA2: premissas do escopo atualizadas com os resultados dos pré-requisitos.
