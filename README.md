# Dashboard de atividades por fase

MVP web (Python, FastAPI, SQLite) que coleta relatórios de validação de repositórios GitHub e exibe o total de features por fase e veredito. Escopo em [docs/01 escopo-mvp.md](docs/01%20escopo-mvp.md).

## Executar

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

$env:GITHUB_TOKEN = "<token com leitura de conteúdo>"   # opcional para repositórios públicos
uvicorn app.main:create_app --factory
```

Abra <http://127.0.0.1:8000>. Cadastre um repositório (`owner/repo`), clique em **Coletar** e veja o gráfico.

| Variável | Padrão | Uso |
|---|---|---|
| `GITHUB_TOKEN` | — | Token de leitura. Sem ele, o limite da API é de 60 requisições/hora. |
| `DATABASE_PATH` | `app.db` | Arquivo SQLite. |

O gráfico usa Chart.js, carregado de `cdnjs.cloudflare.com`; a página precisa de acesso à internet.

## Testes

```powershell
pip install -r requirements-dev.txt
pytest
```

## Estrutura

- `app/api`: rotas (`/repositories`, `/collections`, `/api/dashboard`).
- `app/services`: coleta, parser dos relatórios e agregação.
- `app/github`: cliente GitHub (interface, HTTP e versão em memória para testes).
- `app/repositories`: persistência em SQLite.
- `app/models`: modelos Pydantic.
- `app/static`: interface web.
