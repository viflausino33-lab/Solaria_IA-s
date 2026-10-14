from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: str = Field(min_length=3, max_length=100_000)
    collaboration: Literal["auto", "single", "review"] = "auto"
    privacy: Literal["local_only", "standard"] = "local_only"
    max_output_tokens: int | None = Field(default=None, ge=32, le=8_192)


class RouteDecision(BaseModel):
    task_type: Literal["general", "coding", "research", "analysis", "planning"]
    complexity: Literal["low", "medium", "high"]
    consequence: Literal["low", "medium", "high"]
    provider: Literal["mock", "ollama"]
    model: str
    collaboration: Literal["single", "review"]
    reason: str


class StepMetric(BaseModel):
    role: str
    provider: str
    model: str
    elapsed_ms: int
    input_tokens_estimated: int
    output_tokens_estimated: int


class TaskResponse(BaseModel):
    run_id: str
    status: Literal["completed"]
    answer: str
    route: RouteDecision
    steps: list[StepMetric]
    total_elapsed_ms: int
    note: str
