# Roadmap com critérios de aceite

## Fase 0 — base técnica (este scaffold)

- [x] Contratos da API e classificação inicial.
- [x] Modo mock sem rede/credenciais.
- [x] Adapter local Ollama.
- [x] Fluxo single e revisão sequencial opcional.
- [x] Testes offline e CI.
- [x] Documentação da engenharia reversa.

**Aceite:** testes passam; comportamento sem modelo disponível falha de forma explícita; nenhuma chamada cloud ocorre.

## Fase 1 — executar e medir localmente

- [ ] Rodar com um único modelo local e registrar latência.
- [ ] Medir RAM/VRAM em 20 tarefas pequenas/médias; medir reload com keep-alive 0/60s/5m.
- [ ] Construir conjunto inicial de 30 tarefas de teste (general, coding, research, reasoning, private).
- [ ] Definir rubrica de qualidade com avaliações humanas/resultado verificável.
- [ ] Estabelecer baseline “uma chamada local por tarefa”.

**Aceite:** relatório reproduzível de tempo, estimativa de tokens, pico de memória, acurácia de classificação e qualidade; resultados não devem depender de benchmarking não controlado.

## Fase 2 — política e orquestração testáveis

- [ ] Separar `TaskClassifier`, `PolicyEngine`, `WorkflowPlanner` e `ContextBuilder` em módulos estáveis.
- [ ] Declarar `max_calls_per_run`, `max_output_tokens`, `max_context_tokens`, `privacy_mode` e limite local de concorrência.
- [ ] Criar tests for high-risk trigger, private/local-only and resource cap.
- [ ] Introduzir execução de workflow com artifact structs tipados, não mensagens soltas.

**Aceite:** rotas são determinísticas e explicáveis; cada chamada extra tem um motivo registrado.

## Fase 3 — memória de execução e contexto

- [ ] SQLite para run/step ledger, sem persistir prompts por padrão.
- [ ] Resumo condicionado ao tamanho/limite de contexto.
- [ ] Contexto isolado de cada especialista.
- [ ] Métricas de compressão e teste de perda de informação.

**Aceite:** contextos maiores não crescem linearmente com todo o histórico; saída de resumo é validada em um conjunto de casos.

## Fase 4 — primeiro modelo cloud com controle financeiro

- [ ] Escolher um provider e um modelo econômico por tarefa, não vários.
- [ ] Implementar chamada explícita (ex.: LiteLLM SDK), guardião de orçamento e registro de uso real.
- [ ] Criar price catalogue datado e script/teste para detectar preço desconhecido.
- [ ] Testar bloqueio antes da chamada, falha de rede, retorno sem usage, retry e fallback.
- [ ] Manter `ALLOW_CLOUD=false` por padrão até passar testes.

**Aceite:** nenhuma chamada paga é feita se `external_allowed` for falso, preço ausente ou budget insuficiente; o limite é testado sob duas requisições concorrentes.

## Fase 5 — colaboração multiagente condicional

- [ ] Introduzir papéis de planner, specialist e critic como contratos de saída.
- [ ] Usar agentes diferentes somente onde os testes demonstrarem ganho.
- [ ] Começar sequencial; paralelismo é opt-in e limitado (ex.: máximo 2).
- [ ] Early stopping quando a validação passa ou orçamento acaba.
- [ ] Comparar single-agent vs. critic vs. MoA em qualidade/custo/latência.

**Aceite:** a melhoria de qualidade do fluxo colaborativo é maior que o custo/latência incremental segundo critérios publicados.

## Fase 6 — RAG e memória de longo prazo

- [ ] Só se casos de uso exigirem memória entre sessões.
- [ ] Indexar artefatos locais com exclusão de segredos e políticas de retenção.
- [ ] Recuperar trechos relevantes, com fonte e limite de quantidade.
- [ ] Testar precisão/recall de recuperação e vazamento de dados entre usuários/sessões.

**Aceite:** demonstra valor frente a não ter RAG; não indexar todo chat automaticamente.

## Fase 7 — segurança de ferramentas

- [ ] Ferramentas em allowlist; nenhum shell genérico.
- [ ] Sandbox para código, timeout, limite de memória/rede/arquivos.
- [ ] Confirmação humana para operações destrutivas/externas.
- [ ] Prompt injection tests e auditoria de permissões.

**Aceite:** testes de isolamento e fail-safe antes de habilitar agentes que atuam no ambiente.

## Fase 8 — UI e distribuição (somente depois)

- [ ] CLI ou UI leve se melhorar o fluxo de desenvolvimento.
- [ ] Sem transformar o projeto em comparador de modelos.
- [ ] Interface mostra “por que este modelo foi escolhido”, uso, limite e passos efetuados.

**Aceite:** a UI ajuda a operar a engine, mas não substitui o foco no roteamento econômico e na colaboração.
