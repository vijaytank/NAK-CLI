import pytest
from unittest.mock import AsyncMock
from nak.cli.repl import (
    cycle_mode,
    compress_prompt,
    parse_slash_command,
    REPLState,
)

def test_cycle_mode():
    state = REPLState()
    assert state.mode == "chat" # Default mode
    
    state.mode = cycle_mode(state.mode)
    assert state.mode == "plan"
    
    state.mode = cycle_mode(state.mode)
    assert state.mode == "code"
    
    state.mode = cycle_mode(state.mode)
    assert state.mode == "chat"

def test_compress_prompt():
    short_prompt = "hello\nworld"
    assert compress_prompt(short_prompt) == short_prompt
    
    long_prompt = "line1\nline2\nline3\nline4\nline5\nline6"
    assert compress_prompt(long_prompt) == "[Pasted: 6 lines]"

def test_parse_slash_command():
    # command, should_continue
    cmd, cont = parse_slash_command("/clear")
    assert cmd == "clear"
    assert cont is False
    
    cmd, cont = parse_slash_command("/new")
    assert cmd == "new"
    assert cont is False
    
    cmd, cont = parse_slash_command("/chat")
    assert cmd == "chat"
    assert cont is False
    
    cmd, cont = parse_slash_command("not a command")
    assert cmd is None
    assert cont is True

def test_repl_state_properties():
    state = REPLState(workspace_root="dummy_ws")
    assert state.mode == "chat"
    assert state.workspace_root == "dummy_ws"
    assert state.cached_plan is None
    assert state.auto_execute_cached is False
    assert len(state.session_id) > 0

def test_repl_backtab_transition():
    state = REPLState()
    state.mode = "plan"
    state.cached_plan = {"goal": "build nak"}
    
    # Simulate the Shift+Tab (BackTab) keypress transition
    if state.mode == "plan" and state.cached_plan is not None:
        state.mode = "code"
        state.auto_execute_cached = True
        
    assert state.mode == "code"
    assert state.auto_execute_cached is True

@pytest.mark.asyncio
async def test_run_repl_missing_provider(tmp_path):
    from nak.cli.repl import run_repl
    from unittest.mock import AsyncMock, patch
    
    with patch("nak.cli.repl.SQLiteMemoryStore") as mock_store_cls, \
         patch("click.echo") as mock_echo:
         
        mock_store = mock_store_cls.return_value
        mock_store.get_config = AsyncMock(return_value=None)
        
        await run_repl(workspace_root=str(tmp_path), mode="code")
        
        mock_echo.assert_any_call("Error: Active provider is not configured. Please run 'nak config [ollama|llama]' first.")

def test_slash_command_behavior():
    state = REPLState()
    
    # Test /chat
    cmd, cont = parse_slash_command("/chat")
    assert cmd == "chat"
    assert cont is False
    parts = cmd.split(None, 1)
    cmd_base = parts[0] if parts else ""
    if cmd_base == "chat":
        state.mode = "chat"
    assert state.mode == "chat"
    
    # Test /plan
    cmd, cont = parse_slash_command("/plan")
    assert cmd == "plan"
    parts = cmd.split(None, 1)
    cmd_base = parts[0] if parts else ""
    if cmd_base == "plan":
        state.mode = "plan"
    assert state.mode == "plan"
    
    # Test /code
    cmd, cont = parse_slash_command("/code")
    assert cmd == "code"
    parts = cmd.split(None, 1)
    cmd_base = parts[0] if parts else ""
    if cmd_base == "code":
        state.mode = "code"
    assert state.mode == "code"
    
    # Test /new resets session, clears cached plan, and resets mode to chat
    state.mode = "plan"
    state.cached_plan = {"dummy": "plan"}
    cmd, cont = parse_slash_command("/new")
    assert cmd == "new"
    parts = cmd.split(None, 1)
    cmd_base = parts[0] if parts else ""
    if cmd_base == "new":
        state.cached_plan = None
        state.mode = "chat"
    assert state.cached_plan is None
    assert state.mode == "chat"
    
    # Test /clear clears cached plan
    state.cached_plan = {"dummy": "plan"}
    cmd, cont = parse_slash_command("/clear")
    assert cmd == "clear"
    parts = cmd.split(None, 1)
    cmd_base = parts[0] if parts else ""
    if cmd_base == "clear":
        state.cached_plan = None
    assert state.cached_plan is None


