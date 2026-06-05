import pytest
from unittest.mock import AsyncMock, MagicMock
from nak.planner.planner import Planner
from nak.protocols.model_provider import ChatResponse
from nak.core.errors import AppError

@pytest.fixture
def mock_provider():
    return AsyncMock()

def test_planner_system_prompt_guidelines():
    planner = Planner(provider=MagicMock())
    prompt = planner.build_system_prompt("ws")
    
    # Must enforce workspace relative path rules (addresses Bug #4 from POC)
    assert "relative path" in prompt.lower()
    assert "leading slash" in prompt.lower() or "strip" in prompt.lower()

@pytest.mark.asyncio
async def test_planner_parse_success(mock_provider):
    json_graph = (
        "{\n"
        "  \"goal\": \"test goal\",\n"
        "  \"workspace\": \"ws\",\n"
        "  \"mode\": \"trusted-local\",\n"
        "  \"tasks\": [\n"
        "    { \"id\": \"t1\", \"kind\": \"context\", \"depends_on\": [], \"action\": \"fetch\" }\n"
        "  ]\n"
        "}"
    )
    
    mock_provider.chat.return_value = ChatResponse(
        content=json_graph,
        tool_calls=[],
        finish_reason="stop",
        usage={},
        raw_provider_response={}
    )
    
    planner = Planner(provider=mock_provider)
    graph = await planner.plan("fix bug", "ws", "trusted-local")
    
    assert graph["goal"] == "test goal"
    assert graph["workspace"] == "ws"
    assert len(graph["tasks"]) == 1
    assert graph["tasks"][0]["id"] == "t1"

@pytest.mark.asyncio
async def test_planner_invalid_json_raises_error(mock_provider):
    # Freeform text from LLM instead of JSON
    mock_provider.chat.return_value = ChatResponse(
        content="Here is your plan: ...",
        tool_calls=[],
        finish_reason="stop",
        usage={},
        raw_provider_response={}
    )
    
    planner = Planner(provider=mock_provider)
    with pytest.raises(AppError) as exc_info:
        await planner.plan("fix bug", "ws", "trusted-local")
    assert exc_info.value.code == "invalid_output"
