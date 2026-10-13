import time
import uuid

from solaria_ia.providers.base import Provider
from solaria_ia.routing.policy import classify_task
from solaria_ia.schemas import RouteDecision, StepMetric, TaskRequest, TaskResponse
from solaria_ia.settings import Settings

ANSWER_SYSTEM = (
    "Você é um especialista cuidadoso. Responda à tarefa em português, a menos que outra língua seja solicitada. "
    "Declare incertezas; não invente fatos nem afirme ter usado ferramentas que não possui."
)
CRITIC_SYSTEM = (
    "Você é um revisor independente. Avalie o rascunho apenas contra a tarefa. Procure erros materiais, "
    "lacunas, premissas frágeis e riscos. Se não houver correção material, comece exatamente com APPROVED. "
    "Se precisar de alteração, comece com REVISE e enumere apenas os pontos indispensáveis. Não reescreva tudo."
)
FINAL_SYSTEM = (
    "Você é o sintetizador final. Corrija o rascunho apenas com base na tarefa e na revisão fornecidas. "
    "Não aceite críticas incorretas sem avaliar. Responda diretamente e sinalize incerteza relevante."
)


def _approx_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


class OrchestrationError(RuntimeError):
    pass


class TaskService:
    def __init__(self, settings: Settings, provider: Provider) -> None:
        self.settings = settings
        self.provider = provider

    async def run(self, request: TaskRequest) -> TaskResponse:
        if len(request.task) > self.settings.max_input_chars:
            raise ValueError(f"A tarefa excede o limite configurado de {self.settings.max_input_chars} caracteres.")
        if request.max_output_tokens is not None:
            max_output_tokens = min(request.max_output_tokens, self.settings.max_output_tokens)
        else:
            max_output_tokens = self.settings.max_output_tokens

        route = classify_task(request, self.settings)
        # Enforce a strict call count before any inference is started.
        planned_calls = 1 if route.collaboration == "single" else 3
        if planned_calls > self.settings.max_calls_per_run:
            raise OrchestrationError(
                f"O fluxo exige até {planned_calls} chamadas, mas SOLARIA_MAX_CALLS_PER_RUN="
                f"{self.settings.max_calls_per_run}. Reduza o fluxo ou aumente o limite conscientemente."
            )

        run_id = str(uuid.uuid4())
        start = time.perf_counter()
        steps: list[StepMetric] = []

        answer_result = await self._generate(
            role="specialist",
            system_prompt=ANSWER_SYSTEM,
            user_prompt=request.task,
            max_output_tokens=max_output_tokens,
            steps=steps,
        )
        answer = answer_result.text

        if route.collaboration == "review":
            # The reviewer receives only the task and draft—not the complete execution history.
            review_prompt = f"TAREFA:\n{request.task}\n\nRASCUNHO PARA REVISÃO:\n{answer}"
            review_result = await self._generate(
                role="critic",
                system_prompt=CRITIC_SYSTEM,
                user_prompt=review_prompt,
                max_output_tokens=min(max_output_tokens, 400),
                steps=steps,
            )
            if not review_result.text.lstrip().startswith("APPROVED"):
                # Only pay the synthesis/revision call when the critic signals material changes.
                final_prompt = (
                    f"TAREFA ORIGINAL:\n{request.task}\n\nRASCUNHO:\n{answer}\n\n"
                    f"CRÍTICA:\n{review_result.text}\n\nProduza a resposta final corrigida."
                )
                final_result = await self._generate(
                    role="synthesizer",
                    system_prompt=FINAL_SYSTEM,
                    user_prompt=final_prompt,
                    max_output_tokens=max_output_tokens,
                    steps=steps,
                )
                answer = final_result.text

        elapsed = int((time.perf_counter() - start) * 1000)
        note = (
            "Modo mock: nenhuma inferência real foi executada."
            if self.provider.name == "mock"
            else "Execução local via Ollama; métricas de tokens podem ser estimadas quando o runtime não as retorna."
        )
        return TaskResponse(
            run_id=run_id,
            status="completed",
            answer=answer,
            route=route,
            steps=steps,
            total_elapsed_ms=elapsed,
            note=note,
        )

    async def _generate(
        self, *, role: str, system_prompt: str, user_prompt: str, max_output_tokens: int, steps: list[StepMetric]
    ):
        start = time.perf_counter()
        result = await self.provider.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_output_tokens=max_output_tokens,
        )
        elapsed = int((time.perf_counter() - start) * 1000)
        steps.append(
            StepMetric(
                role=role,
                provider=result.provider,
                model=result.model,
                elapsed_ms=elapsed,
                input_tokens_estimated=result.input_tokens_estimated or _approx_tokens(system_prompt + user_prompt),
                output_tokens_estimated=result.output_tokens_estimated or _approx_tokens(result.text),
            )
        )
        return result
