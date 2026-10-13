# Solaria IA

> **Visão:** integrar múltiplos modelos de IA em uma estrutura colaborativa e interconectada, usando o menor volume de recursos necessário para produzir uma resposta útil, verificável e dentro do orçamento.

Solaria IA é um projeto **local-first** de orquestração adaptativa. Em vez de enviar todas as tarefas a várias IAs, o sistema decide quando uma única chamada basta, quando um especialista deve revisar uma resposta e quais informações cada etapa realmente precisa receber.

**Descrição do projeto:** Projeto de integração entre múltiplas IAs, criando uma estrutura colaborativa e interconectada que potencializa as capacidades de cada modelo. O objetivo é unir o melhor de cada inteligência artificial em um ecossistema eficiente, priorizando modelos locais e opções gratuitas sempre que forem adequados.

> **Importante sobre custos:** modelos locais podem ser executados sem pagar por chamada de API, mas exigem memória, processamento e armazenamento. APIs externas podem cobrar por uso. Por isso, serviços cloud ficam desativados por padrão e só serão incorporados com limites e autorização explícita.

## Estado atual

Este repositório contém o scaffold/MVP inicial: API FastAPI, roteamento determinístico, provedor `mock` para testes sem custo e integração local opcional com Ollama. Ainda não existe integração cloud multi-provedor nem um sistema de equipe com vários modelos diferentes em produção.

## Princípios

1. **Roteamento antes de colaboração:** selecionar o fluxo mais simples que atenda à tarefa.
2. **Local-first:** não chamar serviços pagos por padrão.
3. **Orçamento fechado:** não executar chamadas cloud sem autorização e política de orçamento validada.
4. **Contexto mínimo:** repassar a cada especialista somente a tarefa, as restrições e os artefatos relevantes.
5. **Memória controlada:** limitar tamanho do contexto, saída e concorrência.
6. **Encerramento antecipado:** não chamar mais modelos quando os critérios de aceitação forem atingidos.
7. **Falhas visíveis:** registrar a razão da escolha, falha ou escalonamento, sem apresentar certeza artificial.

## O que funciona neste scaffold

- `GET /health`: saúde da API e modo de execução.
- `POST /v1/tasks`: uma resposta em modo mock/local ou fluxo opcional de revisão sequencial.
- Classificação determinística por tipo, complexidade e consequência.
- Fluxos `single` e `review`, com limite de chamadas por execução.
- Provedor `mock` padrão, que não utiliza rede nem credenciais.
- Integração opcional com Ollama para inferência local.
- Testes automatizados offline e workflow de CI no GitHub Actions.

## Requisitos

- Python 3.11 ou superior.
- Git para versionamento.
- Opcional: [Ollama](https://ollama.com/) e um modelo compatível com o hardware da máquina.

## Instalação local (Windows PowerShell)

Na pasta raiz do repositório:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
pytest
uvicorn solaria_ia.main:app --reload
```

Em macOS/Linux, ative o ambiente com `source .venv/bin/activate` depois de criar `.venv` e copie a configuração com `cp .env.example .env`.

A API estará em `http://127.0.0.1:8000`; a documentação interativa fica em `http://127.0.0.1:8000/docs`. O modo inicial é `mock`, portanto os primeiros testes não enviam dados a serviços externos.

## Ativar modelo local via Ollama

1. Instale o Ollama e inicie o serviço.
2. Baixe **um modelo que caiba na RAM/VRAM disponível**. Exemplo, confirme a tag na biblioteca oficial antes de usar:

```powershell
ollama pull qwen3:4b
```

3. No arquivo `.env`, ajuste:

```dotenv
SOLARIA_PROVIDER_MODE=ollama
SOLARIA_OLLAMA_MODEL=qwen3:4b
SOLARIA_OLLAMA_BASE_URL=http://localhost:11434
SOLARIA_OLLAMA_KEEP_ALIVE=0
```

`KEEP_ALIVE=0` solicita o descarregamento do modelo após a execução; isso pode liberar memória, mas costuma aumentar o tempo da chamada seguinte porque o modelo precisa ser carregado novamente. Escolha conforme sua máquina e uso.

## Primeiro teste

Envie uma tarefa pela interface em `http://127.0.0.1:8000/docs` usando `POST /v1/tasks`, ou execute:

```powershell
curl.exe -X POST http://127.0.0.1:8000/v1/tasks `
  -H "Content-Type: application/json" `
  -d '{"task":"Explique o Kanban em quatro tópicos", "collaboration":"single"}'
```

## Arquitetura (resumo)

```text
Usuário
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
src/solaria_ia/       # API, políticas, orquestração e provedores
 tests/               # testes automatizados
 configs/             # exemplo de catálogo de modelos
 docs/                # arquitetura, engenharia reversa e roadmap
 .github/             # CI, modelos de Issues e Pull Requests
```

## Roadmap

1. Executar e medir um modelo local em tarefas representativas.
2. Melhorar roteamento, limites de contexto e rastreamento de recursos.
3. Persistir métricas mínimas de execução sem guardar conversas por padrão.
4. Implementar guardião financeiro antes de qualquer integração paga.
5. Adicionar colaboração multiagente condicional e comparar ganho de qualidade versus custo/latência.
6. Avaliar memória de longo prazo, ferramentas e interface apenas quando houver caso de uso demonstrado.

Veja [docs/REVERSE_ENGINEERING.md](docs/REVERSE_ENGINEERING.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) e [docs/ROADMAP.md](docs/ROADMAP.md).

## Segurança

- Nunca comite `.env`, chaves de API, senhas ou dados privados.
- Mantenha o serviço em `localhost` durante o desenvolvimento.
- Não habilite execução autônoma de shell/código sem sandbox, permissões, auditoria e confirmação humana.
- Não envie tarefas privadas para provedores externos sem autorização explícita.

## Licença

Este scaffold está sob licença MIT. Cada dependência e cada modelo baixado conserva seus próprios termos e licenças.
