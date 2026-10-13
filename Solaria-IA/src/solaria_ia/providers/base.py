from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class Generation:
    text: str
    input_tokens_estimated: int
    output_tokens_estimated: int
    provider: str
    model: str


class Provider(Protocol):
    name: str
    model: str

    async def generate(self, *, system_prompt: str, user_prompt: str, max_output_tokens: int) -> Generation:
        """Generate one response; raise an explicit exception on failure."""
