# Diagrama de componentes e fluxo de dados

Componentes do MVP descritos em [01 escopo-mvp.md](01%20escopo-mvp.md). Dois fluxos: **coleta** (linhas tracejadas, A1–A8) e **consulta ao dashboard** (linhas contínuas, B1–B5).

```mermaid
flowchart LR
    Browser["Navegador<br/>(página + gráfico)"]
    GitHub["API do GitHub"]

    subgraph App["Aplicação FastAPI"]
        API["API<br/>(routers, schemas Pydantic)"]
        RepoSvc["RepositoryService<br/>(cadastro)"]
        CollectSvc["CollectionService<br/>(orquestra a coleta)"]
        DashSvc["DashboardService<br/>(agregação)"]
        Client["GitHubClient<br/>(interface)"]
        Parser["ReportParser<br/>(generated, verdict)"]
        Repo["Repositories<br/>(SQLAlchemy)"]
    end

    DB[("Banco de dados<br/>SQLite")]

    %% Cadastro
    Browser -- "cadastra owner/repo" --> API
    API --> RepoSvc
    RepoSvc --> Repo

    %% Fluxo de coleta
    Browser -. "A1. POST /collections" .-> API
    API -. "A2. repositórios" .-> CollectSvc
    CollectSvc -. "A3. árvore e arquivos .md" .-> Client
    Client -. "A4. REST + ETag" .-> GitHub
    GitHub -. "A5. conteúdo" .-> Client
    CollectSvc -. "A6. texto do relatório" .-> Parser
    Parser -. "A7. Report" .-> CollectSvc
    CollectSvc -. "A8. grava em transação" .-> Repo

    %% Fluxo do dashboard
    Browser -- "B1. GET /api/dashboard" --> API
    API -- "B2. filtro de repositórios" --> DashSvc
    DashSvc -- "B3. consulta" --> Repo
    Repo -- "B4. totais por fase e veredito" --> DashSvc
    DashSvc -- "B5. Dashboard (JSON)" --> API

    Repo <--> DB
```