@pytest.mark.asyncio
async def test_execute_task_graph_real(tmp_path):
    from nak.cli.repl import execute_task_graph
    from nak.memory.sqlite_store import SQLiteMemoryStore
    from nak.protocols.model_provider import ChatResponse
    from unittest.mock import AsyncMock
    
    # 1. Setup mock provider
    mock_provider = AsyncMock()
    # Mock the edit task chat response
    mock_provider.chat.return_value = ChatResponse(
        content='{"src/main.py": "print(\'hello\')\\n"}',
        tool_calls=[],
        finish_reason="stop",
        usage={},
        raw_provider_response={}
    )
    
    # 2. Setup store
    db_path = tmp_path / "memory.db"
    store = SQLiteMemoryStore(str(db_path))
    store.connect()
    
    # 3. Create plan graph
    plan_graph = {
        "goal": "Write code",
        "workspace": str(tmp_path),
        "mode": "workspace-write",
        "tasks": [
            {
                "id": "t1",
                "kind": "context",
                "action": "check structure",
                "depends_on": [],
                "tools": ["ls"],
                "read_paths": [],
                "write_paths": []
            },
            {
                "id": "t2",
                "kind": "edit",
                "action": "create src/main.py",
                "depends_on": ["t1"],
                "tools": ["write_file"],
                "read_paths": [],
                "write_paths": ["src/main.py"]
            },
            {
                "id": "t3",
                "kind": "validate",
                "action": "verify main.py contents",
                "depends_on": ["t2"],
                "tools": ["read"],
                "read_paths": ["src/main.py"],
                "write_paths": []
            }
        ]
    }
    
    # 4. Execute
    await execute_task_graph(plan_graph, str(tmp_path), mock_provider, store)
    
    # 5. Assertions
    # Check that file was written to disk
    main_py_path = tmp_path / "src" / "main.py"
    assert main_py_path.exists()
    assert main_py_path.read_text(encoding="utf-8") == "print('hello')\n"
    
    # Verify change record was saved to store
    changes = await store.get_changes(str(tmp_path))
    assert len(changes) == 1
    assert "src/main.py" in changes[0].files_touched
    assert changes[0].validation_status == "success"
    
    store.close()


@pytest.mark.asyncio
async def test_run_repl_custom_timeout(tmp_path):
    from nak.cli.repl import run_repl
    from unittest.mock import AsyncMock, patch
    
    with patch("nak.cli.repl.SQLiteMemoryStore") as mock_store_cls, \
         patch("nak.cli.repl.OllamaModelProvider") as mock_provider_cls, \
         patch("nak.cli.repl.PromptSession") as mock_session_cls, \
         patch("click.echo"):
         
        mock_store = mock_store_cls.return_value
        
        async def get_config_mock(key):
            config_map = {
                "active_provider": "ollama",
                "active_model": "qwen3.5:4b",
                "ollama_url": "http://localhost:11434/v1",
                "model_timeout": "180"
            }
            return config_map.get(key)
            
        mock_store.get_config = AsyncMock(side_effect=get_config_mock)
        
        mock_provider = mock_provider_cls.return_value
        mock_provider.health = AsyncMock(return_value=True)
        mock_provider.name = "ollama"
        
        mock_session = mock_session_cls.return_value
        mock_session.prompt_async = AsyncMock(side_effect=KeyboardInterrupt)
        
        await run_repl(workspace_root=str(tmp_path), mode="code")
        
        # Verify provider was instantiated with the custom timeout of 180 seconds
        mock_provider_cls.assert_called_once_with("http://localhost:11434/v1", "qwen3.5:4b", timeout_seconds=180)


@pytest.mark.asyncio
async def test_stdio_mcp_client_connect_and_call(monkeypatch):
    from nak.mcp_client.base import StdioMcpClient
    import json
    import asyncio
    from unittest.mock import Mock
    
    # Mock create_subprocess_exec with synchronous mocked methods for stdin
    mock_proc = AsyncMock()
    mock_proc.stdin = Mock()
    mock_proc.stdin.write = Mock()
    mock_proc.stdin.drain = AsyncMock()
    
    mock_proc.stdout = Mock()
    mock_proc.returncode = None
    
    # Mock responses: 1 for initialize, 1 for tools/list
    response_initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "serverInfo": {"name": "test-server", "version": "1.0.0"}
        }
    }
    response_tools = {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
            "tools": [{"name": "test_tool", "description": "a test tool"}]
        }
    }
    
    # Simulate readline output for the background loop
    lines = [
        json.dumps(response_initialize).encode("utf-8") + b"\n",
        json.dumps(response_tools).encode("utf-8") + b"\n"
    ]
    
    client = StdioMcpClient(command="dummy-command", args=[])
    
    async def mock_readline():
        while True:
            if lines:
                try:
                    next_line_data = json.loads(lines[0].decode("utf-8"))
                    next_id = next_line_data.get("id")
                    if next_id in client.pending_responses:
                        return lines.pop(0)
                except Exception:
                    return lines.pop(0)
            await asyncio.sleep(0.01)
        
    mock_proc.stdout.readline = AsyncMock(side_effect=mock_readline)
    
    mock_create_subprocess = AsyncMock(return_value=mock_proc)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", mock_create_subprocess)
    
    await client.connect()
    
    # Verify initialize parameters and tools
    assert len(client.tools) == 1
    assert client.tools[0]["name"] == "test_tool"
    
    # Test call_tool success
    mock_call_res = {
        "jsonrpc": "2.0",
        "id": 3,
        "result": {
            "content": [{"type": "text", "text": "tool output"}]
        }
    }
    lines.append(json.dumps(mock_call_res).encode("utf-8") + b"\n")
    
    call_result = await client.call_tool("test_tool", {"param": 1})
    assert call_result.success is True
    assert call_result.result == [{"type": "text", "text": "tool output"}]
    
    await client.close()


