# Backlog mínimo – Dashboard de Atividades por Fase

Legenda: **RF** = requisito funcional, **RT** = requisito técnico. A coluna "origem" refere-se aos IDs de [01 escopo-mvp.md](01%20escopo-mvp.md) (RF-xx, RNF-xx, R-xx).
Cada item só é marcado como concluído (`[x]`) quando todos os seus critérios de aceite (CA) forem atendidos. Itens **parciais** ficam abertos, com os CAs já atendidos marcados e uma nota sobre o que falta.
O corte dos releases segue a revisão em [05 revisão de planejamento.md](05%20revis%C3%A3o%20de%20planejamento.md).

**Situação em 10/10/2026** (365 testes passando, 100% de cobertura de linhas de `app/`)

| Bloco | Concluídos | Parciais | Pendentes | Substituídos |
|---|---|---|---|---|
| Pré-requisitos | RT-R0-02 | RT-R0-03 | RT-R0-01 | – |
| Release 1 – Core | RF-R1-01, RF-R1-02, RF-R1-04, RT-R1-02, RT-R1-03, RT-R1-04 | RF-R1-03, RT-R1-01 | – | – |
| Release 2 – Qualidade | RF-R2-03, RF-R2-04, RF-R2-06, RF-R2-07, RF-R2-09, RT-R2-03 | RF-R2-01, RF-R2-02, RF-R2-08, RT-R2-01, RT-R2-02, RT-R2-04 | – | RF-R2-05 |
| Release 3 – Entrega final | RF-R3-03 | RF-R3-01, RF-R3-02, RT-R3-02, RT-R3-04 | RT-R3-01, RT-R3-03 | – |

## Pré-requisitos (antes da Release 1)

Mitigação dos riscos técnicos R-01, R-02 e R-03.

- [ ] **RT-R0-01 – Relatórios e estrutura reais** (origem: R-02, P-01, P-02, P-07) — *pendente*
  - [ ] CA1: 3 a 5 relatórios reais obtidos e versionados como fixtures.
  - [ ] CA2: P-01 (caminho de Tests) e P-02 (front matter ou corpo) confirmados e registrados no escopo.
- [x] **RT-R0-02 – Protótipo de coleta (spike)** (origem: R-01)
  - [x] CA1: a coleta lê a árvore de um repositório real pela API de árvore do Git (1 chamada) e lista features e relatórios.
  - [x] CA2: o número de chamadas à API foi calculado para 10 repositórios × 200 relatórios e cabe em 5.000 requisições/hora (registrado no doc 05, seção 4). O tempo de coleta não foi medido (ver RT-R3-01).
  - [x] CA3: o resultado está registrado em [05 revisão de planejamento.md](05%20revis%C3%A3o%20de%20planejamento.md).
- [ ] **RT-R0-03 – Fixtures com contagem esperada** (origem: RNF-12) — *parcial*
  - [ ] CA1: pasta de fixtures versionada com estrutura das fases e tabela de contagem esperada por fase e veredito. *Hoje os dados e contagens esperadas estão em `tests/conftest.py`, e há um repositório de exemplo fictício, sem uma pasta própria.*
  - [x] CA2: casos sintéticos incluídos: sem `verdict`, sem `generated`, data inválida, variação de caixa e espaços, duplicatas na mesma fase.

## Release 1 – Core

Objetivo: **uma fase de ponta a ponta**, do cadastro ao gráfico. O código já cobre as 5 fases, porque elas são só linhas da tabela de configuração.

### Requisitos funcionais

- [x] **RF-R1-01 – Cadastrar repositório** (origem: RF-01, RF-04)
  - [x] CA1: informar `owner/repo` cria o registro no banco e o exibe na lista.
  - [x] CA2: após reiniciar a aplicação, os repositórios continuam listados.
- [x] **RF-R1-02 – Coletar relatórios das fases** (origem: RF-05, RF-06, RF-10, RF-11)
  - [x] CA1: a coleta lê a pasta de relatórios de cada fase e identifica a feature pelo subdiretório `<feature>`.
  - [x] CA2: só `*.md` diretamente na pasta de relatórios são lidos.
  - [x] CA3: pasta inexistente resulta em zero features, sem erro.
  - [x] CA4: as fases são definidas por tabela de configuração (`PHASE_LAYOUTS`), sem lógica específica por fase.
  - [x] CA5: a coleta é acionada sob demanda e a data/hora da última coleta é exibida.
