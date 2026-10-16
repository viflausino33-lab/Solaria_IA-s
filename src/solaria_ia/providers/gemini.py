import httpx

from solaria_ia.providers.base import Generation
from solaria_ia.settings import Settings


class GeminiError(RuntimeError):
    """Falha na API Gemini; nenhuma troca automática de provedor é realizada."""


class GeminiQuotaError(GeminiError):
    """A API Gemini informou que uma cota foi atingida."""


class GeminiProvider:
    name = "gemini"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model = settings.gemini_model

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: int,
    ) -> Generation:
        if not self.settings.gemini_enabled:
            raise GeminiError("Gemini está desativado na configuração.")

        if not self.settings.gemini_free_tier_confirmed:
            raise GeminiError("Confirme o acesso gratuito ao Gemini antes de realizar chamadas.")
        if self.settings.gemini_api_key is None:
            raise GeminiError("Configure SOLARIA_GEMINI_API_KEY para habilitar o Gemini.")

        api_key = self.settings.gemini_api_key.get_secret_value()
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        )
        payload = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}],
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}],
                }
            ],
            "generationConfig": {
                "maxOutputTokens": max_output_tokens,
                "temperature": 0.2,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
                response = await client.post(
                    url,
                    headers={"x-goog-api-key": api_key},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code

            if status == 429:
                raise GeminiQuotaError(
                    "A cota ou o limite de requisições do Gemini foi atingido. "
                    "Aguarde ou confira as cotas do projeto; nenhum fallback foi tentado."
                ) from exc

            if status in (401, 403):
                raise GeminiError(
                    "O Gemini recusou a autenticação ou as permissões da chave."
                ) from exc

            raise GeminiError(
                f"A API Gemini retornou HTTP {status}. Nenhum fallback automático foi tentado."
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise GeminiError(
                "Não foi possível comunicar com a API Gemini ou interpretar sua resposta."
            ) from exc

        candidates = data.get("candidates") or []
        if not candidates:
            raise GeminiError(
                "Gemini não retornou uma resposta utilizável; verifique bloqueios e limites."
            )

        candidate = candidates[0]
        if candidate.get("finishReason") == "MAX_TOKENS":
            raise GeminiError(
                f"Gemini atingiu o limite de {max_output_tokens} tokens; "
                "a resposta pode estar truncada."
            )

        parts = (candidate.get("content") or {}).get("parts") or []
        text = "".join(
            part.get("text", "") for part in parts if isinstance(part.get("text"), str)
        ).strip()

        if not text:
            raise GeminiError("Gemini devolveu texto vazio.")

        usage = data.get("usageMetadata") or {}
        input_tokens = usage.get("promptTokenCount")
        output_tokens = usage.get("candidatesTokenCount")

        return Generation(
            text=text,
            input_tokens_estimated=(
                int(input_tokens)
                if input_tokens is not None
                else max(1, len(system_prompt + user_prompt) // 4)
            ),
            output_tokens_estimated=(
                int(output_tokens) if output_tokens is not None else max(1, len(text) // 4)
            ),
            provider=self.name,
            model=self.model,
        )