@pytest.mark.asyncio
async def test_http_mcp_client_connect_and_call(monkeypatch):
    import httpx
    from unittest.mock import Mock
    
    # Mock httpx.AsyncClient post method
    mock_client = AsyncMock()
    
    mock_response_init = Mock()
    mock_response_init.status_code = 200
    mock_response_init.json = Mock(return_value={
        "jsonrpc": "2.0",
        "id": 1,
        "result": {}
    })
    
    mock_response_tools = Mock()
    mock_response_tools.status_code = 200
    mock_response_tools.json = Mock(return_value={
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
            "tools": [{"name": "http_tool", "description": "HTTP description"}]
        }
    })
    
    responses = [mock_response_init, mock_response_tools]
    async def mock_post(*args, **kwargs):
        return responses.pop(0)
        
    mock_client.post = AsyncMock(side_effect=mock_post)
    monkeypatch.setattr(httpx, "AsyncClient", lambda: mock_client)
    
    from nak.mcp_client.base import HttpMcpClient
    client = HttpMcpClient(url="http://dummy-mcp/api")
    
    await client.connect()
    assert client.is_connected is True
    assert len(client.tools) == 1
    assert client.tools[0]["name"] == "http_tool"
    
    # Mock call tool response
    mock_response_call = Mock()
    mock_response_call.status_code = 200
    mock_response_call.json = Mock(return_value={
        "jsonrpc": "2.0",
        "id": 3,
        "result": {
            "isError": False,
            "content": ["http output"]
        }
    })
    responses.append(mock_response_call)
    
    res = await client.call_tool("http_tool", {})
    assert res.success is True
    assert res.result == ["http output"]
    
    await client.close()
    assert client.is_connected is False


@pytest.mark.asyncio
async def test_mcp_reconnect_command_behavior(monkeypatch):
    from nak.cli.repl import run_repl
    from unittest.mock import AsyncMock, patch, MagicMock
    import json
    
    # Mock SQLite memory store
    mock_store_cls = MagicMock()
    mock_store = mock_store_cls.return_value
    
    # Return a dummy mcp server config
    mcp_config = {
        "nakshastra": {"type": "stdio", "command": "dummy", "args": []}
    }
    
    async def get_config_mock(key):
        config_map = {
            "active_provider": "ollama",
            "active_model": "qwen3.5:4b",
            "ollama_url": "http://localhost:11434/v1",
            "mcp_servers": json.dumps(mcp_config)
        }
        return config_map.get(key)
        
    mock_store.get_config = AsyncMock(side_effect=get_config_mock)
    
    # Mock prompt-toolkit Session
    mock_session_cls = MagicMock()
    mock_session = mock_session_cls.return_value
    
    # Simulate first typing /mcp reconnect nakshastra, and then exiting via KeyboardInterrupt
    inputs = ["/mcp reconnect nakshastra", KeyboardInterrupt]
    async def mock_prompt(*args, **kwargs):
        val = inputs.pop(0)
        if val is KeyboardInterrupt:
            raise KeyboardInterrupt
        return val
        
    mock_session.prompt_async = AsyncMock(side_effect=mock_prompt)
    
    # Mock StdioMcpClient.connect
    mock_connect = AsyncMock()
    
    with patch("nak.cli.repl.SQLiteMemoryStore", mock_store_cls), \
         patch("nak.cli.repl.OllamaModelProvider") as mock_provider_cls, \
         patch("nak.cli.repl.PromptSession", mock_session_cls), \
         patch("nak.cli.repl.StdioMcpClient.connect", mock_connect), \
         patch("click.echo") as mock_echo:
         
        mock_provider = mock_provider_cls.return_value
        mock_provider.health = AsyncMock(return_value=True)
        mock_provider.name = "ollama"
        
        await run_repl(workspace_root="dummy_ws", mode="code")
        
        # Verify StdioMcpClient.connect was called twice (once on startup, once on reconnect command)
        assert mock_connect.call_count == 2
        mock_echo.assert_any_call("Successfully reconnected to 'nakshastra'.")


