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

Abra <http://127.0.0.1:8000>. No primeiro uso, o banco já vem com dois repositórios de exemplo (`joaogoes/akcit_modulo_4_repo`, branches `projeto-1` e `projeto-2`); clique em **Coletar todos** e veja o gráfico. Para acompanhar outro repositório, cadastre `owner/repo` (e a branch, se necessária). O mesmo repositório pode ser cadastrado uma vez por branch. O modo **Ver como tendência** mostra a evolução semanal das features por veredito (fase à escolha, padrão Tests), calculada só com os dados já coletados. O botão **Atualizar** de cada painel só coleta se houver um commit novo no branch; **Coletar**, na engrenagem, sempre lê tudo.

Os repositórios de exemplo são cadastrados apenas quando o banco é criado; remover um deles não o recria. Para voltar ao estado inicial, apague o arquivo do banco (`app.db`).

| Variável | Padrão | Uso |
|---|---|---|
| `GITHUB_TOKEN` | — | Token de leitura, necessário para repositórios privados. Sem ele só repositórios públicos funcionam: a árvore vem da API (1 chamada por coleta, limite de 60/hora) e os arquivos de `raw.githubusercontent.com`. |
| `DATABASE_PATH` | `app.db` | Arquivo SQLite. |

O gráfico usa Chart.js, carregado de `cdnjs.cloudflare.com`; a página precisa de acesso à internet.

## Testes

```powershell
pip install -r requirements-dev.txt
pytest                                   # 218 testes
pytest --cov=app --cov-report=term-missing   # com cobertura
```

## Estrutura

- `app/api`: rotas (`/repositories`, `/collections`, `/api/dashboard`).
- `app/services`: coleta, parser dos relatórios e agregação.
- `app/github`: cliente GitHub (interface, HTTP e versão em memória para testes).
- `app/repositories`: persistência em SQLite.
- `app/models`: modelos Pydantic.
- `app/static`: interface web.
