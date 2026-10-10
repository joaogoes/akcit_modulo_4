# Backlog mínimo – Dashboard de Atividades por Fase

Legenda: **RF** = requisito funcional, **RT** = requisito técnico. A coluna "Origem" refere-se aos IDs de [01 escopo-mvp.md](01%20escopo-mvp.md) (RF-xx e RNF-xx).
Cada item só é marcado como concluído quando todos os seus critérios de aceite (CA) forem atendidos.

## Release 1 – Core

Objetivo: ponta a ponta funcional, do cadastro do repositório ao gráfico.

### Requisitos funcionais

- [ ] **RF-R1-01 – Cadastrar e remover repositório** (origem: RF-01, RF-02, RF-04)
  - [ ] CA1: informar `owner/repo` ou URL cria o registro no banco e o exibe na lista.
  - [ ] CA2: remover um repositório apaga o registro e seus relatórios do banco.
  - [ ] CA3: após reiniciar a aplicação, os repositórios continuam listados.
- [ ] **RF-R1-02 – Coletar relatórios das 5 fases** (origem: RF-05, RF-06, RF-10, RF-11)
  - [ ] CA1: a coleta lê as 5 pastas de fase e identifica a feature pelo subdiretório `<feature>`.
  - [ ] CA2: só `*.md` diretamente na pasta de relatórios são lidos.
  - [ ] CA3: fase ou pasta inexistente resulta em zero features, sem erro.
  - [ ] CA4: a coleta é acionada sob demanda e a data/hora da última coleta é exibida.
- [ ] **RF-R1-03 – Extrair `generated` e `verdict`** (origem: RF-07, RF-08, RF-18)
  - [ ] CA1: os campos são lidos em front matter ou no corpo; vale a primeira ocorrência.
  - [ ] CA2: `verdict` é normalizado (sem diferenciar maiúsculas/minúsculas, sem espaços nas extremidades).
  - [ ] CA3: com mais de um relatório válido para a mesma feature e fase, vale o de `generated` mais recente.
- [ ] **RF-R1-04 – Gráfico de barras empilhadas horizontais** (origem: RF-12, RF-13, RF-14, RF-15, RF-17)
  - [ ] CA1: uma barra por fase, na ordem Requirements → FSpec → DSpec → Code → Tests.
  - [ ] CA2: segmentos por veredito, com cor fixa por veredito e legenda.
  - [ ] CA3: o valor de cada segmento é visível em rótulo ou tooltip.
  - [ ] CA4: os totais conferem com a contagem manual de um repositório de teste.

### Requisitos técnicos

- [ ] **RT-R1-01 – Acesso ao GitHub** (origem: RNF-01, RNF-02)
  - [ ] CA1: leitura via API do GitHub com token lido de variável de ambiente.
  - [ ] CA2: o token não aparece em tela, logs ou banco.
  - [ ] CA3: nenhuma operação de escrita é feita nos repositórios consultados.
- [ ] **RT-R1-02 – Banco de dados e migrações** (origem: RNF-06, RNF-07)
  - [ ] CA1: SQLAlchemy + Alembic; SQLite como padrão.
  - [ ] CA2: tabelas de repositórios, relatórios e execuções de coleta criadas por migração.
  - [ ] CA3: o dashboard lê do banco e não dispara coleta ao ser aberto.
- [ ] **RT-R1-03 – Esqueleto da aplicação web** (origem: RNF-08)
  - [ ] CA1: Python 3.11+ com FastAPI ou Flask, executável localmente no Windows 11 com um único comando documentado.
  - [ ] CA2: dependências declaradas em `requirements.txt` ou `pyproject.toml`.
- [ ] **RT-R1-04 – Separação de camadas** (origem: RNF-11)
  - [ ] CA1: parser, cliente GitHub, persistência e agregação são módulos independentes.
  - [ ] CA2: o parser tem testes unitários com fixtures de relatórios.

## Release 2 – Qualidade

Objetivo: robustez, tratamento de erros e cobertura de testes.

### Requisitos funcionais

- [ ] **RF-R2-01 – Validação do cadastro** (origem: RF-03)
  - [ ] CA1: repositório inexistente, sem permissão ou acima do limite de requisições gera mensagem de erro específica.
  - [ ] CA2: cadastro inválido não é gravado no banco.
