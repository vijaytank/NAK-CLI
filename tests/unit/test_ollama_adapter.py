import pytest
import httpx
from unittest.mock import AsyncMock, patch
from nak.model_adapter.providers.ollama import OllamaModelProvider
from nak.protocols.model_provider import ChatRequest, ChatResponse
from nak.core.errors import AppError

@pytest.fixture
def provider():
    return OllamaModelProvider(
        base_url="http://localhost:11434/v1",
        model_name="qwen3.5:4b"
    )

@pytest.mark.asyncio
async def test_ollama_chat_success(provider):
    mock_response = httpx.Response(
        status_code=200,
        json={
            "choices": [{
                "message": {
                    "content": "{\"task\": \"done\"}",
                    "tool_calls": []
                },
                "finish_reason": "stop"
            }],
            "usage": {"total_tokens": 10}
        }
    )
    
    req = ChatRequest(
        system="You are a helper.",
        prompt="Tell me a joke",
        response_format="json",
        tools=[],
        max_tokens=100,
        temperature=0.7,
        metadata={}
    )
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        res = await provider.chat(req)
        
        assert isinstance(res, ChatResponse)
        assert res.content == "{\"task\": \"done\"}"
        assert res.finish_reason == "stop"
        mock_post.assert_called_once()
        
        # Verify JSON format headers / options were requested
        args, kwargs = mock_post.call_args
        json_data = kwargs["json"]
        assert json_data["response_format"] == {"type": "json_object"}
        assert json_data["model"] == "qwen3.5:4b"

@pytest.mark.asyncio
async def test_ollama_chat_timeout(provider):
    req = ChatRequest(
        system="You are a helper.",
        prompt="Tell me a joke",
        response_format=None,
        tools=[],
        max_tokens=100,
        temperature=0.7,
        metadata={}
    )
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.TimeoutException("Timeout")
        with pytest.raises(AppError) as exc_info:
            await provider.chat(req)
        assert exc_info.value.code == "timeout"

@pytest.mark.asyncio
async def test_ollama_chat_connection_error(provider):
    req = ChatRequest(
        system="You are a helper.",
        prompt="Tell me a joke",
        response_format=None,
        tools=[],
        max_tokens=100,
        temperature=0.7,
        metadata={}
    )
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.ConnectError("Connection failed")
        with pytest.raises(AppError) as exc_info:
            await provider.chat(req)
        assert exc_info.value.code == "model_unavailable"
