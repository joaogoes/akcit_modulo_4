# Diagrama de componentes e fluxo de dados

Componentes da aplicação como estão implementados (veja [01 escopo-mvp.md](01%20escopo-mvp.md) para os requisitos). Há três fluxos:

- **Coleta** (linhas tracejadas, A1–A9): lê o GitHub e grava no banco. É o único fluxo que acessa o GitHub.
- **Dashboard** (linhas contínuas, B1–B4): lê só o banco.
- **Tendência** (linhas grossas, C1–C4): lê só o banco.

```mermaid
flowchart LR
    Browser["Navegador<br/>app/static + Chart.js"]
    GitHub["GitHub e Azure DevOps<br/>APIs REST (e raw.githubusercontent.com)"]

    subgraph App["Aplicação FastAPI (app/)"]
        API["api<br/>repositories · collections<br/>dashboard · trend"]
        Collect["CollectionService<br/>(orquestra a coleta)"]
        Source["ReportSource<br/>(encontra e lê relatórios)"]
        Parser["parse_report + layout<br/>(fases, pastas, generated, verdict)"]
        Client["GitHubClient (interface)<br/>um cliente por provedor"]
        Dash["DashboardService"]
        Trend["TrendService"]
        Shared["selection + verdicts<br/>(ids e rótulos comuns)"]
        Repos["RepoRepository<br/>ReportRepository"]
        DB["Database + schema<br/>(sqlite3)"]
    end

    SQLite[("SQLite<br/>app.db")]

    %% Cadastro
    Browser -- "POST/GET/PUT/DELETE /repositories" --> API
    API --> Repos

    %% Coleta
    Browser -. "A1. POST /collections" .-> API
    API -. "A2. repositórios" .-> Collect
    Collect -. "A3. SHA do commit" .-> Client
    Client -. "A4. REST e raw" .-> GitHub
    Collect -. "A5. mesmo SHA? (unchanged)" .-> Repos
    Collect -. "A6. árvore e arquivos .md" .-> Source
    Source -. "A7. texto do relatório" .-> Parser
    Source -. "lê pelo cliente" .-> Client
    Collect -. "A8. grava em transação" .-> Repos
    Collect -. "A9. status e commit" .-> Repos

    %% Dashboard
    Browser -- "B1. GET /api/dashboard" --> API
    API -- "B2. ids" --> Dash
    Dash -- "B3. relatórios" --> Repos
    Dash -- "regras" --> Shared
    Dash -- "B4. JSON por fase e veredito" --> API

    %% Tendência
    Browser == "C1. GET /api/trend" ==> API
    API == "C2. ids e fase" ==> Trend
    Trend == "C3. relatórios datados" ==> Repos
    Trend == "regras" ==> Shared
    Trend == "C4. JSON semanal" ==> API

    Repos --> DB --> SQLite
```

**Pontos de projeto**
- O dashboard e a tendência nunca chamam o GitHub; só a coleta chama, o que mantém a cota da API sob controle.
- A coleta lê todos os arquivos pelo SHA do commit (A3), então os dados são um retrato único dele. Com `only_if_changed`, o mesmo SHA da última coleta bem-sucedida encerra o fluxo em A5, sem ler arquivos.
- `GitHubClient` é uma interface: o serviço de coleta escolhe o cliente pelo provedor do repositório (GitHub ou Azure DevOps). As versões HTTP são usadas em produção e a versão em memória, nos testes.
- A gravação (A8) troca todos os relatórios do repositório em uma única transação; se falhar, os dados anteriores permanecem.
