
from fastapi.testclient import TestClient

import solaria_ia.main as main
from solaria_ia.providers.ollama import OllamaError


class FailingService:
    async def run(self, request):
        raise OllamaError(
            "Ollama atingiu o limite de 300 tokens; a resposta foi truncada."
        )


def test_truncated_response_is_reported_as_error(monkeypatch):
    monkeypatch.setattr(main, "service", FailingService())
    client = TestClient(main.app)

    response = client.post(
        "/v1/tasks",
        json={
            "task": "Explique o Kanban",
            "collaboration": "single",
            "privacy": "local_only",
        },
    )

    assert response.status_code == 502
    assert "resposta foi truncada" in response.json()["detail"]
