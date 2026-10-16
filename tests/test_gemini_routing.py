import pytest

from solaria_ia.orchestration.service import (
    OrchestrationError,
    QuotaExceededError,
    TaskService,
)
from solaria_ia.providers.base import Generation
from solaria_ia.providers.usage_ledger import DailyUsageLedger
from solaria_ia.schemas import TaskRequest
from solaria_ia.settings import Settings


class StubProvider:
    def __init__(self, name, model, response):
        self.name = name
        self.model = model
        self.response = response
        self.calls = []

    async def generate(self, *, system_prompt, user_prompt, max_output_tokens):
        self.calls.append((system_prompt, user_prompt, max_output_tokens))
        return Generation(
            text=self.response,
            input_tokens_estimated=20,
            output_tokens_estimated=max(1, len(self.response) // 4),
            provider=self.name,
            model=self.model,
        )


def make_settings(**overrides):
    values = {
        "provider_mode": "ollama",
        "review_provider": "gemini",
        "gemini_enabled": True,
        "gemini_free_tier_confirmed": True,
        "gemini_api_key": "fake-test-key",
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.asyncio
async def test_local_only_never_calls_gemini(tmp_path):
    settings = make_settings()
    primary = StubProvider("ollama", "qwen3:1.7b", "Rascunho inicial.")
    local_reviewer = StubProvider("ollama", "gemma3:1b", "APPROVED")
    external = StubProvider("gemini", settings.gemini_model, "APPROVED")
    ledger = DailyUsageLedger(str(tmp_path / "usage.sqlite3"))

    service = TaskService(
        settings,
        primary,
        reviewer_provider=local_reviewer,
        external_reviewer_provider=external,
        usage_ledger=ledger,
    )

    result = await service.run(
        TaskRequest(
            task="Explique Kanban",
            collaboration="review",
            privacy="local_only",
        )
    )

    assert [step.model for step in result.steps] == [
        "qwen3:1.7b",
        "gemma3:1b",
    ]
    assert external.calls == []
    assert len(local_reviewer.calls) == 1


@pytest.mark.asyncio
async def test_gemini_confirmation_is_required_before_any_model_call(tmp_path):
    settings = make_settings(gemini_free_tier_confirmed=False)
    primary = StubProvider("ollama", "qwen3:1.7b", "Rascunho inicial.")
    local_reviewer = StubProvider("ollama", "gemma3:1b", "APPROVED")
    external = StubProvider("gemini", settings.gemini_model, "APPROVED")

    service = TaskService(
        settings,
        primary,
        reviewer_provider=local_reviewer,
        external_reviewer_provider=external,
        usage_ledger=DailyUsageLedger(str(tmp_path / "usage.sqlite3")),
    )

    with pytest.raises(OrchestrationError, match="Confirme o acesso gratuito"):
        await service.run(
            TaskRequest(
                task="Explique Kanban",
                collaboration="review",
                privacy="standard",
            )
        )

    assert primary.calls == []
    assert external.calls == []


@pytest.mark.asyncio
async def test_gemini_usage_is_recorded_after_authorized_review(tmp_path):
    settings = make_settings()
    primary = StubProvider("ollama", "qwen3:1.7b", "Rascunho inicial.")
    local_reviewer = StubProvider("ollama", "gemma3:1b", "APPROVED")
    external = StubProvider("gemini", settings.gemini_model, "APPROVED")
    ledger = DailyUsageLedger(str(tmp_path / "usage.sqlite3"))

    service = TaskService(
        settings,
        primary,
        reviewer_provider=local_reviewer,
        external_reviewer_provider=external,
        usage_ledger=ledger,
    )

    result = await service.run(
        TaskRequest(
            task="Explique Kanban",
            collaboration="review",
            privacy="standard",
        )
    )

    assert [step.model for step in result.steps] == [
        "qwen3:1.7b",
        settings.gemini_model,
    ]
    assert local_reviewer.calls == []
    assert len(external.calls) == 1

    usage = ledger.usage("gemini")
    assert usage["calls"] == 1
    assert usage["tokens_used"] > 0
    assert usage["tokens_reserved"] == 0


@pytest.mark.asyncio
async def test_gemini_daily_call_limit_blocks_external_call(tmp_path):
    settings = make_settings(gemini_daily_call_limit=0)
    primary = StubProvider("ollama", "qwen3:1.7b", "Rascunho inicial.")
    local_reviewer = StubProvider("ollama", "gemma3:1b", "APPROVED")
    external = StubProvider("gemini", settings.gemini_model, "APPROVED")
    ledger = DailyUsageLedger(str(tmp_path / "usage.sqlite3"))

    service = TaskService(
        settings,
        primary,
        reviewer_provider=local_reviewer,
        external_reviewer_provider=external,
        usage_ledger=ledger,
    )

    with pytest.raises(QuotaExceededError, match="Limite diário"):
        await service.run(
            TaskRequest(
                task="Explique Kanban",
                collaboration="review",
                privacy="standard",
            )
        )

    assert len(primary.calls) == 1
    assert external.calls == []
    assert ledger.usage("gemini")["tokens_reserved"] == 0


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {"copilot_enabled": False, "copilot_free_tier_confirmed": True},
            "GitHub Copilot está desativado",
        ),
        (
            {"copilot_enabled": True, "copilot_free_tier_confirmed": False},
            "Confirme o acesso gratuito",
        ),
        (
            {"copilot_enabled": True, "copilot_free_tier_confirmed": True},
            "adaptador GitHub Copilot ainda não está implementado",
        ),
    ],
)
@pytest.mark.asyncio
async def test_copilot_selection_fails_closed_before_any_model_call(tmp_path, overrides, message):
    settings = make_settings(review_provider="copilot", **overrides)
    primary = StubProvider("ollama", "qwen3:1.7b", "Rascunho inicial.")
    local_reviewer = StubProvider("ollama", "gemma3:1b", "APPROVED")

    service = TaskService(
        settings,
        primary,
        reviewer_provider=local_reviewer,
    )

    with pytest.raises(OrchestrationError, match=message):
        await service.run(
            TaskRequest(
                task="Explique Kanban",
                collaboration="review",
                privacy="standard",
            )
        )

    assert primary.calls == []
    assert local_reviewer.calls == []


@pytest.mark.asyncio
async def test_local_only_uses_local_reviewer_when_copilot_is_selected():
    settings = make_settings(
        review_provider="copilot",
        copilot_enabled=True,
        copilot_free_tier_confirmed=True,
    )
    primary = StubProvider("ollama", "qwen3:1.7b", "Rascunho inicial.")
    local_reviewer = StubProvider("ollama", "gemma3:1b", "APPROVED")

    service = TaskService(
        settings,
        primary,
        reviewer_provider=local_reviewer,
    )

    result = await service.run(
        TaskRequest(
            task="Explique Kanban",
            collaboration="review",
            privacy="local_only",
        )
    )

    assert len(primary.calls) == 1
    assert len(local_reviewer.calls) == 1
    assert all(step.provider == "ollama" for step in result.steps)
