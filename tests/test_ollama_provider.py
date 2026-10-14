import pytest

from solaria_ia.providers.ollama import OllamaError, OllamaProvider
from solaria_ia.settings import Settings


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class FakeAsyncClient:
    def __init__(self, payload):
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False

    async def post(self, url, json):
        return FakeResponse(self.payload)


@pytest.mark.asyncio
async def test_ollama_provider_rejects_truncated_generation(monkeypatch):
    payload = {
        "done_reason": "length",
        "message": {"content": "Resposta incompleta"},
        "prompt_eval_count": 20,
        "eval_count": 300,
    }

    monkeypatch.setattr(
        "solaria_ia.providers.ollama.httpx.AsyncClient",
        lambda **kwargs: FakeAsyncClient(payload),
    )

    provider = OllamaProvider(
        Settings(
            provider_mode="ollama",
            ollama_model="qwen3:1.7b",
        )
    )

    with pytest.raises(OllamaError, match="resposta foi truncada"):
        await provider.generate(
            system_prompt="Responda com precisão.",
            user_prompt="Explique o Kanban.",
            max_output_tokens=300,
        )