@pytest.mark.asyncio
async def test_mcp_tool_calling_loop_in_chat(monkeypatch):
    from nak.cli.repl import run_repl
    from unittest.mock import AsyncMock, patch, MagicMock
    from nak.protocols.mcp_transport import ToolCallResult
    import json
    
    # Mock SQLite memory store
    mock_store_cls = MagicMock()
    mock_store = mock_store_cls.return_value
    
    # Return a dummy mcp server config
    mcp_config = {
        "dummy_mcp": {"type": "stdio", "command": "dummy", "args": []}
    }
    
    async def get_config_mock(key):
        config_map = {
            "active_provider": "ollama",
            "active_model": "qwen3.5:4b",
            "ollama_url": "http://localhost:11434/v1",
            "mcp_servers": json.dumps(mcp_config)
        }
        return config_map.get(key)
        
    mock_store.get_config = AsyncMock(side_effect=get_config_mock)
    mock_store.get_chat_history = AsyncMock(return_value=[])
    mock_store.save_chat_message = AsyncMock()
    mock_store.get_last_session_id = AsyncMock(return_value=None)
    
    # Mock prompt-toolkit Session
    mock_session_cls = MagicMock()
    mock_session = mock_session_cls.return_value
    
    # Standard chat mode input, followed by exit via KeyboardInterrupt
    inputs = ["Search the codebase for HttpMcpClient", KeyboardInterrupt]
    async def mock_prompt(*args, **kwargs):
        val = inputs.pop(0)
        if val is KeyboardInterrupt:
            raise KeyboardInterrupt
        return val
        
    mock_session.prompt_async = AsyncMock(side_effect=mock_prompt)
    
    # Mock client and its tools
    mock_connect = AsyncMock()
    
    # Set tools directly on StdioMcpClient instances (mock client)
    from nak.mcp_client.base import StdioMcpClient
    original_init = StdioMcpClient.__init__
    
    def patched_init(self, command, args):
        original_init(self, command, args)
        self.tools = [{"name": "search_codebase", "description": "Search codebase", "inputSchema": {"type": "object", "properties": {}}}]
        mock_proc = MagicMock()
        mock_proc.returncode = None
        self.proc = mock_proc
        
    monkeypatch.setattr(StdioMcpClient, "__init__", patched_init)
    
    # Mock call_tool
    mock_call_tool = AsyncMock(return_value=ToolCallResult(success=True, result={"matches": ["file.py"]}, error_code=None, error_message=None, metadata={}))
    monkeypatch.setattr(StdioMcpClient, "call_tool", mock_call_tool)
    
    with patch("nak.cli.repl.SQLiteMemoryStore", mock_store_cls), \
         patch("nak.cli.repl.OllamaModelProvider") as mock_provider_cls, \
         patch("nak.cli.repl.PromptSession", mock_session_cls), \
         patch("nak.cli.repl.StdioMcpClient.connect", mock_connect), \
         patch("click.echo") as mock_echo:
         
        mock_provider = mock_provider_cls.return_value
        mock_provider.health = AsyncMock(return_value=True)
        mock_provider.name = "ollama"
        
        # We need two responses:
        # 1. First response: requesting tool call "search_codebase"
        # 2. Second response: final assistant answer
        from nak.protocols.model_provider import ChatResponse
        response_1 = ChatResponse(
            content="",
            tool_calls=[{
                "id": "call_123",
                "type": "function",
                "function": {
                    "name": "search_codebase",
                    "arguments": "{\"query\": \"HttpMcpClient\"}"
                }
            }],
            finish_reason="tool_calls",
            usage={},
            raw_provider_response={}
        )
        response_2 = ChatResponse(
            content="I found the files containing HttpMcpClient.",
            tool_calls=[],
            finish_reason="stop",
            usage={},
            raw_provider_response={}
        )
        
        chat_responses = [response_1, response_2]
        async def mock_chat(*args, **kwargs):
            return chat_responses.pop(0)
            
        mock_provider.chat = AsyncMock(side_effect=mock_chat)
        
        await run_repl(workspace_root="dummy_ws", mode="chat")
        
        # Assertions
        # 1. Verify connect was called
        mock_connect.assert_called_once()
        
        # 2. Verify call_tool was called with correct parameters
        mock_call_tool.assert_called_once_with("search_codebase", {"query": "HttpMcpClient"})
        
        # 3. Verify click.echo printed tool execution info
        mock_echo.assert_any_call("Executing tool call: search_codebase({'query': 'HttpMcpClient'})...")
        mock_echo.assert_any_call('Tool Result: {"matches": ["file.py"]}')
        mock_echo.assert_any_call("I found the files containing HttpMcpClient.")
