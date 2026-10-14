import re
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
    "Você é um revisor independente. Compare o rascunho com a tarefa original. "
    "Verifique erros materiais, omissões importantes, premissas frágeis e riscos. "
    "A primeira linha deve começar com APPROVED ou REVISE. "
    "Use APPROVED quando o rascunho cumprir os requisitos essenciais da tarefa. "
    "Use REVISE somente se houver erro material, omissão relevante ou violação "
    "de uma exigência explícita do usuário. "
    "Não peça mudanças apenas por preferência de estilo, polimento opcional, "
    "redundância menor ou desejo de tornar a resposta mais detalhada. "
    "Se usar REVISE, liste no máximo 3 correções indispensáveis. "
    "Não escreva introdução antes do marcador e não reescreva o rascunho inteiro."
)


FINAL_SYSTEM = (
    "Você é o sintetizador final. Use a tarefa original como requisito principal "
    "e avalie criticamente as sugestões do revisor. Corrija apenas problemas "
    "reais ou violações de requisitos explícitos. Preserve o formato, o idioma, "
    "a extensão e a quantidade de itens ou frases pedidos pelo usuário. "
    "Não acrescente títulos, conclusões, notas de incerteza ou comentários "
    "sobre a própria resposta, salvo quando forem pedidos ou materialmente "
    "necessários para evitar uma resposta enganosa. "
    "Entregue apenas a resposta final."
)

def _approx_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)
def _critic_decision(text: str) -> str:
    first_line = next(
        (line.strip() for line in text.splitlines() if line.strip()),
        "",
    )

    if re.match(r"^\**\s*APPROVED\b", first_line, re.IGNORECASE):
        return "approved"

    if re.match(r"^\**\s*REVISE\b", first_line, re.IGNORECASE):
        return "revise"

    return "unknown"

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
            critic_decision = _critic_decision(review_result.text)

            if critic_decision == "approved":
                route.reason += "; crítico marcou APPROVED; síntese dispensada"
            else:
                if critic_decision == "revise":
                    route.reason += "; crítico marcou REVISE; síntese executada"
                else:
                    route.reason += (
                        "; marcador do crítico inválido ou ausente; "
                        "síntese executada por segurança"
                    )
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
