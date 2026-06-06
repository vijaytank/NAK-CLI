import pytest
import httpx
from unittest.mock import AsyncMock, patch
from typer.testing import CliRunner

from nak.cli.main import app
from nak.model_adapter.providers.ollama import OllamaModelProvider
from nak.model_adapter.providers.llama import LlamaModelProvider
from nak.core.errors import AppError

runner = CliRunner()

@pytest.mark.asyncio
async def test_ollama_provider_health_success():
    provider = OllamaModelProvider(base_url="http://localhost:11434/v1", model_name="qwen")
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(status_code=200)
        assert await provider.health() is True
        mock_get.assert_called_once_with("http://localhost:11434/v1/models")

@pytest.mark.asyncio
async def test_ollama_provider_health_failure():
    provider = OllamaModelProvider(base_url="http://localhost:11434/v1", model_name="qwen")
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        # 1. Non-200 code
        mock_get.return_value = httpx.Response(status_code=500)
        assert await provider.health() is False
        
        # 2. Timeout exception
        mock_get.side_effect = httpx.TimeoutException("Timeout")
        assert await provider.health() is False

        # 3. Connection error
        mock_get.side_effect = httpx.ConnectError("Connection failed")
        assert await provider.health() is False

@pytest.mark.asyncio
async def test_llama_provider_health_success():
    provider = LlamaModelProvider(base_url="http://localhost:8080/v1", model_name="llama")
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = httpx.Response(status_code=200)
        assert await provider.health() is True
        mock_get.assert_called_once_with("http://localhost:8080/v1/models")

@pytest.mark.asyncio
async def test_llama_provider_health_failure():
    provider = LlamaModelProvider(base_url="http://localhost:8080/v1", model_name="llama")
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.ConnectError("Connection failed")
        assert await provider.health() is False

@pytest.mark.asyncio
async def test_ollama_list_models_empty_on_failure():
    provider = OllamaModelProvider(base_url="http://localhost:11434/v1", model_name="qwen")
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        # Failure should return [] instead of hardcoded defaults
        mock_get.side_effect = httpx.ConnectError("Offline")
        models = await provider.list_models()
        assert models == []

@pytest.mark.asyncio
async def test_llama_list_models_empty_on_failure():
    provider = LlamaModelProvider(base_url="http://localhost:8080/v1", model_name="llama")
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.ConnectError("Offline")
        models = await provider.list_models()
        assert models == []

def test_cli_model_list_unconfigured_provider(tmp_path):
    workspace_dir = str(tmp_path)
    result = runner.invoke(app, ["model", "list", "--workspace", workspace_dir])
    assert result.exit_code != 0
    normalized_output = result.output.lower().replace("\r", "").replace("\n", " ").replace("  ", " ")
    assert "no active provider configured" in normalized_output
    assert "please configure one using 'nak config [ollama|llama]'" in normalized_output

def test_cli_model_list_unconfigured_url(tmp_path):
    workspace_dir = str(tmp_path)
    # Configure provider only, not the URL
    runner.invoke(app, ["config", "ollama", "--workspace", workspace_dir])
    result = runner.invoke(app, ["model", "list", "--workspace", workspace_dir])
    assert result.exit_code != 0
    assert "url is not configured" in result.output.lower()

@patch("nak.model_adapter.providers.ollama.OllamaModelProvider.health", new_callable=AsyncMock)
def test_cli_model_list_offline_provider(mock_health, tmp_path):
    workspace_dir = str(tmp_path)
    # Configure provider and URL
    runner.invoke(app, ["config", "ollama", "--local", "http://localhost:11434/v1", "--workspace", workspace_dir])
    
    mock_health.return_value = False
    result = runner.invoke(app, ["model", "list", "--workspace", workspace_dir])
    assert result.exit_code != 0
    assert "please make sure your ollama is running and connected" in result.output.lower()

@patch("nak.model_adapter.providers.ollama.OllamaModelProvider.health", new_callable=AsyncMock)
@patch("nak.model_adapter.providers.ollama.OllamaModelProvider.list_models", new_callable=AsyncMock)
def test_cli_model_list_online_provider(mock_list, mock_health, tmp_path):
    workspace_dir = str(tmp_path)
    runner.invoke(app, ["config", "ollama", "--local", "http://localhost:11434/v1", "--workspace", workspace_dir])
    
    mock_health.return_value = True
    mock_list.return_value = ["my-model-1", "my-model-2"]
    
    result = runner.invoke(app, ["model", "list", "--workspace", workspace_dir])
    assert result.exit_code == 0
    assert "my-model-1" in result.output
    assert "my-model-2" in result.output
