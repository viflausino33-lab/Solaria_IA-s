from types import SimpleNamespace

import pytest

from solaria_ia.providers.copilot import CopilotError, CopilotProvider
from solaria_ia.settings import Settings

sdk_events = pytest.importorskip("copilot.session_events")
AssistantMessageData = sdk_events.AssistantMessageData
AssistantUsageData = sdk_events.AssistantUsageData


class FakeSession:
    def __init__(self):
        self.handlers = []
        self.prompt = None
        self.disconnected = False

    def on(self, handler):
        self.handlers.append(handler)
        return lambda: self.handlers.remove(handler)

    async def send_and_wait(self, *, prompt, timeout):
        self.prompt = prompt
        event = SimpleNamespace(
            agent_id=None,
            data=AssistantUsageData(
                model="gpt-test",
                input_tokens=70,
                output_tokens=12,
                cost=1.0,
            ),
        )
        for handler in list(self.handlers):
            handler(event)

        return SimpleNamespace(
            data=AssistantMessageData(
                content="Revisão concluída.",
                message_id="test-message",
                model="gpt-test",
                output_tokens=12,
            )
        )

    async def disconnect(self):
        self.disconnected = True


class FakeClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.session_kwargs = None
        self.session = FakeSession()
        self.started = False
        self.stopped = False

    async def start(self):
        self.started = True

    async def create_session(self, **kwargs):
        self.session_kwargs = kwargs
        return self.session

    async def stop(self):
        self.stopped = True


def make_settings(**overrides):
    values = {
        "copilot_enabled": True,
        "copilot_free_tier_confirmed": True,
        "copilot_model": "auto",
        "copilot_max_ai_credits_per_run": 1.0,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("enabled", "confirmed", "message"),
    [
        (False, True, "desativado"),
        (True, False, "Confirme o acesso gratuito"),
    ],
)
async def test_copilot_refuses_call_before_creating_client(enabled, confirmed, message):
    def forbidden_factory(**kwargs):
        raise AssertionError("O cliente não deveria ser criado.")

    provider = CopilotProvider(
        make_settings(
            copilot_enabled=enabled,
            copilot_free_tier_confirmed=confirmed,
        ),
        client_factory=forbidden_factory,
    )

    with pytest.raises(CopilotError, match=message):
        await provider.generate(
            system_prompt="Revise objetivamente.",
            user_prompt="Rascunho para revisão.",
            max_output_tokens=100,
        )


@pytest.mark.asyncio
async def test_copilot_uses_no_tools_and_reports_sdk_usage(monkeypatch, tmp_path):
    copilot_home = tmp_path / "copilot-home"
    monkeypatch.setenv("COPILOT_HOME", str(copilot_home))
    client = FakeClient()

    def factory(**kwargs):
        client.kwargs.update(kwargs)
        return client

    provider = CopilotProvider(
        make_settings(),
        client_factory=factory,
    )

    result = await provider.generate(
        system_prompt="Revise objetivamente.",
        user_prompt="Rascunho para revisão.",
        max_output_tokens=100,
    )

    assert result.text == "Revisão concluída."
    assert result.provider == "copilot"
    assert result.model == "gpt-test"
    assert result.input_tokens_estimated == 70
    assert result.output_tokens_estimated == 12

    assert client.started
    assert client.stopped
    assert client.session.disconnected
    assert client.kwargs["mode"] == "empty"
    assert client.kwargs["base_directory"] == str(copilot_home)
    assert client.kwargs["use_logged_in_user"] is True

    config = client.session_kwargs
    assert config["available_tools"] == []
    assert config["mcp_servers"] == {}
    assert config["system_message"]["mode"] == "append"
    assert config["session_limits"] == {"max_ai_credits": 1.0}
    assert config["enable_skills"] is False
    assert config["skip_custom_instructions"] is True
