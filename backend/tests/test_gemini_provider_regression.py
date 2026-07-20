import os

import pytest

from app.services import ai_provider, llm_service


class _DummyModels:
    def __init__(self):
        self.calls = 0

    def get(self, **kwargs):
        self.calls += 1
        raise AssertionError("startup validation should not issue a real SDK request")


class _DummyClient:
    def __init__(self, *args, **kwargs):
        self.models = _DummyModels()


class _CountingProvider:
    def __init__(self):
        self.calls = 0

    def generate_response(self, user_message, knowledge_context=None):
        self.calls += 1
        raise RuntimeError("transient failure")


def test_gemini_provider_does_not_issue_sdk_validation_on_init(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    monkeypatch.setattr(ai_provider.google_genai, "Client", lambda *args, **kwargs: _DummyClient())

    provider = ai_provider.GeminiProvider()

    assert provider.is_ready() is True
    assert provider._model_name == "gemini-2.5-flash"


def test_llm_service_does_not_double_retry_provider_calls(monkeypatch):
    provider = _CountingProvider()
    monkeypatch.setattr(llm_service, "get_ai_provider", lambda: provider)

    with pytest.raises(RuntimeError):
        llm_service.generate_response("hello")

    assert provider.calls == 1
