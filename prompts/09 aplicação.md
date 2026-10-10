Contexto: Escopo em docs/01 escopo-mvp.md; já existem app/models, app/repositories e rotas CRUD de repositórios em app/api.
Objetivo: Completar a aplicação web com interface gráfica: cadastro e remoção de repositórios, coleta no GitHub (cliente, parser de generated/verdict e serviço de coleta), endpoint GET /api/dashboard e página com gráfico de barras empilhadas horizontais por fase e veredito, filtro por repositório e status da última coleta.
Estilo: Python tipado e FastAPI em camadas (API, Service, Repository); front-end em HTML, CSS e JavaScript simples servido pelo FastAPI, com Chart.js; cliente GitHub atrás de interface para testes.
Resposta: Código completo de app/main.py, app/services, app/github, app/static e instruções de execução.