- [ ] **RF-R1-03 – Extrair `generated` e `verdict`** (origem: RF-07, RF-08, RF-18, P-04) — *parcial*
  - [ ] CA1: os campos são lidos conforme o formato confirmado em RT-R0-01; vale a primeira ocorrência. *O parser aceita front matter e corpo, mas o formato real ainda não foi confirmado (P-02).*
  - [x] CA2: `verdict` é normalizado (sem diferenciar maiúsculas/minúsculas, sem espaços nas extremidades).
  - [x] CA3: com mais de um relatório válido para a mesma feature e fase, vale o de `generated` mais recente.
  - [x] CA4: datas ISO 8601 (data e data/hora, com e sem fuso) são aceitas; sem fuso assume UTC; formato inválido torna o relatório inválido.
- [x] **RF-R1-04 – Gráfico de barras empilhadas horizontais** (origem: RF-12, RF-13, RF-14, RF-15, RF-17)
  - [x] CA1: uma barra por fase, na ordem Requirements → FSpec → DSpec → Code → Tests.
  - [x] CA2: segmentos por veredito, com cor fixa por veredito e legenda. Aprovado é verde (Sucesso, Success, Approved, Passed e OK são reportados como Aprovado), Aprovado com ressalvas é âmbar e Reprovado é vermelho.
  - [x] CA3: ordem dos segmentos fixa e estável: Aprovado, Aprovado com ressalvas, Reprovado, os demais vereditos em ordem alfabética e "Inválido" por último. A API devolve os vereditos em ordem alfabética.
  - [x] CA4: o valor de cada segmento é visível em rótulo ou tooltip.
  - [x] CA5: os totais coincidem com a contagem esperada dos dados de teste.

### Requisitos técnicos

- [ ] **RT-R1-01 – Acesso ao GitHub atrás de interface** (origem: RNF-01, RNF-02, RNF-13) — *parcial*
  - [x] CA1: interface `GitHubClient` (`get_default_branch`, `get_head_commit`, `list_files`, `get_file`) com implementação HTTP e implementação em memória.
  - [x] CA2: a implementação real usa a API de árvore do Git.
  - [x] CA3: o token vem do banco (cifrado) ou de variável de ambiente e não aparece em tela, logs nem respostas da API (testes automatizados; a revisão formal continua em RT-R3-03).
  - [x] CA4: nenhuma operação de escrita é feita nos repositórios consultados.
- [x] **RT-R1-02 – Banco de dados e gravação atômica** (origem: RNF-06, RNF-07, RF-11, R-03)
  - [x] CA1: `sqlite3` da biblioteca padrão; esquema criado por script SQL idempotente.
  - [x] CA2: duas tabelas: repositórios e relatórios (repositório, fase, feature, caminho, `generated`, `verdict`; mais status e commit da última coleta).
  - [x] CA3: a coleta de um repositório grava em uma única transação; falha injetada no meio da gravação mantém os dados anteriores (teste automatizado).
  - [x] CA4: o dashboard lê do banco e não dispara coleta ao ser aberto.
- [x] **RT-R1-03 – Aplicação web em camadas e API de dados** (origem: RNF-08, RNF-11, RNF-14)
  - [x] CA1: Python 3.11+ com FastAPI, executável localmente no Windows 11 com um único comando documentado; dependências declaradas.
  - [x] CA2: parser, cliente GitHub, persistência e agregação são módulos independentes.
  - [x] CA3: endpoint JSON (`GET /api/dashboard`) devolve a agregação por fase e veredito; a página consome esse endpoint.
- [x] **RT-R1-04 – Testes da Release 1** (origem: RNF-11, RNF-12)
  - [x] CA1: testes unitários do parser com relatórios sintéticos.
  - [x] CA2: teste da agregação sobre SQLite em memória, comparando com a contagem esperada.
  - [x] CA3: teste do endpoint JSON com o cliente GitHub em memória.
  - [x] CA4: todos os testes passam com `pytest`.

## Release 2 – Qualidade

Objetivo: completar as fases e funcionalidades de gestão, e dar robustez e cobertura de testes.

### Requisitos funcionais

- [ ] **RF-R2-01 – Gestão de repositórios completa** (origem: RF-02, RF-03, RF-01) — *parcial*
  - [x] CA1: remover um repositório apaga o registro e seus relatórios do banco e atualiza o gráfico sem nova coleta.
  - [ ] CA2: repositório inexistente, sem permissão ou acima do limite de requisições gera mensagem de erro específica. *Hoje o erro específico aparece na coleta, não no cadastro.*
  - [ ] CA3: cadastro inválido não é gravado no banco. *Nome fora do formato `owner/repo` é rejeitado (422), mas um repositório inexistente no GitHub é gravado.*
  - [x] CA4: URL completa do GitHub é aceita e normalizada para `owner/repo`.
