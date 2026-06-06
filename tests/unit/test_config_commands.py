import os
import tempfile
import pytest
from typer.testing import CliRunner
from unittest.mock import AsyncMock, patch

from nak.cli.main import app
from nak.memory.sqlite_store import SQLiteMemoryStore

runner = CliRunner()

@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "memory.db")
        store = SQLiteMemoryStore(db_path)
        store.connect()
        try:
            yield store, db_path
        finally:
            store.close()

@pytest.mark.asyncio
async def test_database_config_store(temp_db):
    store, _ = temp_db
    
    # Initially none
    assert await store.get_config("test_key") is None
    
    # Save config
    await store.set_config("test_key", "test_value")
    assert await store.get_config("test_key") == "test_value"
    
    # Overwrite config
    await store.set_config("test_key", "new_value")
    assert await store.get_config("test_key") == "new_value"

def test_cli_config_commands(tmp_path):
    # Set workspace option pointing to tmp_path to avoid modifying host settings
    workspace_dir = str(tmp_path)
    
    # 1. Config show should display no configurations found
    result = runner.invoke(app, ["config", "show", "--workspace", workspace_dir])
    assert result.exit_code == 0
    normalized_output = result.output.lower().replace("\r", "").replace("\n", " ").replace("  ", " ")
    assert "no configurations found" in normalized_output
    assert "use 'nak config [ollama|llama]' to configure a provider" in normalized_output
    
    # 2. Config ollama with custom local URL
    result = runner.invoke(app, ["config", "ollama", "--local", "http://127.0.0.1:11434/v1", "--workspace", workspace_dir])
    assert result.exit_code == 0
    assert "provider set to: ollama" in result.output.lower()
    
    # 3. Config llama with custom local URL
    result = runner.invoke(app, ["config", "llama", "--local", "http://127.0.0.1:8080/v1", "--workspace", workspace_dir])
    assert result.exit_code == 0
    assert "provider set to: llama" in result.output.lower()
    
    # 4. Config show should now show llama and custom URLs
    result = runner.invoke(app, ["config", "show", "--workspace", workspace_dir])
    assert result.exit_code == 0
    assert "llama" in result.output.lower()
    assert "http://127.0.0.1:8080/v1" in result.output


def test_cli_config_set(tmp_path):
    workspace_dir = str(tmp_path)
    
    # 1. Set model_timeout
    result = runner.invoke(app, ["config", "set", "model_timeout", "600", "--workspace", workspace_dir])
    assert result.exit_code == 0
    assert "model_timeout set to: 600" in result.output.lower()
    
    # 2. Config show should display Model Timeout: 600 seconds
    result = runner.invoke(app, ["config", "show", "--workspace", workspace_dir])
    assert result.exit_code == 0
    assert "model timeout" in result.output.lower()
    assert "600" in result.output


def test_cli_model_commands(tmp_path):
    workspace_dir = str(tmp_path)
    
    # 1. Model command should show not configured
    result = runner.invoke(app, ["model", "--workspace", workspace_dir])
    assert result.exit_code == 0
    assert "not configured" in result.output.lower()
    
    # 2. Model set should change the model
    result = runner.invoke(app, ["model", "set", "custom-model:7b", "--workspace", workspace_dir])
    assert result.exit_code == 0
    assert "model set to: custom-model:7b" in result.output.lower()
    
    # 3. Model command should now show custom-model:7b
    result = runner.invoke(app, ["model", "--workspace", workspace_dir])
    assert result.exit_code == 0
    assert "custom-model:7b" in result.output.lower()

@pytest.mark.asyncio
async def test_llama_model_provider():
    from nak.model_adapter.providers.llama import LlamaModelProvider
    from nak.protocols.model_provider import ChatRequest
    
    provider = LlamaModelProvider(base_url="http://localhost:8080/v1", model_name="llama-3b")
    assert provider.name == "llama"
    assert provider.version == "model-provider/1"
    
    req = ChatRequest(
        system="System prompt",
        prompt="User prompt",
        response_format=None,
        tools=[],
        max_tokens=50,
        temperature=0.7,
        metadata={}
    )
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        import httpx
        mock_response = httpx.Response(
            status_code=200,
            json={
                "choices": [{
                    "message": {
                        "content": "Hello user",
                        "tool_calls": []
                    },
                    "finish_reason": "stop"
                }],
                "usage": {"total_tokens": 15}
            }
        )
        mock_post.return_value = mock_response
        res = await provider.chat(req)
        assert res.content == "Hello user"
