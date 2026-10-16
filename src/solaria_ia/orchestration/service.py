import re
import time
import uuid

from solaria_ia.orchestration.budget import (
    RunTokenBudget,
    TokenBudgetExceeded,
)
from solaria_ia.providers.base import Provider
from solaria_ia.providers.usage_ledger import (
    DailyUsageLedger,
    UsageLimitError,
)
from solaria_ia.routing.policy import classify_task
from solaria_ia.schemas import StepMetric, TaskRequest, TaskResponse
from solaria_ia.settings import Settings

ANSWER_SYSTEM = (
    "Você é um especialista cuidadoso. Responda à tarefa em português, "
    "a menos que outra língua seja solicitada. "
    "Declare incertezas; não invente fatos nem afirme ter usado "
    "ferramentas que não possui."
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


class QuotaExceededError(OrchestrationError):
    pass


class TaskService:
    def __init__(
        self,
        settings: Settings,
        provider: Provider,
        reviewer_provider: Provider | None = None,
        external_reviewer_provider: Provider | None = None,
        usage_ledger: DailyUsageLedger | None = None,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.reviewer_provider = reviewer_provider or provider
        self.external_reviewer_provider = external_reviewer_provider
        self.usage_ledger = usage_ledger

    async def run(self, request: TaskRequest) -> TaskResponse:
        if len(request.task) > self.settings.max_input_chars:
            raise ValueError(
                "A tarefa excede o limite configurado de "
                f"{self.settings.max_input_chars} caracteres."
            )
        if request.max_output_tokens is not None:
            max_output_tokens = min(request.max_output_tokens, self.settings.max_output_tokens)
        else:
            max_output_tokens = self.settings.max_output_tokens

        route = classify_task(request, self.settings)
        selected_reviewer = self.reviewer_provider

        use_external_review = route.collaboration == "review" and request.privacy != "local_only"
        if use_external_review and self.settings.review_provider == "copilot":
            if not self.settings.copilot_enabled:
                raise OrchestrationError(
                    "GitHub Copilot está desativado; nenhuma chamada externa foi realizada."
                )
            if not self.settings.copilot_free_tier_confirmed:
                raise OrchestrationError(
                    "Confirme o acesso gratuito ao GitHub Copilot antes de ativá-lo. "
                    "Nenhuma chamada externa foi realizada."
                )
            if self.external_reviewer_provider is None or self.usage_ledger is None:
                raise OrchestrationError(
                    "O adaptador GitHub Copilot ou controle de cota diário "
                    "está indisponível; nenhuma chamada externa foi realizada."
                )
            selected_reviewer = self.external_reviewer_provider

        use_gemini = (
            route.collaboration == "review"
            and request.privacy != "local_only"
            and self.settings.review_provider == "gemini"
        )
        if use_gemini:
            if not self.settings.gemini_enabled:
                raise OrchestrationError(
                    "Gemini está desativado; nenhuma chamada externa foi realizada."
                )
            if not self.settings.gemini_free_tier_confirmed:
                raise OrchestrationError(
                    "Confirme o acesso gratuito ao Gemini antes de ativá-lo. "
                    "Nenhuma chamada externa foi realizada."
                )
            if self.settings.gemini_api_key is None:
                raise OrchestrationError("Configure SOLARIA_GEMINI_API_KEY no ambiente local.")
            if self.external_reviewer_provider is None or self.usage_ledger is None:
                raise OrchestrationError(
                    "Adaptador Gemini ou controle de cota diário indisponível."
                )
            selected_reviewer = self.external_reviewer_provider

        # Enforce a strict call count before any inference is started.
        planned_calls = 1 if route.collaboration == "single" else 3
        if planned_calls > self.settings.max_calls_per_run:
            raise OrchestrationError(
                f"O fluxo exige até {planned_calls} chamadas, mas "
                "SOLARIA_MAX_CALLS_PER_RUN="
                f"{self.settings.max_calls_per_run}. "
                "Reduza o fluxo ou aumente o limite conscientemente."
            )

        run_id = str(uuid.uuid4())
        start = time.perf_counter()
        steps: list[StepMetric] = []
        budget = RunTokenBudget(limit=self.settings.max_total_tokens_per_run)

        answer_result = await self._generate(
            role="specialist",
            system_prompt=ANSWER_SYSTEM,
            user_prompt=request.task,
            max_output_tokens=max_output_tokens,
            steps=steps,
            budget=budget,
        )
        answer = answer_result.text

        if route.collaboration == "review":
            # The reviewer receives only the task and draft—not the complete execution history.
            review_prompt = f"TAREFA:\n{request.task}\n\nRASCUNHO PARA REVISÃO:\n{answer}"
            review_result = await self._generate(
                role="critic",
                system_prompt=CRITIC_SYSTEM,
                user_prompt=review_prompt,
                max_output_tokens=min(
                    max_output_tokens,
                    self.settings.review_max_output_tokens,
                ),
                steps=steps,
                provider=selected_reviewer,
                budget=budget,
            )
            critic_decision = _critic_decision(review_result.text)

            if critic_decision == "approved":
                route.reason += "; crítico marcou APPROVED; síntese dispensada"
            else:
                if critic_decision == "revise":
                    route.reason += "; crítico marcou REVISE; síntese executada"
                else:
                    route.reason += (
                        "; marcador do crítico inválido ou ausente; síntese executada por segurança"
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
                    budget=budget,
                )
                answer = final_result.text

        elapsed = int((time.perf_counter() - start) * 1000)
        note = (
            "Modo mock: nenhuma inferência real foi executada."
            if self.provider.name == "mock"
            else (
                "Execução local via Ollama; métricas de tokens podem ser estimadas "
                "quando o runtime não as retorna."
            )
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
        self,
        *,
        role: str,
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: int,
        steps: list[StepMetric],
        budget: RunTokenBudget,
        provider: Provider | None = None,
    ):
        start = time.perf_counter()
        active_provider = provider or self.provider

        try:
            output_limit = budget.prepare(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                requested_output_tokens=max_output_tokens,
            )
        except TokenBudgetExceeded as exc:
            raise OrchestrationError(str(exc)) from exc

        ledger = self.usage_ledger
        reservation: tuple[str, int] | None = None

        if active_provider.name in {"gemini", "copilot"}:
            if ledger is None:
                budget.abandon()
                raise OrchestrationError(
                    "O controle de cotas do provedor externo não está disponível."
                )

            estimated_input = budget.estimate_input(system_prompt, user_prompt)
            reserve_tokens = estimated_input * 2 + output_limit
            if active_provider.name == "gemini":
                call_limit = self.settings.gemini_daily_call_limit
                token_limit = self.settings.gemini_daily_token_limit
            else:
                call_limit = self.settings.copilot_daily_call_limit
                token_limit = self.settings.copilot_daily_token_limit

            try:
                reservation = ledger.reserve(
                    provider=active_provider.name,
                    estimated_tokens=reserve_tokens,
                    call_limit=call_limit,
                    token_limit=token_limit,
                )
            except UsageLimitError as exc:
                budget.abandon()
                raise QuotaExceededError(str(exc)) from exc
            except BaseException:
                budget.abandon()
                raise

        try:
            result = await active_provider.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_output_tokens=output_limit,
            )
        except BaseException:
            budget.abandon()
            if reservation is not None and ledger is not None:
                usage_date, reserved_tokens = reservation
                try:
                    ledger.release(
                        usage_date=usage_date,
                        provider=active_provider.name,
                        reserved_tokens=reserved_tokens,
                    )
                except Exception as exc:
                    raise OrchestrationError(
                        "A chamada falhou e não foi possível liberar a reserva "
                        "de tokens do provedor externo. Confira o ledger antes de tentar novamente."
                    ) from exc
            raise

        input_tokens = result.input_tokens_estimated or _approx_tokens(system_prompt + user_prompt)
        output_tokens = result.output_tokens_estimated or _approx_tokens(result.text)
        budget.record(input_tokens, output_tokens)

        if reservation is not None and ledger is not None:
            usage_date, reserved_tokens = reservation
            ledger.settle(
                usage_date=usage_date,
                provider=active_provider.name,
                reserved_tokens=reserved_tokens,
                actual_tokens=input_tokens + output_tokens,
            )

        elapsed = int((time.perf_counter() - start) * 1000)
        steps.append(
            StepMetric(
                role=role,
                provider=result.provider,
                model=result.model,
                elapsed_ms=elapsed,
                input_tokens_estimated=input_tokens,
                output_tokens_estimated=output_tokens,
            )
        )
        return result