- [ ] **RF-R2-02 – Demais fases (FSpec, DSpec, Code, Tests)** (origem: RF-05, RF-10) — *parcial*
  - [x] CA1: as quatro fases estão na tabela de configuração, sem nova lógica de coleta.
  - [ ] CA2: as fixtures cobrem as 5 fases e a contagem esperada é atendida. *As fixtures de teste cobrem Requirements e Code; as 5 fases foram conferidas com o repositório de exemplo.*
  - [x] CA3: o gráfico exibe as 5 barras na ordem definida.
- [x] **RF-R2-03 – Relatórios inválidos** (origem: RF-09, RF-17)
  - [x] CA1: relatório sem `verdict` ou com `generated` ilegível é sinalizado ao usuário.
  - [x] CA2: feature cujos relatórios na fase são todos inválidos aparece como "Inválido".
  - [x] CA3: feature com ao menos um relatório válido usa o veredito do mais recente entre os válidos.
  - [x] CA4: relatório inválido não interrompe a coleta dos demais.
- [x] **RF-R2-04 – Contagem por repositório** (origem: RF-10a)
  - [x] CA1: feature de mesmo nome em 2 repositórios conta 2 vezes.
- [x] **RF-R2-05 – Filtro por repositório** (origem: RF-16) — *substituído*: a interface mostra um gráfico por repositório (prompt 10), então não há filtro nem agregação na tela. O endpoint `/api/dashboard` ainda aceita `repository_ids`.
  - ~~CA1: o gráfico agrega todos os repositórios por padrão.~~
  - ~~CA2: o usuário seleciona um ou mais repositórios e o gráfico é recalculado.~~
- [x] **RF-R2-06 – Coleta parcial e status** (origem: RF-11, RNF-04)
  - [x] CA1: a coleta pode ser feita para todos os repositórios ou para um específico.
  - [x] CA2: o status e a data/hora da última coleta aparecem por repositório.
  - [x] CA3: coleta que falha por completo preserva os dados da coleta anterior.
- [x] **RF-R2-07 – Atualizar apenas com novo commit** (origem: RF-19)
  - [x] CA1: cada painel tem o botão **Atualizar**.
  - [x] CA2: com o mesmo commit da última coleta bem-sucedida, nada é lido e a mensagem informa que não há novos commits.
  - [x] CA3: com commit diferente, a coleta ocorre e o novo commit é gravado e exibido no painel.
  - [x] CA4: coleta que falhou não altera o commit armazenado, e o próximo **Atualizar** tenta de novo.
- [ ] **RF-R2-08 – Repositórios do Azure DevOps** (origem: RF-21) — *parcial*: falta validar contra um repositório real
  - [x] CA1: a URL do Azure DevOps (`dev.azure.com`, com ou sem usuário, ou `*.visualstudio.com`) é aceita e normalizada para `organização/projeto/repositório`; endereços de outros provedores são recusados com orientação.
  - [x] CA2: a coleta, o botão **Atualizar** (por commit), o dashboard e a tendência funcionam para repositórios do Azure DevOps.
  - [x] CA3: o token vem de `AZURE_DEVOPS_TOKEN` (Basic com PAT); a falta de autenticação gera uma mensagem que pede o token.
  - [ ] CA4: validado contra um repositório real do Azure DevOps. *Só foi testado com respostas simuladas e com a sondagem anônima da API, que confirmou o redirecionamento para o login.*

- [x] **RF-R2-09 – Tokens por provedor, cifrados no banco** (origem: RF-22, RNF-02)
  - [x] CA1: a janela da engrenagem permite salvar, substituir e remover o token de cada provedor; a tela mostra só o estado (banco, variável de ambiente ou não configurado).
  - [x] CA2: o token é cifrado com o DPAPI do Windows; o arquivo do banco não contém o valor em claro (conferido com o DPAPI real).
  - [x] CA3: a API nunca devolve o token, e os erros de validação e os logs não o repetem (testes automatizados).
  - [x] CA4: o token do banco vale na requisição seguinte, sem reiniciar, e tem prioridade sobre a variável de ambiente.
  - [x] CA5: onde não há DPAPI, salvar é recusado com orientação a usar as variáveis de ambiente.

### Requisitos técnicos

- [ ] **RT-R2-01 – Migrações e execuções de coleta** (origem: RNF-07) — *parcial*
  - [x] CA1: migrações controladas por `PRAGMA user_version` (em `app/repositories/schema.py`), a partir do esquema da Release 1. *São feitas em código Python, não em scripts SQL separados.*
  - [ ] CA2: tabela de execuções de coleta (início, fim, status, erros) criada por migração.
