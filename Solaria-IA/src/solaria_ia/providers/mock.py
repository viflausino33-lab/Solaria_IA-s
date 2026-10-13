from solaria_ia.providers.base import Generation


class MockProvider:
    """Offline provider for tests and architecture work; output is not a real AI answer."""

    name = "mock"
    model = "mock-v1"

    async def generate(self, *, system_prompt: str, user_prompt: str, max_output_tokens: int) -> Generation:
        text = (
            "[MOCK MODE — nenhuma IA foi chamada]\n"
            "Este é um retorno simulado para testar o fluxo de orquestração.\n\n"
            f"Tarefa recebida: {user_prompt[:500]}\n\n"
            "Configure SOLARIA_PROVIDER_MODE=ollama para executar um modelo local."
        )
        return Generation(
            text=text,
            input_tokens_estimated=max(1, len(system_prompt + user_prompt) // 4),
            output_tokens_estimated=max(1, len(text) // 4),
            provider=self.name,
            model=self.model,
        )
