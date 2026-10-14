# Solaria IA

> **Visão:** integrar múltiplos modelos de IA em uma estrutura colaborativa e interconectada, usando o menor volume de recursos necessário para produzir uma resposta útil, verificável e dentro do orçamento.

Solaria IA é um projeto **local-first** de orquestração adaptativa. Em vez de enviar todas as tarefas a várias IAs, o sistema decide quando uma única chamada basta, quando um especialista deve revisar uma resposta e quais informações cada etapa realmente precisa receber.

**Descrição do projeto:** Projeto de integração entre múltiplas IAs, criando uma estrutura colaborativa e interconectada que potencializa as capacidades de cada modelo. O objetivo é unir o melhor de cada inteligência artificial em um ecossistema eficiente, priorizando modelos locais e opções gratuitas sempre que forem adequados.

> **Importante sobre custos:** modelos locais podem ser executados sem pagar por chamada de API, mas exigem memória, processamento e armazenamento. APIs externas podem cobrar por uso. Por isso, serviços cloud ficam desativados por padrão e só serão incorporados com limites e autorização explícita.

## Estado atual

Este repositório contém o MVP em evolução: API FastAPI, roteamento determinístico, provedor `mock` para testes sem custo, integração local opcional com Ollama e uma interface web inicial. Ainda não existe integração cloud multi-provedor nem um sistema de equipe com vários modelos diferentes em produção.

## Princípios

1. **Roteamento antes de colaboração:** selecionar o fluxo mais simples que atenda à tarefa.
2. **Local-first:** não chamar serviços pagos por padrão.
3. **Orçamento fechado:** não executar chamadas cloud sem autorização e política de orçamento validada.
4. **Contexto mínimo:** repassar a cada especialista somente a tarefa, as restrições e os artefatos relevantes.
5. **Memória controlada:** limitar tamanho do contexto, saída e concorrência.
6. **Encerramento antecipado:** não chamar mais modelos quando os critérios de aceitação forem atingidos.
7. **Falhas visíveis:** registrar a razão da escolha, falha ou escalonamento, sem apresentar certeza artificial.

## O que funciona neste MVP

- `GET /`: interface web inicial.
- `GET /health`: saúde da API e modo de execução.
- `POST /v1/tasks`: resposta em modo mock/local ou fluxo opcional de revisão sequencial.
- Classificação determinística por tipo, complexidade e consequência.
- Fluxos `single` e `review`, com limite de chamadas por execução.
- Provedor `mock` para testes sem custo.
- Integração opcional com Ollama para inferência local.
- Testes automatizados offline e workflow de CI no GitHub Actions.

A interface web permite escrever uma tarefa, selecionar `auto`, `single` ou `review`, ver a resposta, o tempo total, o provedor/modelo e as etapas da execução. O MVP não persiste histórico.

## Requisitos

- Python 3.11 ou superior.
- Git para versionamento.
- Opcional: [Ollama](https://ollama.com/) e um modelo compatível com o hardware da máquina.

## Instalação local (Windows PowerShell)

Na pasta raiz do repositório:

```powershell
py -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
python -m pytest -q
python -m uvicorn solaria_ia.main:app --reload
```

Em macOS/Linux, ative o ambiente com `source .venv/bin/activate` depois de criar `.venv` e copie a configuração com `cp .env.example .env`.

Com o servidor em execução, abra:

- Interface web: `http://127.0.0.1:8000/`
- Documentação interativa da API: `http://127.0.0.1:8000/docs`
- Saúde da API: `http://127.0.0.1:8000/health`

No GitHub Codespaces, inicie o Uvicorn na porta 8000 e abra a porta encaminhada pelo painel **Ports** do Codespaces. A interface e a API usam a mesma origem.

O modo inicial é `mock`, portanto os primeiros testes não enviam dados a serviços externos.

## Ativar modelo local via Ollama

1. Instale o Ollama e inicie o serviço.
2. Baixe **um modelo que caiba na RAM/VRAM disponível**. Confirme a tag na biblioteca oficial antes de usar. Exemplo:

```bash
ollama pull qwen3:1.7b
```

3. No arquivo `.env`, ajuste os campos para o modelo baixado:

```dotenv
SOLARIA_PROVIDER_MODE=ollama
SOLARIA_OLLAMA_MODEL=qwen3:1.7b
SOLARIA_OLLAMA_BASE_URL=http://localhost:11434
SOLARIA_OLLAMA_KEEP_ALIVE=5m
```

`KEEP_ALIVE=0` solicita o descarregamento do modelo após a execução; isso libera memória, mas geralmente aumenta o tempo da chamada seguinte, pois o modelo precisa ser carregado novamente. Um valor como `5m` mantém o modelo carregado por até cinco minutos desde a última utilização.

Inicie o Ollama em uma terminal e a API em outra. Se o ambiente for reiniciado, os serviços poderão precisar ser iniciados novamente, mas o modelo baixado normalmente permanece no armazenamento do Codespace.

## Primeiro teste

Use a interface web em `http://127.0.0.1:8000/` e escolha a estratégia de execução. Alternativamente, envie uma tarefa pela documentação em `/docs`, usando `POST /v1/tasks`, ou execute:

```bash
curl -sS -X POST http://127.0.0.1:8000/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{"task":"Explique Kanban em quatro tópicos","collaboration":"single","privacy":"local_only"}'
```

## Arquitetura (resumo)

```text
Usuário
  -> Interface web ou cliente de API
  -> API e validação de limites
  -> Classificador determinístico (sem chamada de IA)
  -> Motor de políticas
  -> Fluxo single ou revisão sequencial, se necessário
  -> Provedor mock/local
  -> Resultado + métricas + justificativa da rota
```

A colaboração com diversos provedores, o guardião de orçamento cloud e a memória persistente serão acrescentados somente após a validação dos limites, testes e métricas do MVP.

## Estrutura do repositório

```text
src/solaria_ia/       # API, políticas, orquestração, provedores e interface web
tests/                # testes automatizados
configs/              # exemplo de catálogo de modelos
docs/                 # arquitetura, engenharia reversa e roadmap
.github/              # CI, modelos de Issues e Pull Requests
```

## Roadmap

1. Executar e medir um modelo local em tarefas representativas.
2. Melhorar roteamento, limites de contexto e rastreamento de recursos.
3. Persistir métricas mínimas de execução sem guardar conversas por padrão.
4. Implementar guardião financeiro antes de qualquer integração paga.
5. Adicionar provedores adicionais e colaboração condicional, comparando ganho de qualidade versus custo/latência.
6. Aprimorar a interface e avaliar memória de longo prazo apenas quando houver necessidade demonstrada.

Veja [docs/REVERSE_ENGINEERING.md](docs/REVERSE_ENGINEERING.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) e [docs/ROADMAP.md](docs/ROADMAP.md).

## Segurança

- Nunca comite `.env`, chaves de API, senhas ou dados privados.
- Mantenha o serviço em `localhost` durante o desenvolvimento.
- Não habilite execução autônoma de shell/código sem sandbox, permissões, auditoria e confirmação humana.
- Não envie tarefas privadas para provedores externos sem autorização explícita.

## Licença

Este scaffold está sob licença MIT. Cada dependência e cada modelo baixado conserva seus próprios termos e licenças.
