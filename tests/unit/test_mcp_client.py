import pytest
from unittest.mock import AsyncMock
from nak.mcp_client.base import FallbackMcpTransport
from nak.protocols.mcp_transport import ToolCallResult

@pytest.mark.asyncio
async def test_mcp_fallback_success_on_first_try():
    mock_stdio = AsyncMock()
    mock_http = AsyncMock()
    
    transport = FallbackMcpTransport(stdio_transport=mock_stdio, http_transport=mock_http)
    
    await transport.connect()
    
    # Stdio should connect successfully, HTTP shouldn't be called
    mock_stdio.connect.assert_called_once()
    mock_http.connect.assert_not_called()
    assert transport.active_transport == mock_stdio

@pytest.mark.asyncio
async def test_mcp_fallback_to_http_on_stdio_failure():
    mock_stdio = AsyncMock()
    # Stdio throws error during connect
    mock_stdio.connect.side_effect = RuntimeError("Stdio locked / already running")
    
    mock_http = AsyncMock()
    
    transport = FallbackMcpTransport(stdio_transport=mock_stdio, http_transport=mock_http)
    
    await transport.connect()
    
    # Both stdio and HTTP connect should be called
    mock_stdio.connect.assert_called_once()
    mock_http.connect.assert_called_once()
    assert transport.active_transport == mock_http

@pytest.mark.asyncio
async def test_mcp_fallback_calls_active_transport():
    mock_stdio = AsyncMock()
    mock_stdio.connect.side_effect = RuntimeError("failed")
    
    mock_http = AsyncMock()
    mock_http.call_tool.return_value = ToolCallResult(
        success=True, result="mcp result", error_code=None, error_message=None, metadata={}
    )
    
    transport = FallbackMcpTransport(stdio_transport=mock_stdio, http_transport=mock_http)
    await transport.connect()
    
    res = await transport.call_tool("some_tool", {"arg": 1})
    assert res.success is True
    assert res.result == "mcp result"
    mock_http.call_tool.assert_called_once_with("some_tool", {"arg": 1})
    mock_stdio.call_tool.assert_not_called()
