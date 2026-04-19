import pytest
from unittest.mock import MagicMock, patch
from devwatcher.providers.anthropic import AnthropicProvider


def test_anthropic_provider_calls_create_with_correct_model(mocker):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Resumo gerado.")]
    mock_client.messages.create.return_value = mock_response

    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    provider = AnthropicProvider(api_key="fake", model="claude-sonnet-4-6", max_tokens=100)
    result = provider.generate("meu prompt")

    assert result == "Resumo gerado."
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-sonnet-4-6"
    assert call_kwargs["messages"][0]["content"] == "meu prompt"


def test_anthropic_provider_passes_system_when_provided(mocker):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="ok")]
    mock_client.messages.create.return_value = mock_response

    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    provider = AnthropicProvider(api_key="fake", model="claude-sonnet-4-6", max_tokens=100)
    provider.generate("prompt", system="system instructions")

    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["system"] == "system instructions"


def test_anthropic_provider_omits_system_when_empty(mocker):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="ok")]
    mock_client.messages.create.return_value = mock_response

    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    provider = AnthropicProvider(api_key="fake", model="claude-sonnet-4-6", max_tokens=100)
    provider.generate("prompt")

    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert "system" not in call_kwargs
