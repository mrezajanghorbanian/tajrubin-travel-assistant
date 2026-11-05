"""CORE-01 protocol proof with synthetic responses; no external model in CI."""
import json

import httpx
import pytest
from pydantic import ValidationError

from app.providers.openai_compatible import OpenAICompatibleProviderError, OpenAICompatibleTextGenerationProvider
from app.providers.runtime_config import LocalProviderRuntimeConfigV1, build_local_text_generation_provider
from app.providers.text_generation import TextGenerationResponseV1


class Stub:
    def __init__(self, text=None, error=None):
        self.text = text
        self.error = error
        self.calls = []

    def generate(self, request):
        self.calls.append(request)
        if self.error:
            raise self.error
        return TextGenerationResponseV1(text=self.text, model_name="fixture-local-model")


def turn(message="برای سه روز شیراز یه سفر آروم می‌خوام.", **kwargs):
    from app.assistant.local_model_turn import LocalModelTurnRequestV1, generate_local_turn
    return generate_local_turn(LocalModelTurnRequestV1(message=message), **kwargs)


def valid_reply():
    return json.dumps({"understanding": "سفر آرام سه‌روزه به شیراز می‌خواهید.", "clarification_question": "چه تاریخی سفر می‌کنید؟"})


def test_real_provider_protocol_reaches_strict_persian_intake():
    captured = []
    def handler(request):
        captured.append(json.loads(request.content))
        assert str(request.url) == "http://127.0.0.1:1234/v1/chat/completions"
        assert "authorization" not in request.headers
        return httpx.Response(200, json={"model": "fixture-qwen", "choices": [{"message": {"content": valid_reply()}}]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleTextGenerationProvider(base_url="http://127.0.0.1:1234", model="fixture-qwen", client=client)
        result = turn(provider=provider)
    assert result.status == "model_reply"
    assert result.model_name == "fixture-qwen"
    assert result.intake.clarification_question == "چه تاریخی سفر می‌کنید؟"
    assert result.live_verified is False
    assert result.needs_verification is True
    assert result.error_code is None
    assert len(captured) == 1
    assert captured[0]["max_tokens"] == 512
    schema = captured[0]["response_format"]
    assert schema["type"] == "json_schema"
    assert schema["json_schema"]["schema"]["additionalProperties"] is False
    assert set(schema["json_schema"]["schema"]["required"]) == {"understanding", "clarification_question"}
    assert [m["role"] for m in captured[0]["messages"]] == ["system", "user"]
    assert "شیراز" in captured[0]["messages"][1]["content"]


@pytest.mark.parametrize("reply", [
    "not JSON", "[]", "{}", "```json\n{}\n```",
    '{"understanding":"x","understanding":"y","clarification_question":null}',
    '{"understanding":"x","clarification_question":false}',
    '{"understanding":" ","clarification_question":null}',
    '{"understanding":"x","clarification_question":null,"tool":"book"}',
    '{"understanding":"x","clarification_question":null,"booked":true}',
    "x" * 8001,
])
def test_invalid_or_action_bearing_output_fails_without_fallback(reply):
    provider = Stub(reply)
    result = turn(provider=provider)
    assert result.status == "invalid_model_reply"
    assert result.intake is None
    assert result.error_code == "output_contract"
    assert len(provider.calls) == 1


@pytest.mark.parametrize("code", ["timeout", "http_error", "transport_error", "invalid_json", "invalid_response", "empty_response"])
def test_provider_failure_is_explicit_and_never_replaced_by_rules(code):
    result = turn(provider=Stub(error=OpenAICompatibleProviderError(code, "sensitive diagnostic")))
    assert result.status in {"model_unavailable", "invalid_model_reply"}
    assert result.intake is None
    assert result.error_code == code
    assert "sensitive diagnostic" not in result.model_dump_json()


@pytest.mark.parametrize("message", ["", "x", "a" * 2001])
def test_invalid_input_does_not_call_model(message):
    with pytest.raises(ValidationError):
        turn(message, provider=Stub(valid_reply()))


def test_question_can_be_null_without_claiming_a_completed_plan():
    result = turn(provider=Stub('{"understanding":"درخواست اولیه ثبت شد.","clarification_question":null}'))
    assert result.status == "model_reply"
    assert result.intake.clarification_question is None
    assert "schedule" not in result.model_dump()
    assert "booked" not in result.model_dump()


def test_cli_json_and_error_exit_codes(monkeypatch, capsys):
    from app.assistant import local_model_turn as module
    class ContextStub(Stub):
        def __enter__(self): return self
        def __exit__(self, *args): pass
    provider = ContextStub(valid_reply())
    monkeypatch.setattr(module, "build_local_text_generation_provider", lambda config: provider)
    assert module.main(["سه روز شیراز", "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "model_reply"
    provider.error = OpenAICompatibleProviderError("timeout", "sensitive diagnostic")
    assert module.main(["سه روز شیراز", "--format", "json"]) == 1
    assert json.loads(capsys.readouterr().out)["error_code"] == "timeout"
    assert module.main(["x", "--format", "json"]) == 2
    assert "x" not in capsys.readouterr().err


def test_local_builder_does_not_use_environment_proxies(monkeypatch):
    from app.providers import openai_compatible
    captured = {}
    class Client:
        def close(self): pass
    def factory(**kwargs):
        captured.update(kwargs)
        return Client()
    monkeypatch.setattr(openai_compatible.httpx, "Client", factory)
    with build_local_text_generation_provider(LocalProviderRuntimeConfigV1()):
        pass
    assert captured["trust_env"] is False
    assert captured["follow_redirects"] is False


@pytest.mark.parametrize("url", ["https://example.com", "http://user@localhost:1234", "http://localhost:1234/v1", "http://localhost:1234?x=1", "http://localhost:1234#frag"])
def test_agent_config_rejects_remote_or_ambiguous_base_urls(url):
    with pytest.raises(ValidationError):
        LocalProviderRuntimeConfigV1(base_url=url)


def test_invalid_provider_contract_is_a_model_failure():
    class InvalidProvider:
        def generate(self, request):
            return TextGenerationResponseV1(text="")
    result = turn(provider=InvalidProvider())
    assert result.status == "invalid_model_reply"
    assert result.error_code == "invalid_response"
    assert result.intake is None


@pytest.mark.parametrize("depth", [1200, 3500])
def test_excessive_json_nesting_is_rejected(depth):
    nested = '{"understanding":' + '[' * depth + '0' + ']' * depth + ',"clarification_question":null}'
    result = turn(provider=Stub(nested))
    assert result.status == "invalid_model_reply"
    assert result.error_code == "output_contract"


@pytest.mark.parametrize("payload", [
    {"status": "model_reply"},
    {"status": "model_unavailable"},
    {"status": "model_unavailable", "error_code": "timeout", "live_verified": True},
])
def test_response_cannot_claim_an_inconsistent_or_verified_outcome(payload):
    from app.assistant.local_model_turn import LocalModelTurnV1
    with pytest.raises(ValidationError):
        LocalModelTurnV1(**payload)


@pytest.mark.parametrize("tokens", [0, 127, 1025, True])
def test_token_budget_is_bounded_and_not_boolean(tokens):
    from app.assistant.local_model_turn import LocalModelTurnRequestV1
    with pytest.raises(ValidationError):
        LocalModelTurnRequestV1(message="سه روز شیراز", max_tokens=tokens)


@pytest.mark.parametrize("timeout", ["0", "-1", "121", "nan"])
def test_cli_rejects_unbounded_timeout_before_model_call(timeout, capsys):
    from app.assistant.local_model_turn import main
    assert main(["سه روز شیراز", "--timeout", timeout]) == 2
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("schema", ["invalid", "[]", '{"type":"array"}', "x" * 20001])
def test_generation_schema_is_bounded_json_object_schema(schema):
    from app.providers.text_generation import TextGenerationRequestV1
    with pytest.raises(ValidationError):
        TextGenerationRequestV1(prompt="fixture", response_schema_json=schema)
