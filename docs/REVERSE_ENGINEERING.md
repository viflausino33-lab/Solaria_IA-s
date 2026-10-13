# Engenharia reversa: projetos de referência

**Pesquisa consultada em 13/10/2026.** Esta é uma análise de arquitetura pública (README, manifestos, configuração e arquivos selecionados), não uma auditoria de segurança nem uma garantia de que cada projeto funciona sem adaptação. Stars/commits e documentação mudam; valide o estado do repositório antes de adotá-lo.

## Resumo executivo

| Projeto | Papel principal | Padrões que vale estudar | O que não copiar cegamente | Licença indicada no repo |
|---|---|---|---|---|
| [PuzldAI](https://github.com/MedChaouch/Puzld.ai) | Orquestração de multi-LLM | Roteador, adaptadores, pipelines, revisão, contexto, sumarização e memória | É TypeScript/Node e licença AGPL-3.0; integração/cópia precisa de análise de licença. O roteador pode cair para fallback e a confiança reportada no fallback merece cuidado | AGPL-3.0-only |
| [Together MoA](https://github.com/togethercomputer/MoA) | Agregação de múltiplos modelos | respostas de referência + agregador; experimentos reproduzíveis | `moa.py` chama quatro modelos em paralelo e depois um agregador: cinco chamadas no exemplo. Aumenta custo/contexto e não deve ser fluxo padrão | Apache-2.0 |
| [HermesAgent-MultiModel](https://github.com/InfiniteWhispers/HermesAgent-MultiModel) | Receita de execução local | seleção de modelos por função, Ollama, cache/KV e limites de co-carregamento | Não é um framework de orquestração de código geral: o topo do repo concentra README, `.hermes/config.yaml` e docs. Documenta alvo de 16 GB VRAM e 48+ GB RAM; não é requisito mínimo universal | MIT |
| [Hermes Hybrid Agent Router](https://github.com/cvsgireesh/hermes-hybrid-agent-router) | Arquitetura local + cloud por risco | local para rascunho, modelo de autoridade para decisão, MoA excepcional, fallback explícito | Repositório pequeno de configuração/documentação e scripts; não presumir maturidade de produção nem copiar sem licença declarada | Nenhuma licença encontrada no diretório raiz consultado |
| [multi-llm-router](https://github.com/IgnacioGentili/multi-llm-router) | Roteamento por complexidade | classificador heurístico sem tokens, fábrica de provedores, módulo de custo | O arquivo `cost.py` consultado diz que seus preços são de dez/2024; dados de preço desatualizados podem comprometer qualquer teto de custo. README chama o projeto de production-ready, mas o tamanho/histórico visto é pequeno: trate como exemplo, não garantia | README declara MIT |
| [Cebus](https://github.com/cebus-ai/cebus) | Chat colaborativo multi-modelo | LangGraph, participantes por provedor, fluxo sequencial vs. paralelo, estrutura TypeScript | O modo “todos ao mesmo tempo” dispara várias chamadas para a mesma pergunta; colaboração não é sinônimo de eficiência | MIT |
| [MatrixLLM](https://github.com/agent-matrix/matrix-llm) | Gateway multi-provedor self-hosted | uma API compatível com OpenAI, conectores isolados, configuração de provedores, API local | É a camada de acesso/roteamento a modelos, não um planejador de equipe multiagente por si só | Apache-2.0 |
| [LiteLLM](https://github.com/BerriAI/litellm) | SDK/gateway e controle operacional | interface unificada, logs de gasto, limites, fallback e observabilidade | Um gateway não decide sozinho qual equipe usar. A documentação alerta que os budgets do proxy requerem banco de dados; não anunciar teto duro sem validar a configuração e o fail-closed | Ver licença e versão atuais do repositório antes de redistribuir |

## 1. PuzldAI — o modelo de componentes mais próximo

**Stack observada:** TypeScript/Node 20+, build com Bun; Fastify/Hono para interfaces HTTP, `ollama` para modelo local, `better-sqlite3` para persistência, LanceDB para busca vetorial, além de adapters e módulos separados para `router`, `orchestrator`, `context`, `memory`, `agentic` e `executor`.

**Roteamento observado:** `src/router/router.ts` usa um modelo local Ollama para devolver JSON com agente, tipo de tarefa e confiança. O orquestrador primeiro respeita um agente forçado; no modo automático usa o router se disponível e depois executa o adapter escolhido. Se o adapter não estiver disponível, tenta fallback.

**Contexto observado:** `src/context/tokens.ts` estima tokens como caracteres/4, utiliza limites por modelo e trunca/divide conteúdo. `src/context/summarizer.ts` resume com Ollama e preserva blocos de código.

**Aprendizados para SOLARIA:** dividir router, adaptadores, contexto e memória é uma boa estrutura; sumarizar só quando necessário evita chamadas desnecessárias. Porém, estimativa caracteres/4 é apenas aproximação, os limites devem vir do catálogo de modelos, e o fallback deve registrar `fallback_reason` e manter a confiança original/indeterminada em vez de transformá-la em confiança 1.0. A licença AGPL-3.0 exige cautela para reutilização direta de código em um projeto com outra licença.

## 2. Mixture-of-Agents — colaboração e custo

**Código examinado:** `moa.py`. A lista de referência contém quatro modelos, chamadas em paralelo usando `asyncio.gather`, cada uma limitada a 512 tokens de saída; depois o agregador recebe o texto de todas as respostas e produz a resposta final.

**Aprendizado:** agregação pode elevar qualidade em tarefas onde perspectivas realmente diferentes ajudam. **Contra:** cinco inferências por resposta no exemplo, maior fan-out, maior latência/custo de entrada no agregador e contexto composto. SOLARIA deve chamar MoA só por política de risco, incerteza/desacordo ou pedido explícito, com máximo de modelos/rodadas.

## 3. HermesAgent-MultiModel — local-first, mas exigente em hardware

O README descreve um setup baseado em Hermes + Ollama, com perfis de planejamento, código, raciocínio e visão. A tabela dá estimativas de VRAM para modelos e avisa que alguns modelos grandes não devem ser carregados juntos em placas de 16 GB. A árvore principal consultada contém configuração e documentação; não é um motor genérico de agentes que SOLARIA deva importar como biblioteca.

**Aprendizado:** usar roles/aliases de modelo e definir explicitamente o orçamento de VRAM/contexto. **Contra:** mais modelos baixados e memória de pesos não significam uso econômico; um único modelo quantizado e sequencial é uma melhor base para a primeira versão.

## 4. Hermes Hybrid Agent Router — roteamento por consequência

O documento `docs/ARCHITECTURE.md` divide tarefas em lanes: local draft/reference, autoridade, perfis especialistas e MoA em decisões de maior consequência. Recomenda que a lane de autoridade falhe explicitamente em vez de cair silenciosamente para um modelo local mais fraco.

**Aprendizado:** a decisão deve considerar o custo de errar, não apenas o texto da pergunta. **Limite da evidência:** é um repositório pequeno de scripts/config/documentação; adotar a ideia, não presumir que exista uma engine pronta.

## 5. multi-llm-router — classificador e custo

O README separa coordinator determinístico, smart router, provider factory e cost tracker. O `router.py` classifica por palavras-chave/complexidade sem uma chamada adicional de LLM. O `cost.py` usa preço por mil tokens e declara atualização de dezembro de 2024.

**Aprendizado:** o roteador de custo zero deve ser a baseline, fácil de testar. **Contra:** heurísticas de palavras-chave não são suficientes sozinhas e os preços não podem permanecer hard-coded/desatualizados. O custo desconhecido tem de bloquear chamada paga no modo estrito, não usar um preço default otimista.

## 6. Cebus — modelos em uma conversa

O README descreve uma aplicação TypeScript com monorepo, Node 24+, LangGraph e modos como “all at once” e “one by one”. Isso atende bem à interação em grupo, mas o fan-out simultâneo chama todos os participantes.

**Aprendizado:** separar a camada de interface da engine e permitir um modo sequencial é útil. **Contra:** um grupo de chat sempre ligado tende a desperdiçar tokens; SOLARIA usa agentes como especialistas acionáveis, não participantes obrigatórios.

## 7. MatrixLLM — camada de provedor

O `pyproject.toml` declara Python 3.10+, FastAPI, httpx, Pydantic Settings, SQLAlchemy/SQLModel e conectores de modelos. O conceito central é um endpoint local compatível com a API OpenAI para conectar Ollama e provedores cloud.

**Aprendizado:** uma interface de provedor comum evita que o restante da aplicação dependa de SDKs individuais. **Contra:** um gateway não deve ser confundido com o workflow de agentes; manteremos router/policy separado do provider adapter.

## 8. LiteLLM — gateway, métricas e limites

O README descreve um SDK e proxy que unifica muitos provedores, com tracking de gasto, fallback, rate limits e chaves virtuais. A documentação de budgets alerta que limites baseados em gasto exigem banco de dados; uma configuração sem banco não deve ser tratada como teto financeiro rígido.

**Aprendizado:** adotar mais tarde como adaptador ou gateway pode acelerar o suporte a providers. **Decisão SOLARIA:** primeiro criar uma política de budget testável dentro da aplicação; se LiteLLM Proxy for usado, testar orçamento/banco/fail-closed antes de confiar nele.

## Padrões adicionais úteis

- **LangGraph subagents:** subagentes podem ser chamados como ferramentas e ter histórico separado; passar um brief reduz crescimento do contexto principal. Referência: [documentação de subagents](https://github.com/langchain-ai/docs/blob/main/src/oss/langchain/multi-agent/subagents.mdx).
- **Pydantic AI:** documenta delegação, handoff programático, gráficos, limites de uso e contextos separados por execução. Referência: [multi-agent applications](https://github.com/pydantic/pydantic-ai/blob/main/docs/multi-agent-applications.md).
- **Ollama:** permite configurar `keep_alive`; `0` descarrega imediatamente e tempos positivos retêm o modelo. Também define limites de modelos carregados e paralelismo. Ajustar conforme o hardware real: [configuração do Ollama](https://github.com/ollama/ollama/blob/main/envconfig/config.go) e [FAQ](https://github.com/ollama/ollama/blob/main/docs/faq.mdx).
- **llama.cpp server:** o router pode carregar/descarregar modelos e o modo sleep descarrega pesos/cache após inatividade: [server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md).

## Síntese: o que SOLARIA deve construir

1. Reutilizar padrões abertos, não copiar um framework inteiro.
2. Um modelo local por vez, paralelismo local padrão igual a 1.
3. Roteamento determinístico sem inferência extra; chamar o classificador de LLM apenas se um experimento provar que compensa.
4. Uma única resposta como caminho padrão; crítico/síntese adicional apenas por política explícita.
5. Contextos isolados e resultados tipados, nunca a conversa inteira por padrão.
6. Catálogo de modelos com custo, capacidade, contexto e memória; preço desconhecido bloqueia cloud sob orçamento estrito.
7. Medir qualidade por testes da tarefa e não usar o próprio modelo como único juiz de si mesmo.
8. Nenhuma ferramenta que modifique sistemas ou execute código sem sandbox e aprovação.
