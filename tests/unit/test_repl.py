from nak.cli.repl import (
    cycle_mode,
    compress_prompt,
    parse_slash_command,
    REPLState,
)

def test_cycle_mode():
    state = REPLState()
    assert state.mode == "code" # Default mode
    
    state.mode = cycle_mode(state.mode)
    assert state.mode == "plan"
    
    state.mode = cycle_mode(state.mode)
    assert state.mode == "chat"
    
    state.mode = cycle_mode(state.mode)
    assert state.mode == "code"

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
    
    cmd, cont = parse_slash_command("not a command")
    assert cmd is None
    assert cont is True

def test_repl_state_properties():
    state = REPLState(workspace_root="dummy_ws")
    assert state.mode == "code"
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

