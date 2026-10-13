# Contribuindo

## Antes de abrir uma implementação

1. Leia `docs/ARCHITECTURE.md` e os ADRs.
2. Abra uma Issue para mudanças de arquitetura ou novos provedores.
3. Defina teste reproduzível antes de otimizar qualidade, latência ou custo.
4. Não use credenciais reais em testes; use o provedor `mock`.

## Regras de desenvolvimento

- Python 3.11+; async I/O para chamadas a modelos.
- Roteamento determinístico primeiro; chamada de LLM para classificar somente se houver benefício medido.
- Tipos e schemas explícitos; erros de provedor não podem virar sucesso silencioso.
- Toda nova chamada de modelo deve documentar seu gatilho, limite, custo esperado e teste de bloqueio.
- Não registrar prompts/respostas completos por padrão.
- Não fazer execução de shell/alteração de arquivos em agentes sem sandbox e autorização.

## Validação local

```bash
python -m pip install -e ".[dev]"
pytest
ruff check .
```

## Pull requests

Inclua: motivação, trade-offs, testes executados, mudança de custo/latência/recursos e impactos sobre privacidade.
