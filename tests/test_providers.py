import pytest
from unittest.mock import MagicMock, patch
from devwatcher.providers.anthropic import AnthropicProvider
from unittest.mock import call
from devwatcher.providers.gemini import GeminiProvider


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


# --- GeminiProvider ---

def test_gemini_provider_calls_generate_content_with_correct_model(mocker):
    mock_client = MagicMock()
    mock_response = MagicMock(text="Resumo Gemini.")
    mock_client.models.generate_content.return_value = mock_response

    mocker.patch("devwatcher.providers.gemini.genai.Client", return_value=mock_client)

    provider = GeminiProvider(api_key="fake", model="gemini-2.0-flash", max_tokens=500)
    result = provider.generate("meu prompt")

    assert result == "Resumo Gemini."
    call_kwargs = mock_client.models.generate_content.call_args.kwargs
    assert call_kwargs["model"] == "gemini-2.0-flash"
    assert call_kwargs["contents"] == "meu prompt"


def test_gemini_provider_passes_system_instruction_when_provided(mocker):
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(text="ok")

    mocker.patch("devwatcher.providers.gemini.genai.Client", return_value=mock_client)

    provider = GeminiProvider(api_key="fake", model="gemini-2.0-flash", max_tokens=500)
    provider.generate("prompt", system="instruções do sistema")

    call_kwargs = mock_client.models.generate_content.call_args.kwargs
    assert call_kwargs["config"].system_instruction == "instruções do sistema"


def test_gemini_provider_omits_system_instruction_when_empty(mocker):
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(text="ok")

    mocker.patch("devwatcher.providers.gemini.genai.Client", return_value=mock_client)

    provider = GeminiProvider(api_key="fake", model="gemini-2.0-flash", max_tokens=500)
    provider.generate("prompt")

    call_kwargs = mock_client.models.generate_content.call_args.kwargs
    assert call_kwargs["config"].system_instruction is None
