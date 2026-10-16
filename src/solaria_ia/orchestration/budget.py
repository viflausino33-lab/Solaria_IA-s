class TokenBudgetExceeded(RuntimeError):
    pass


class RunTokenBudget:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.spent = 0
        self._pending_input_estimate: int | None = None

    @staticmethod
    def estimate_input(system_prompt: str, user_prompt: str) -> int:
        combined = system_prompt + user_prompt
        return max(1, (len(combined) + 2) // 3)

    def prepare(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        requested_output_tokens: int,
    ) -> int:
        if self._pending_input_estimate is not None:
            raise RuntimeError("A chamada anterior ainda não foi contabilizada.")

        input_estimate = self.estimate_input(system_prompt, user_prompt)
        remaining = self.limit - self.spent
        output_limit = min(
            requested_output_tokens,
            remaining - input_estimate,
        )

        if output_limit < 32:
            raise TokenBudgetExceeded(
                "Orçamento de tokens insuficiente para iniciar outra chamada. "
                "Reduza o contexto ou aumente conscientemente o limite."
            )

        self._pending_input_estimate = input_estimate
        return output_limit

    def record(self, input_tokens: int, output_tokens: int) -> None:
        if self._pending_input_estimate is None:
            raise RuntimeError("Não há chamada reservada para contabilizar.")

        counted_input = max(
            self._pending_input_estimate,
            max(1, input_tokens),
        )
        counted_output = max(1, output_tokens)
        self.spent += counted_input + counted_output
        self._pending_input_estimate = None

    def abandon(self) -> None:
        """Clear a pending reservation after a failed generation."""
        self._pending_input_estimate = None
