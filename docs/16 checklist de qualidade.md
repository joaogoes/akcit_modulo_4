# Checklist de qualidade

Gerado a partir do código e dos testes em 10/10/2026 (241 testes, 100% das linhas e dos ramos de `app/`). Resposta ao prompt [16 qualidade.md](../prompts/16%20qualidade.md).

## Verificado na geração do checklist

- **Os logs da coleta não aparecem.** O logger do Python está no nível `WARNING` e sem handlers, então `logger.info("coleta repo=…")` nunca chega ao console. O RT-R2-03 está marcado como concluído no backlog, mas na prática não é visível.
- **Cobertura de ramos:** 96 ramos, nenhum sem teste (100%).
- **Relatórios com quebras de linha CRLF ou com caracteres fora de UTF-8** são lidos normalmente, embora nenhum teste cubra esses casos.

## Riscos técnicos restantes

- [ ] **Logs invisíveis:** configurar o logging no `create_app` e reabrir o RT-R2-03.
- [ ] **Coleta síncrona:** a requisição fica presa durante a leitura (608 arquivos levaram cerca de 20 s). Com muitos repositórios pode estourar o tempo de proxy ou do navegador.
- [ ] **Coletas simultâneas do mesmo repositório** (duas abas, duplo clique): o último a gravar vence, e não há trava.
- [ ] **Limite de requisições no meio da coleta:** tudo é descartado e a próxima tentativa recomeça do zero, gastando a cota de novo. O `ETag` ajudaria.
- [ ] **Sem autenticação:** quem alcança o servidor pode cadastrar repositórios, gastar a cota do token, apagar dados ou ver o resumo de repositórios privados acessíveis pelo token. O padrão do `uvicorn` escuta só em 127.0.0.1, e isso precisa estar documentado.
- [ ] **Chart.js do CDN, sem `integrity`:** risco de cadeia de fornecimento. Sem internet ou com o CDN fora do ar, `Chart` fica indefinido e a página quebra, sem cair para a tabela.
- [ ] **Árvore truncada** (repositório muito grande) falha, sem alternativa.
- [ ] **Branch com `/`** (`feature/x`): o nome é codificado como `%2F` na URL. Não foi testado contra a API real.
- [ ] **Vereditos sem limite:** a API devolve todos, e rótulos longos estouram a legenda.
- [ ] **N+1 no navegador:** uma chamada de dashboard por repositório a cada atualização.
- [ ] **Datas perto da meia-noite:** a tendência usa a data em UTC, então um relatório de 23h30 em UTC-3 cai no dia seguinte.

## Gaps de cobertura de teste

- [ ] **`app.js` (638 linhas) sem teste de comportamento:** modos, tema, diálogo, botão **Atualizar**, cores e erros da coleta. A suíte só confere a estrutura.
- [ ] **Concorrência:** coletas simultâneas e leitura durante a gravação.
- [ ] **Sem teste contra o GitHub real**, nem opcional (por exemplo marcado como `integration` e fora da execução padrão).
- [ ] **Desempenho:** nada com 10 × 200 relatórios (RT-R3-01).
- [ ] **Segurança:** nada garante que o token não aparece em logs ou mensagens de erro (RT-R3-03).
- [ ] **Contraste e acessibilidade** das cores (RT-R3-02), e **fixtures com relatórios reais** (RT-R0-01).
- [ ] **Entradas de borda do parser:** arquivos CRLF, não UTF-8 e muito grandes funcionam, mas sem teste.
- [ ] **Cenário conjunto do aceite** (2 repositórios válidos e 1 inválido) e as 5 fases nos dados de teste (hoje só Requirements e Code).
- [ ] **Sem análise estática:** `ruff` e `mypy` não estão instalados nem configurados, apesar do pedido de código tipado.

## Melhorias prioritárias para a próxima release

1. [ ] Configurar logs visíveis (`INFO` na coleta, sem expor o token).
2. [ ] Validar o repositório no cadastro (existência, acesso e branch), com erro específico (RF-R2-01).
3. [ ] Confirmar P-01 e P-02 com relatórios reais e ajustar o parser (RT-R0-01).
4. [ ] Coleta em segundo plano, com status e proteção contra duas coletas do mesmo repositório.
5. [ ] `ETag` e retomada depois de erro de limite; coleta de repositórios em paralelo, medindo 10 × 200 (RT-R2-02, RT-R3-01).
6. [ ] Servir o Chart.js localmente (ou com `integrity`) e cair para a tabela se ele não carregar.
7. [ ] Endpoint único que devolva todos os painéis de uma vez.
8. [ ] Testes de interface com Playwright, e CI com `pytest`, `ruff` e `mypy`.
9. [ ] Tabela de execuções de coleta e histórico na interface (RT-R2-01).
10. [ ] Documentar a política de acesso (somente local) e avaliar autenticação simples antes de qualquer uso em rede.
