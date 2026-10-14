import pytest

from solaria_ia.orchestration.service import TaskService
from solaria_ia.providers.base import Generation
from solaria_ia.schemas import TaskRequest
from solaria_ia.settings import Settings


class CountingProvider:
    name = "mock"
    model = "mock-test"

    def __init__(
        self,
        critic_response="**APPROVED** — sem correções materiais.",
    ):
        self.calls = []
        self.critic_response = critic_response

    async def generate(self, *, system_prompt, user_prompt, max_output_tokens):
        self.calls.append((system_prompt, user_prompt, max_output_tokens))

        if system_prompt.startswith("Você é um revisor"):
            text = self.critic_response
        else:
            text = "Resposta de teste."

        return Generation(text, 10, 5, self.name, self.model)


@pytest.mark.asyncio
async def test_single_mode_only_calls_provider_once():
    provider = CountingProvider()
    service = TaskService(Settings(provider_mode="mock"), provider)
    result = await service.run(TaskRequest(task="Explique Kanban", collaboration="single"))
    assert len(provider.calls) == 1
    assert len(result.steps) == 1


@pytest.mark.asyncio
async def test_review_stops_after_approved_critic():
    provider = CountingProvider()
    service = TaskService(Settings(provider_mode="mock"), provider)
    result = await service.run(TaskRequest(task="Explique Kanban", collaboration="review"))
    assert len(provider.calls) == 2
    assert [step.role for step in result.steps] == ["specialist", "critic"]
    assert "crítico marcou APPROVED" in result.route.reason


@pytest.mark.asyncio
async def test_review_uses_dedicated_reviewer_with_limited_tokens():
    primary = CountingProvider()
    primary.model = "qwen3:1.7b"

    reviewer = CountingProvider()
    reviewer.model = "gemma3:1b"

    settings = Settings(
        provider_mode="mock",
        max_output_tokens=800,
        review_max_output_tokens=160,
    )
    service = TaskService(
        settings,
        primary,
        reviewer_provider=reviewer,
    )

    result = await service.run(TaskRequest(task="Explique Kanban", collaboration="review"))

    assert [step.model for step in result.steps] == [
        "qwen3:1.7b",
        "gemma3:1b",
    ]
    assert [step.role for step in result.steps] == ["specialist", "critic"]
    assert len(primary.calls) == 1
    assert len(reviewer.calls) == 1
    assert reviewer.calls[0][2] == 160


@pytest.mark.asyncio
async def test_revision_returns_to_primary_provider():
    primary = CountingProvider()
    primary.model = "qwen3:1.7b"

    reviewer = CountingProvider(critic_response="REVISE\\n- Corrigir uma omissão importante.")
    reviewer.model = "gemma3:1b"

    service = TaskService(
        Settings(
            provider_mode="mock",
            max_output_tokens=800,
            review_max_output_tokens=160,
        ),
        primary,
        reviewer_provider=reviewer,
    )

    result = await service.run(TaskRequest(task="Explique Kanban", collaboration="review"))

    assert [step.model for step in result.steps] == [
        "qwen3:1.7b",
        "gemma3:1b",
        "qwen3:1.7b",
    ]
    assert [step.role for step in result.steps] == [
        "specialist",
        "critic",
        "synthesizer",
    ]
    assert len(primary.calls) == 2
    assert len(reviewer.calls) == 1


@pytest.mark.asyncio
async def test_input_limit_rejects_before_provider_call():
    provider = CountingProvider()
    settings = Settings(provider_mode="mock", max_input_chars=500)
    service = TaskService(settings, provider)
    with pytest.raises(ValueError):
        await service.run(TaskRequest(task="x" * 501))
    assert provider.calls == []


@pytest.mark.asyncio
async def test_review_runs_synthesis_when_critic_requests_revision():
    provider = CountingProvider(
        critic_response=("REVISE\n- Especifique uma medida preventiva concreta.")
    )
    service = TaskService(Settings(provider_mode="mock"), provider)

    result = await service.run(
        TaskRequest(
            task="Explique Kanban",
            collaboration="review",
        )
    )

    assert len(provider.calls) == 3
    assert [step.role for step in result.steps] == [
        "specialist",
        "critic",
        "synthesizer",
    ]
    assert result.answer == "Resposta de teste."
    assert "crítico marcou REVISE" in result.route.reason


@pytest.mark.asyncio
async def test_review_synthesizes_when_critic_marker_is_unknown():
    provider = CountingProvider(
        critic_response="A resposta parece adequada, mas tenho uma observação."
    )
    service = TaskService(Settings(provider_mode="mock"), provider)

    result = await service.run(
        TaskRequest(
            task="Explique Kanban",
            collaboration="review",
        )
    )

    assert len(provider.calls) == 3
    assert "marcador do crítico inválido ou ausente" in result.route.reason
