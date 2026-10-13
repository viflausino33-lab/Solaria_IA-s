from solaria_ia.schemas import RouteDecision, TaskRequest
from solaria_ia.settings import Settings


HIGH_CONSEQUENCE = {
    "production", "produção", "deploy", "deployment", "delete", "deletar", "apagar",
    "payment", "pagamento", "financial", "financeiro", "legal", "contrato",
    "security", "segurança", "credential", "credencial", "database migration", "migração",
}
CODING = {"code", "código", "python", "bug", "debug", "function", "função", "api", "refactor", "refatorar", "testes"}
RESEARCH = {"pesquise", "pesquisa", "research", "fontes", "referências", "latest", "atual", "comparar", "compare", "literature"}
ANALYSIS = {"analise", "análise", "evaluate", "avaliar", "trade-off", "tradeoff", "risco", "impacto", "otimizar", "optimization"}
PLANNING = {"planeje", "planejamento", "roadmap", "etapas", "estratégia", "strategy", "arquitetura", "architecture"}


def _contains(text: str, words: set[str]) -> bool:
    normalized = text.casefold()
    return any(word in normalized for word in words)


def classify_task(request: TaskRequest, settings: Settings) -> RouteDecision:
    """Cheap, deterministic baseline. This must not make a model call."""
    task = request.task
    lower = task.casefold()

    if _contains(lower, CODING):
        task_type = "coding"
    elif _contains(lower, RESEARCH):
        task_type = "research"
    elif _contains(lower, ANALYSIS):
        task_type = "analysis"
    elif _contains(lower, PLANNING):
        task_type = "planning"
    else:
        task_type = "general"

    score = 0
    if len(task) > 1_500:
        score += 1
    if len(task) > 5_000:
        score += 1
    if task.count("\n") >= 8:
        score += 1
    if _contains(lower, {"step by step", "passo a passo", "comprehensive", "detalhado", "prove", "demonstre", "architecture", "arquitetura"}):
        score += 1
    if _contains(lower, HIGH_CONSEQUENCE):
        score += 1
    complexity = "low" if score <= 1 else ("medium" if score <= 3 else "high")
    consequence = "high" if _contains(lower, HIGH_CONSEQUENCE) else ("medium" if task_type in {"coding", "research", "analysis", "planning"} else "low")

    if request.collaboration == "single":
        collaboration = "single"
        reason = "modo single solicitado explicitamente; nenhuma chamada de crítica será feita"
    elif request.collaboration == "review":
        collaboration = "review"
        reason = "modo review solicitado; fluxo sequencial limitado a no máximo 3 chamadas"
    elif consequence == "high":
        collaboration = "review"
        reason = "consequência alta aciona revisão sequencial, mesmo se a tarefa parecer curta"
    else:
        collaboration = "single"
        reason = "uma única chamada é a opção padrão; não há evidência suficiente para justificar custo extra"

    if request.privacy == "local_only":
        reason += "; privacidade local-only respeitada"

    return RouteDecision(
        task_type=task_type,
        complexity=complexity,
        consequence=consequence,
        provider=settings.provider_mode,
        model=settings.ollama_model if settings.provider_mode == "ollama" else "mock-v1",
        collaboration=collaboration,
        reason=reason,
    )
