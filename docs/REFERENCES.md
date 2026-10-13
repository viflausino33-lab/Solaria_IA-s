# Referências técnicas

Links consultados para padrões/arquitetura. A licença, dependências e estado atual de cada projeto devem ser reconfirmados antes de incorporar código.

## Projetos comparados

- PuzldAI — https://github.com/MedChaouch/Puzld.ai
- Together Mixture-of-Agents — https://github.com/togethercomputer/MoA
- HermesAgent-MultiModel — https://github.com/InfiniteWhispers/HermesAgent-MultiModel
- Hermes Hybrid Agent Router — https://github.com/cvsgireesh/hermes-hybrid-agent-router
- multi-llm-router — https://github.com/IgnacioGentili/multi-llm-router
- Cebus — https://github.com/cebus-ai/cebus
- MatrixLLM — https://github.com/agent-matrix/matrix-llm
- LiteLLM — https://github.com/BerriAI/litellm

## Padrões e runtime

- LangGraph subagents/context engineering — https://github.com/langchain-ai/docs/blob/main/src/oss/langchain/multi-agent/subagents.mdx
- Pydantic AI multi-agent applications — https://github.com/pydantic/pydantic-ai/blob/main/docs/multi-agent-applications.md
- Ollama configuration — https://github.com/ollama/ollama/blob/main/envconfig/config.go
- Ollama FAQ — https://github.com/ollama/ollama/blob/main/docs/faq.mdx
- llama.cpp server/router/sleep — https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- LiteLLM budget docs — https://github.com/BerriAI/litellm-docs/blob/main/docs/proxy/users.md
- LiteLLM budget fallbacks — https://github.com/BerriAI/litellm-docs/blob/main/docs/proxy/budget_fallbacks.md

## Nota de reprodutibilidade

A presente engenharia reversa consultou README, `package.json`, `pyproject.toml`, licenças e alguns módulos de roteamento/contexto. Não constitui revisão linha a linha de cada repositório, execução de todos os testes, auditoria de segurança ou benchmark comparável em hardware próprio. Antes de depender de uma conclusão, clone o repositório, fixe um commit/tag e valide localmente.
