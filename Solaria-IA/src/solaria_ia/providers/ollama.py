import httpx

from solaria_ia.providers.base import Generation
from solaria_ia.settings import Settings


class OllamaError(RuntimeError):
    """Local model backend failed; no paid fallback is attempted."""


class OllamaProvider:
    name = "ollama"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model = settings.ollama_model

    async def generate(self, *, system_prompt: str, user_prompt: str, max_output_tokens: int) -> Generation:
        url = self.settings.ollama_base_url.rstrip("/") + "/api/chat"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "keep_alive": self.settings.ollama_keep_alive,
            "options": {"num_predict": max_output_tokens},
        }
        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OllamaError(
                "Ollama não respondeu corretamente. Verifique o serviço, o modelo baixado e a URL. "
                "Nenhum fallback pago será tentado automaticamente."
            ) from exc

        text = ((data.get("message") or {}).get("content") or "").strip()
        if not text:
            raise OllamaError("Ollama devolveu uma resposta vazia; a execução foi interrompida.")

        prompt_tokens = data.get("prompt_eval_count")
        output_tokens = data.get("eval_count")
        return Generation(
            text=text,
            input_tokens_estimated=int(prompt_tokens) if prompt_tokens is not None else max(1, len(system_prompt + user_prompt) // 4),
            output_tokens_estimated=int(output_tokens) if output_tokens is not None else max(1, len(text) // 4),
            provider=self.name,
            model=self.model,
        )
