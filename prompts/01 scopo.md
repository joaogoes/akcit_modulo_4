1. Contexto
MVP WEB criado em python, com banco de dados, para visualização de dashboard de atividades executadas em um conjunto de repositórios do github cadastrados pelo usuário em tempo de execução.
Cada repositório possui os seguintes arquivos, separados por fase de projeto:
    - Requirements: relatórios *.md em `200 Requirements\230 Output\<feature>\reports\req-validation`
    - FSpec: relatórios *.md em `300 Specs\320 F-Specs\Output\<feature>\reports\fspec-validation`
    - DSpec: relatórios *.md em `300 Specs\330 D-Specs\Output\<feature>\reports\dspec-validation`
    - Code: relatórios *.md em `400 Code\Output\<feature>\reports\code-validation`
    - Tests: relatórios *.md em `500 Tests\Output\<feature>reports\code-tests`
Cada relatório possui os campos:
    - Data do relatório em "generated: <data do relatório>"
    - Veredito em "verdict: <resultado>"
O dashboard deve mostrar o total de features por fase e veredito considerando os conteúdos das pastas, em gráficos de barras empilhadas horizontalmente.

2. Objetivo: Gerar documento de escopo com objetivo, requisitos funcionais, não funcionais e fora de escopo.
3. Estilo: Linguagem técnica, direta, em markdown
4. Resposta: Forneça o conteúdo completo em `docs/01 escopo-mvp.md`

