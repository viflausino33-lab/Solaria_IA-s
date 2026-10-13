# Política de segurança

## Escopo atual

O MVP foi pensado para rodar localmente. Não o exponha à internet e não o considere multiusuário/production-ready.

## Reporte responsável

Não publique credenciais, prompts confidenciais ou detalhes de exploração em Issues públicas. Remova chaves e dados pessoais de qualquer relatório. Até existir canal privado dedicado, abra uma Issue sem detalhes sensíveis solicitando contato seguro.

## Controles obrigatórios antes de agentes com ferramentas

- autenticação/autorização da API;
- allowlist por ferramenta e por agente;
- execução de código em sandbox isolada;
- aprovação humana para operações destrutivas ou externas;
- limites de tempo, memória, arquivos e chamadas;
- proteção contra prompt injection em documentos e ferramentas;
- logs de auditoria sem segredos;
- isolamento de dados por sessão/usuário.
