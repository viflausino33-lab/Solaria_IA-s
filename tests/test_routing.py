from solaria_ia.routing.policy import classify_task
from solaria_ia.schemas import TaskRequest
from solaria_ia.settings import Settings


def test_simple_task_uses_single_call_by_default():
    settings = Settings(provider_mode="mock")
    route = classify_task(TaskRequest(task="O que é Kanban?"), settings)
    assert route.collaboration == "single"
    assert route.provider == "mock"


def test_explicit_review_is_respected():
    settings = Settings(provider_mode="mock")
    route = classify_task(
        TaskRequest(task="Explique uma estratégia", collaboration="review"), settings
    )
    assert route.collaboration == "review"
    assert "solicitado" in route.reason


def test_high_consequence_long_task_routes_to_review():
    settings = Settings(provider_mode="mock")
    task = "Planeje uma migração de banco de dados de produção com segurança. " + (
        "Detalhe e valide cada etapa.\n" * 30
    )
    route = classify_task(TaskRequest(task=task), settings)
    assert route.consequence == "high"
    assert route.collaboration == "review"


def test_local_only_does_not_change_provider_to_cloud():
    settings = Settings(provider_mode="ollama")
    route = classify_task(TaskRequest(task="Analise um bug", privacy="local_only"), settings)
    assert route.provider == "ollama"
    assert route.model == settings.ollama_model
