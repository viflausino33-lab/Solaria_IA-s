import httpx
import pytest

from solaria_ia.providers.gemini import GeminiError, GeminiProvider
from solaria_ia.settings import Settings


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request(
                "POST",
                "https://generativelanguage.googleapis.com",
            )
            response = httpx.Response(
                self.status_code,
                request=request,
                json=self.payload,
            )
            raise httpx.HTTPStatusError(
                "HTTP error",
                request=request,
                response=response,
            )

    def json(self):
        return self.payload


class FakeAsyncClient:
    def __init__(self, payload, status_code=200, captured=None):
        self.payload = payload
        self.status_code = status_code
        self.captured = captured

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False

    async def post(self, url, *, headers, json):
        if self.captured is not None:
            self.captured.update(url=url, headers=headers, json=json)
        return FakeResponse(self.payload, self.status_code)


@pytest.mark.asyncio
async def test_gemini_provider_returns_text_and_usage(monkeypatch):
    captured = {}
    payload = {
        "candidates": [
            {
                "content": {"parts": [{"text": "Resposta do Gemini."}]},
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 12,
            "candidatesTokenCount": 5,
        },
    }

    monkeypatch.setattr(
        "solaria_ia.providers.gemini.httpx.AsyncClient",
        lambda **kwargs: FakeAsyncClient(payload, captured=captured),
    )

    settings = Settings(
        provider_mode="mock",
        gemini_enabled=True,
        gemini_free_tier_confirmed=True,
        gemini_api_key="fake-test-key",
        gemini_model="gemini-3.5-flash-lite",
    )
    provider = GeminiProvider(settings)

    result = await provider.generate(
        system_prompt="Responda em português.",
        user_prompt="Explique Kanban.",
        max_output_tokens=160,
    )

    assert result.text == "Resposta do Gemini."
    assert result.provider == "gemini"
    assert result.model == "gemini-3.5-flash-lite"
    assert result.input_tokens_estimated == 12
    assert result.output_tokens_estimated == 5
    assert captured["headers"]["x-goog-api-key"] == "fake-test-key"
    assert captured["json"]["generationConfig"]["maxOutputTokens"] == 160


@pytest.mark.asyncio
async def test_gemini_provider_is_disabled_by_default():
    provider = GeminiProvider(Settings(provider_mode="mock"))

    with pytest.raises(GeminiError, match="desativado"):
        await provider.generate(
            system_prompt="Sistema.",
            user_prompt="Tarefa.",
            max_output_tokens=100,
        )


@pytest.mark.asyncio
async def test_gemini_provider_stops_when_quota_is_exhausted(monkeypatch):
    monkeypatch.setattr(
        "solaria_ia.providers.gemini.httpx.AsyncClient",
        lambda **kwargs: FakeAsyncClient(
            {"error": {"message": "RESOURCE_EXHAUSTED"}},
            status_code=429,
        ),
    )

    provider = GeminiProvider(
        Settings(
            provider_mode="mock",
            gemini_enabled=True,
            gemini_free_tier_confirmed=True,
            gemini_api_key="fake-test-key",
        )
    )

    with pytest.raises(GeminiError, match="cota ou o limite"):
        await provider.generate(
            system_prompt="Sistema.",
            user_prompt="Tarefa.",
            max_output_tokens=100,
        )