- [ ] **RF-R2-02 – Relatórios inválidos** (origem: RF-09, RF-17)
  - [ ] CA1: relatório sem `verdict` ou com `generated` ilegível é sinalizado ao usuário.
  - [ ] CA2: feature cujos relatórios na fase são todos inválidos aparece como "Inválido", sempre como último segmento da barra.
  - [ ] CA3: feature com ao menos um relatório válido usa o veredito do mais recente entre os válidos.
  - [ ] CA4: relatório inválido não interrompe a coleta dos demais.
- [ ] **RF-R2-03 – Contagem por repositório** (origem: RF-10a)
  - [ ] CA1: feature de mesmo nome em 2 repositórios conta 2 vezes.
- [ ] **RF-R2-04 – Filtro por repositório** (origem: RF-16)
  - [ ] CA1: o gráfico agrega todos os repositórios por padrão.
  - [ ] CA2: o usuário seleciona um ou mais repositórios e o gráfico é recalculado.
- [ ] **RF-R2-05 – Coleta parcial e status** (origem: RF-11, RNF-04)
  - [ ] CA1: a coleta pode ser feita para todos os repositórios ou para um específico.
  - [ ] CA2: o status e a data/hora da última coleta aparecem por repositório.
  - [ ] CA3: coleta que falha por completo preserva os dados da coleta anterior.

### Requisitos técnicos

- [ ] **RT-R2-01 – Resiliência** (origem: RNF-04)
  - [ ] CA1: falha em um repositório ou arquivo não impede a exibição dos demais.
  - [ ] CA2: os erros são reportados por repositório.
- [ ] **RT-R2-02 – Limite de taxa da API** (origem: RNF-05)
  - [ ] CA1: resposta de rate limit é detectada e o usuário é informado de quando tentar novamente.
- [ ] **RT-R2-03 – Logs de coleta** (origem: RNF-10)
  - [ ] CA1: cada coleta registra repositório, número de arquivos lidos, número de erros e duração.
- [ ] **RT-R2-04 – Testes automatizados** (origem: RNF-11)
  - [ ] CA1: testes de agregação contra SQLite em memória cobrindo os casos de RF-R2-02 e RF-R2-03.
  - [ ] CA2: testes do cliente GitHub com respostas simuladas, incluindo 404, 403 e rate limit.
  - [ ] CA3: todos os testes passam em execução local com `pytest`.

## Release 3 – Entrega final

Objetivo: atender aos requisitos não funcionais, validar o aceite e documentar.

### Requisitos funcionais

- [ ] **RF-R3-01 – Ordem e rótulo dos vereditos** (origem: P-08, RF-18)
  - [ ] CA1: a ordem dos segmentos está definida e confirmada com o patrocinador.
  - [ ] CA2: o rótulo exibido é a primeira grafia encontrada do veredito.
- [ ] **RF-R3-02 – Aceite ponta a ponta** (origem: critérios de aceite, seção 7)
  - [ ] CA1: 2 repositórios válidos e 1 inválido: os válidos aparecem e o inválido mostra erro específico.
  - [ ] CA2: remover um repositório atualiza o gráfico sem nova coleta.
  - [ ] CA3: após reiniciar a aplicação, repositórios e último resultado continuam disponíveis.

### Requisitos técnicos

- [ ] **RT-R3-01 – Desempenho** (origem: RNF-03)
  - [ ] CA1: coleta de 10 repositórios com 200 relatórios cada em até 60 s, com requisições em paralelo.
- [ ] **RT-R3-02 – Usabilidade e acessibilidade** (origem: RNF-09)
  - [ ] CA1: dashboard legível a partir de 1280 px de largura.
  - [ ] CA2: cores dos vereditos com contraste mínimo WCAG AA.
- [ ] **RT-R3-03 – Segurança verificada** (origem: RNF-02)
  - [ ] CA1: revisão confirma que o token não aparece em tela, logs, banco ou repositório de código.
- [ ] **RT-R3-04 – Documentação de entrega** (origem: RNF-08)
  - [ ] CA1: README com pré-requisitos, configuração do token, migração do banco, execução e testes.
  - [ ] CA2: premissas P-01 e P-02 confirmadas e refletidas no parser e no escopo.
