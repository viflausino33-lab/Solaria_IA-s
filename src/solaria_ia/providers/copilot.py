from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from solaria_ia.providers.base import Generation
from solaria_ia.settings import Settings


class CopilotError(RuntimeError):
    """Falha no adaptador Copilot. Não realiza fallback automático."""


class CopilotQuotaError(CopilotError):
    """O Copilot informou cota, crédito ou limite de uso atingido."""


def _estimate_tokens(text: str) -> int:
    """Estimativa conservadora aproximada; não substitui a contagem do provedor."""
    return max(1, (len(text) + 1) // 2)


class CopilotProvider:
    name = "copilot"

    def __init__(
        self,
        settings: Settings,
        client_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.settings = settings
        self.model = settings.copilot_model
        self._client_factory = client_factory

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: int,
    ) -> Generation:
        # Fail closed: estas verificações ocorrem antes de criar uma sessão.
        if not self.settings.copilot_enabled:
            raise CopilotError("GitHub Copilot está desativado.")

        if not self.settings.copilot_free_tier_confirmed:
            raise CopilotError("Confirme o acesso gratuito ao Copilot antes de realizar chamadas.")

        try:
            from copilot import CopilotClient
            from copilot.session_events import AssistantMessageData, AssistantUsageData
        except ImportError as exc:
            raise CopilotError(
                'SDK ausente. Instale com: python -m pip install -e ".[copilot]"'
            ) from exc

        factory = self._client_factory or CopilotClient
        client = None
        session = None
        unsubscribe = None
        usage = {"input": 0, "output": 0, "model": None}

        with tempfile.TemporaryDirectory(prefix="solaria-copilot-review-") as workspace:
            try:
                # Reutiliza a autenticação da CLI; nunca solicita uma chave de API.
                configured_home = os.environ.get("COPILOT_HOME")
                copilot_home = str(
                    Path(configured_home).expanduser()
                    if configured_home
                    else Path.home() / ".copilot"
                )
                client = factory(
                    use_logged_in_user=True,
                    mode="empty",
                    base_directory=copilot_home,
                    working_directory=workspace,
                    log_level="error",
                )
                await client.start()

                review_instructions = (
                    f"{system_prompt}\n\n"
                    "Você é o revisor da Solaria IA. Faça somente uma revisão textual. "
                    "Não execute comandos, não altere arquivos, não use ferramentas nem "
                    "solicite ações externas. Analise o rascunho fornecido e responda "
                    "com achados objetivos e concisos. "
                    f"Mantenha a resposta próxima de {max_output_tokens} tokens ou menos."
                )

                session = await client.create_session(
                    model=self.model,
                    system_message={
                        "mode": "append",
                        "content": review_instructions,
                    },
                    available_tools=[],
                    mcp_servers={},
                    working_directory=workspace,
                    streaming=True,
                    session_limits={"max_ai_credits": self.settings.copilot_max_ai_credits_per_run},
                    enable_session_telemetry=False,
                    enable_file_change_tracking=False,
                    skip_custom_instructions=True,
                    refresh_custom_instructions=False,
                    enable_skills=False,
                    enable_session_store=False,
                    enable_github_cache_store=False,
                    skip_embedding_retrieval=True,
                    enable_on_demand_instruction_discovery=False,
                    enable_file_hooks=False,
                    enable_host_git_operations=False,
                    additional_directories=[],
                )

                def on_event(event: Any) -> None:
                    data = getattr(event, "data", None)
                    if getattr(event, "agent_id", None):
                        return
                    if isinstance(data, AssistantUsageData):
                        usage["input"] += data.input_tokens or 0
                        usage["output"] += data.output_tokens or 0
                        usage["model"] = data.model or usage["model"]

                unsubscribe = session.on(on_event)
                response = await session.send_and_wait(
                    prompt=user_prompt,
                    timeout=float(self.settings.request_timeout_seconds),
                )

                if response is None or not isinstance(response.data, AssistantMessageData):
                    raise CopilotError("O Copilot não retornou uma resposta utilizável.")

                answer = response.data.content.strip()
                if not answer:
                    raise CopilotError("O Copilot retornou uma resposta vazia.")

                # Prefere métricas informadas pelo SDK; utiliza estimativas somente
                # quando algum campo não é fornecido.
                input_tokens = usage["input"] or _estimate_tokens(system_prompt + user_prompt)
                output_tokens = (
                    usage["output"] or response.data.output_tokens or _estimate_tokens(answer)
                )

                return Generation(
                    text=answer,
                    input_tokens_estimated=input_tokens,
                    output_tokens_estimated=output_tokens,
                    provider=self.name,
                    model=usage["model"] or response.data.model or self.model,
                )

            except CopilotError:
                raise
            except Exception as exc:
                detail = str(exc).lower()
                quota_markers = (
                    "quota",
                    "rate limit",
                    "ai credits",
                    "credit limit",
                    "usage limit",
                    "budget exhausted",
                    "premium request limit",
                )
                if any(marker in detail for marker in quota_markers):
                    raise CopilotQuotaError(
                        "O Copilot informou um limite de uso ou de créditos. "
                        "Nenhum fallback automático foi tentado."
                    ) from exc
                raise CopilotError(
                    "Falha na sessão do Copilot. Nenhum fallback automático foi tentado."
                ) from exc
            finally:
                if unsubscribe is not None:
                    try:
                        unsubscribe()
                    except Exception:
                        pass

                if session is not None:
                    try:
                        await session.disconnect()
                    except Exception:
                        pass

                if client is not None:
                    try:
                        await client.stop()
                    except Exception:
                        pass
