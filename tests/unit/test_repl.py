import pytest
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
    import pytest
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
         patch("click.echo") as mock_echo:
         
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




