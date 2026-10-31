import pytest

from obsidian_postit_kde import openrouter
from obsidian_postit_kde.openrouter import OpenRouterClient, OpenRouterError


def test_env_key_takes_precedence(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "env-key-123")
    assert openrouter.get_api_key() == "env-key-123"
    assert openrouter.has_api_key() is True


def test_no_key_raises(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(openrouter, "get_api_key", lambda: None)
    client = OpenRouterClient("openai/gpt-4o-mini")
    with pytest.raises(OpenRouterError):
        client.summarize("hello")


def test_empty_text_raises(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    client = OpenRouterClient("openai/gpt-4o-mini")
    with pytest.raises(OpenRouterError):
        client.clean("   ")
