from fastapi import FastAPI, HTTPException

from solaria_ia.orchestration.service import OrchestrationError, TaskService
from solaria_ia.providers.mock import MockProvider
from solaria_ia.providers.ollama import OllamaError, OllamaProvider
from solaria_ia.schemas import TaskRequest, TaskResponse
from solaria_ia.settings import get_settings

settings = get_settings()
app = FastAPI(
    title="Solaria IA",
    version="0.1.0",
    description="Orquestração local-first com roteamento enxuto e colaboração condicional.",
)
provider = MockProvider() if settings.provider_mode == "mock" else OllamaProvider(settings)
service = TaskService(settings=settings, provider=provider)


@app.get("/health")
def health() -> dict[str, str | int]:
    return {
        "status": "ok",
        "provider_mode": settings.provider_mode,
        "model": settings.ollama_model if settings.provider_mode == "ollama" else "mock-v1",
        "local_parallelism": settings.local_parallelism,
        "max_calls_per_run": settings.max_calls_per_run,
    }


@app.post("/v1/tasks", response_model=TaskResponse)
async def create_task(request: TaskRequest) -> TaskResponse:
    try:
        return await service.run(request)
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except OrchestrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OllamaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # no silent fallback to a paid provider
        raise HTTPException(status_code=500, detail="Falha interna; nenhuma troca automática de provedor foi realizada.") from exc
