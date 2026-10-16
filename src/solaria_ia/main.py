import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from solaria_ia.orchestration.service import (
    OrchestrationError,
    QuotaExceededError,
    TaskService,
)
from solaria_ia.providers.copilot import (
    CopilotError,
    CopilotProvider,
    CopilotQuotaError,
)
from solaria_ia.providers.gemini import (
    GeminiError,
    GeminiProvider,
    GeminiQuotaError,
)
from solaria_ia.providers.mock import MockProvider
from solaria_ia.providers.ollama import OllamaError, OllamaProvider
from solaria_ia.providers.usage_ledger import DailyUsageLedger
from solaria_ia.schemas import TaskRequest, TaskResponse
from solaria_ia.settings import get_settings

settings = get_settings()
app = FastAPI(
    title="Solaria IA",
    version="0.1.0",
    description="Orquestração local-first com roteamento enxuto e colaboração condicional.",
)
if settings.provider_mode == "mock":
    provider = MockProvider()
    reviewer_provider = provider
else:
    inference_lock = asyncio.Lock()
    provider = OllamaProvider(settings, inference_lock=inference_lock)
    reviewer_provider = OllamaProvider(
        settings,
        model=settings.ollama_review_model,
        inference_lock=inference_lock,
    )

external_reviewer_provider = None
usage_ledger = None
if (
    settings.review_provider == "gemini"
    and settings.gemini_enabled
    and settings.gemini_free_tier_confirmed
):
    external_reviewer_provider = GeminiProvider(settings)
    usage_ledger = DailyUsageLedger(settings.daily_usage_db_path)
elif (
    settings.review_provider == "copilot"
    and settings.copilot_enabled
    and settings.copilot_free_tier_confirmed
):
    external_reviewer_provider = CopilotProvider(settings)
    usage_ledger = DailyUsageLedger(settings.daily_usage_db_path)

service = TaskService(
    settings=settings,
    provider=provider,
    reviewer_provider=reviewer_provider,
    external_reviewer_provider=external_reviewer_provider,
    usage_ledger=usage_ledger,
)
WEB_INDEX = Path(__file__).parent / "static" / "index.html"


@app.get("/", include_in_schema=False)
def web_interface() -> FileResponse:
    """Serve the lightweight web UI from the same origin as the API."""
    return FileResponse(WEB_INDEX, media_type="text/html")


@app.get("/health")
def health() -> dict[str, str | int | bool]:
    gemini_active = (
        settings.review_provider == "gemini"
        and settings.gemini_enabled
        and settings.gemini_free_tier_confirmed
        and settings.gemini_api_key is not None
    )
    copilot_active = (
        settings.review_provider == "copilot"
        and settings.copilot_enabled
        and settings.copilot_free_tier_confirmed
    )
    if gemini_active:
        review_model = settings.gemini_model
    elif copilot_active:
        review_model = settings.copilot_model
    elif settings.provider_mode == "ollama":
        review_model = settings.ollama_review_model
    else:
        review_model = "mock-v1"

    return {
        "status": "ok",
        "provider_mode": settings.provider_mode,
        "model": (settings.ollama_model if settings.provider_mode == "ollama" else "mock-v1"),
        "review_model": review_model,
        "review_provider_configured": settings.review_provider,
        "gemini_enabled": settings.gemini_enabled,
        "gemini_free_tier_confirmed": settings.gemini_free_tier_confirmed,
        "copilot_enabled": settings.copilot_enabled,
        "copilot_free_tier_confirmed": settings.copilot_free_tier_confirmed,
        "copilot_active": copilot_active,
        "local_parallelism": settings.local_parallelism,
        "max_calls_per_run": settings.max_calls_per_run,
    }


@app.post("/v1/tasks", response_model=TaskResponse)
async def create_task(request: TaskRequest) -> TaskResponse:
    try:
        return await service.run(request)
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except QuotaExceededError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except OrchestrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OllamaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except GeminiQuotaError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except GeminiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except CopilotQuotaError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except CopilotError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # no silent fallback to a paid provider
        raise HTTPException(
            status_code=500,
            detail="Falha interna; nenhuma troca automática de provedor foi realizada.",
        ) from exc