- [ ] **RT-R2-02 – Resiliência e limite de taxa** (origem: RNF-04, RNF-05) — *parcial*
  - [x] CA1: falha em um repositório ou arquivo não impede a exibição dos demais; erros reportados por repositório.
  - [x] CA2: resposta de rate limit é detectada e o usuário é informado de quando tentar novamente.
  - [ ] CA3: requisições condicionais com `ETag` evitam consumo de cota para arquivos inalterados.
- [x] **RT-R2-03 – Logs de coleta** (origem: RNF-10)
  - [x] CA1: cada coleta registra repositório, número de arquivos lidos, número de erros e duração.
- [ ] **RT-R2-04 – Testes automatizados da Release 2** (origem: RNF-11, RNF-13) — *parcial*
  - [x] CA1: testes de agregação cobrindo os casos de RF-R2-03 e RF-R2-04.
  - [ ] CA2: testes do cliente GitHub real com respostas simuladas: 404, 403 e rate limit estão cobertos; falta o ETag 304 (depende de RT-R2-02, CA3).
  - [x] CA3: todos os testes passam com `pytest`.

## Release 3 – Entrega final

Objetivo: atender aos requisitos não funcionais, validar o aceite e documentar.

### Requisitos funcionais

- [ ] **RF-R3-01 – Ordem semântica dos vereditos (opcional)** (origem: P-08) — *parcial*
  - [ ] CA1: patrocinador confirma se a ordem atual atende; se não, a ordem semântica é definida e aplicada. *Os três vereditos conhecidos já têm posição e cor fixas (Aprovado, com ressalvas, Reprovado), sem confirmação formal.*
  - [x] CA2: o rótulo exibido é a primeira grafia encontrada do veredito (RF-18).
- [ ] **RF-R3-02 – Aceite ponta a ponta** (origem: critérios de aceite, seção 7) — *parcial*
  - [ ] CA1: 2 repositórios válidos e 1 inválido: os válidos aparecem e o inválido mostra erro específico. *Cada parte é testada, mas não o cenário conjunto.*
  - [x] CA2: após reiniciar a aplicação, repositórios e último resultado continuam disponíveis.
  - [x] CA3: coleta interrompida no meio da gravação mantém os dados anteriores.
- [x] **RF-R3-03 – Modo tendência** (origem: RF-20)
  - [x] CA1: o modo **Ver como tendência** exibe um gráfico de linhas empilhadas por repositório, com seletor de fase (padrão Tests).
  - [x] CA2: `GET /api/trend` devolve pontos semanais e uma série por veredito, calculados só com o banco e sem chamadas ao GitHub (teste automatizado).
  - [x] CA3: o veredito vigente em cada data é o do relatório válido mais recente até ela; a soma das séries em cada ponto é o número de features já avaliadas na fase.
  - [x] CA4: barras e tendência têm exatamente a mesma aparência: preenchimento com a cor do veredito a 35% de opacidade e contorno super fino (0,5 px) na cor exata (verde, âmbar e vermelho; conferido pixel a pixel no navegador); fase sem relatórios datados mostra um aviso.
  - [x] CA5: todos os gráficos de tendência têm exatamente as mesmas datas no eixo horizontal (`start` e `end` de `GET /api/trend`, calculados sobre todos os repositórios).

### Requisitos técnicos

- [ ] **RT-R3-01 – Desempenho** (origem: RNF-03, RNF-15) — *pendente*
  - [ ] CA1: repositório sintético de 10 repositórios × 200 relatórios gerado por script.
  - [ ] CA2: coleta completa em até 60 s, medida pelo log de coleta, com requisições em paralelo.
- [ ] **RT-R3-02 – Usabilidade e acessibilidade** (origem: RNF-09, RNF-15) — *parcial*
  - [x] CA1: dashboard legível a partir de 1280 px de largura (conferido em capturas de tela).
  - [ ] CA2: teste automatizado calcula a razão de contraste da paleta de vereditos e exige WCAG AA.
- [ ] **RT-R3-03 – Segurança verificada** (origem: RNF-02) — *pendente*
  - [ ] CA1: revisão confirma que o token não aparece em tela, logs, banco ou repositório de código.
- [ ] **RT-R3-04 – Documentação de entrega** (origem: RNF-08) — *parcial*
  - [x] CA1: README com pré-requisitos, configuração do token, execução e testes.
  - [ ] CA2: premissas do escopo atualizadas com os resultados dos pré-requisitos (depende de RT-R0-01).
