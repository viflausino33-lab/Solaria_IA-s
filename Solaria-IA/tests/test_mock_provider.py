import pytest
from solaria_ia.providers.mock import MockProvider


@pytest.mark.asyncio
async def test_mock_explicitly_identifies_itself():
    result = await MockProvider().generate(system_prompt="system", user_prompt="test task", max_output_tokens=100)
    assert "MOCK MODE" in result.text
    assert result.provider == "mock"
