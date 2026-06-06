import os
import uuid
import json
import asyncio
import click
from typing import Dict, Any, Optional, Tuple
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.completion import WordCompleter

from nak.memory.sqlite_store import SQLiteMemoryStore
from nak.model_adapter.providers.ollama import OllamaModelProvider
from nak.planner.planner import Planner
from nak.protocols.model_provider import ChatRequest, ModelProvider
from nak.scheduler.scheduler import Scheduler, Task, TaskResult
from nak.workspace_fs.fs import WorkspaceFS
from nak.protocols.memory_store import ChangeRecord
from nak.mcp_client.base import StdioMcpClient, HttpMcpClient


class REPLState:
    def __init__(self, workspace_root: str = ".") -> None:
        self.mode: str = "chat"
        self.session_id: str = str(uuid.uuid4())
        self.cached_plan: Optional[Dict[str, Any]] = None
        self.workspace_root: str = workspace_root
        self.auto_execute_cached: bool = False
        self.mcp_clients: Dict[str, Any] = {}

def cycle_mode(current: str) -> str:
    modes = ["chat", "plan", "code"]
    idx = modes.index(current)
    return modes[(idx + 1) % len(modes)]

def compress_prompt(prompt: str) -> str:
    lines = prompt.splitlines()
    if len(lines) > 5:
        return f"[Pasted: {len(lines)} lines]"
    return prompt

def parse_slash_command(text: str) -> Tuple[Optional[str], bool]:
    cleaned = text.strip()
    if cleaned.startswith("/"):
        cmd = cleaned[1:]
        return cmd, False
    return None, True

async def execute_task_graph(
    plan_graph: Dict[str, Any],
    workspace_root: str,
    provider: ModelProvider,
    store: SQLiteMemoryStore
) -> None:
    scheduler = Scheduler()
    fs = WorkspaceFS(workspace_root)
    task_outputs: Dict[str, str] = {}
    files_written = set()
    all_success = True
    tasks = []

    def create_action(t):
        async def action():
            tid = t["id"]
            kind = t.get("kind", "non-model")
            action_desc = t.get("action", "unknown action")
            tools = t.get("tools", [])
            read_paths = t.get("read_paths", [])
            write_paths = t.get("write_paths", [])
            depends_on = t.get("depends_on", [])
            
            click.echo(f"  Executing task {tid}: {action_desc}...")
            
            try:
                if kind in ("context", "read"):
                    output_parts = []
                    if any(tool in ("ls", "list_dir") for tool in tools):
                        dir_to_list = read_paths[0] if read_paths else "."
                        try:
                            items = fs.list_dir(dir_to_list)
                            output_parts.append(f"Directory listing of '{dir_to_list}': {', '.join(items)}")
                        except Exception as e:
                            output_parts.append(f"Failed to list directory '{dir_to_list}': {str(e)}")
                    
                    for p in read_paths:
                        try:
                            content = fs.read_file(p)
                            output_parts.append(f"File content of '{p}':\n{content}")
                        except Exception as e:
                            output_parts.append(f"Failed to read file '{p}': {str(e)}")
                            
                    output = "\n\n".join(output_parts) if output_parts else "No context read."
                    task_outputs[tid] = output
                    return TaskResult(success=True, output=output, error_message=None)
                    
                elif kind == "edit":
                    dep_ctx = ""
                    for dep_id in depends_on:
                        if dep_id in task_outputs:
                            dep_ctx += f"--- Context from Dependency Task {dep_id} ---\n{task_outputs[dep_id]}\n"
                            
                    current_contents = ""
                    for p in write_paths:
                        try:
                            content = fs.read_file(p)
                            current_contents += f"--- Current Content of '{p}' ---\n{content}\n"
                        except FileNotFoundError:
                            pass
                            
                    prompt = (
                        f"You are executing an 'edit' task as part of a plan.\n"
                        f"Goal: {plan_graph.get('goal', '')}\n"
                        f"Workspace: {workspace_root}\n"
                        f"Task Action: {action_desc}\n"
                        f"Files to write/update: {write_paths}\n"
                        f"Files to read: {read_paths}\n\n"
                    )
                    if dep_ctx:
                        prompt += f"Dependency Context:\n{dep_ctx}\n"
                    if current_contents:
                        prompt += f"Current file contents:\n{current_contents}\n"
                        
                    prompt += (
                        "Please generate the complete content of the file(s) that need to be written or updated.\n"
                        "You MUST return a JSON object where the keys are the relative file paths from 'write_paths' and the values are the complete new contents of the files.\n"
                        "Do not wrap in markdown or include thinking blocks. Return ONLY the raw JSON object.\n"
                        "Example format:\n"
                        "{\n"
                        '  "src/main.py": "print(\'hello\')\\n"\n'
                        "}\n"
                    )
                    
                    chat_req = ChatRequest(
                       system="You are a precise AI code generator. Return only raw JSON mapping relative file paths to their complete contents.",
                       prompt=prompt,
                       response_format="json",
                       tools=[],
                       max_tokens=4096,
                       temperature=0.0,
                       metadata={}
                    )
                    response = await provider.chat(chat_req)
                    
                    content = response.content.strip()
                    if content.startswith("```"):
                        lines = content.splitlines()
                        if lines[0].startswith("```"):
                            lines = lines[1:]
                        if lines and lines[-1].startswith("```"):
                            lines = lines[:-1]
                        content = "\n".join(lines).strip()
                        
                    try:
                        files_map = json.loads(content)
                        if not isinstance(files_map, dict):
                            raise ValueError("Expected a JSON object mapping file paths to content")
                    except Exception as e:
                        return TaskResult(
                            success=False,
                            output=None,
                            error_message=f"Model failed to return valid JSON object. Error: {str(e)}. Content: {response.content}"
                        )
                        
                    for path, body in files_map.items():
                        fs.write_file(path, body)
                        files_written.add(path)
                        click.echo(f"    [File Written] {path}")
                        
                    output = f"Successfully wrote/updated files: {list(files_map.keys())}"
                    task_outputs[tid] = output
                    return TaskResult(success=True, output=output, error_message=None)
                    
                elif kind == "validate":
                    output_parts = []
                    if any(tool in ("cat", "read") for tool in tools):
                        for p in read_paths:
                            try:
                                content = fs.read_file(p)
                                click.echo(f"\n--- Content of '{p}' ---")
                                click.echo(content)
                                click.echo("-------------------------\n")
                                output_parts.append(f"Validated contents of '{p}'.")
                            except Exception as e:
                                output_parts.append(f"Failed to read '{p}': {str(e)}")
                                
                    cmd_tools = [tool for tool in tools if tool not in ("cat", "read", "ls", "list_dir", "write", "write_file")]
                    for tool in cmd_tools:
                        try:
                            from nak.validator.autodetect import resolve_executable
                            exe_path = resolve_executable(tool)
                        except FileNotFoundError:
                            exe_path = tool
                            
                        cmd_args = [exe_path]
                        if tool == "javac":
                            cmd_args.extend(read_paths or write_paths)
                        elif tool == "pytest":
                            cmd_args.extend(read_paths)
                            
                        click.echo(f"    Running validation command: {' '.join(cmd_args)}")
                        try:
                            proc = await asyncio.create_subprocess_exec(
                                *cmd_args,
                                cwd=workspace_root,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE
                           )
                            stdout, stderr = await proc.communicate()
                            stdout_str = stdout.decode("utf-8", errors="replace")
                            stderr_str = stderr.decode("utf-8", errors="replace")
                           
                            if proc.returncode == 0:
                                output_parts.append(f"Command '{tool}' succeeded with output:\n{stdout_str}")
                            else:
                                error_msg = f"Command '{tool}' failed with exit code {proc.returncode}.\nStdout:\n{stdout_str}\nStderr:\n{stderr_str}"
                                return TaskResult(success=False, output=None, error_message=error_msg)
                        except Exception as e:
                            return TaskResult(success=False, output=None, error_message=f"Failed to execute command '{tool}': {str(e)}")
                            
                    output = "\n".join(output_parts) if output_parts else "No validation tools executed."
                    task_outputs[tid] = output
                    return TaskResult(success=True, output=output, error_message=None)
                    
                elif kind == "remember":
                    output = f"Remembering status of goal '{plan_graph.get('goal', '')}'"
                    task_outputs[tid] = output
                    return TaskResult(success=True, output=output, error_message=None)
                    
                else:
                    output = f"Executed {kind} task."
                    task_outputs[tid] = output
                    return TaskResult(success=True, output=output, error_message=None)
                    
            except Exception as e:
                return TaskResult(success=False, output=None, error_message=f"Error executing task: {str(e)}")
                
        return action

    for t in plan_graph.get("tasks", []):
        task_id = t["id"]
        tasks.append(
            Task(
                id=task_id,
                kind=t.get("kind", "non-model"),
                depends_on=t.get("depends_on", []),
                action=create_action(t),
                read_paths=t.get("read_paths", []),
                write_paths=t.get("write_paths", [])
            )
        )
        
    results = await scheduler.run(tasks)
    
    click.echo("\nExecution results:")
    for tid, res in results.items():
        if res.success:
            click.echo(f"  Task {tid}: success")
        else:
            click.echo(f"  Task {tid}: failed - {res.error_message}")
            all_success = False

    if files_written:
        change_rec = ChangeRecord(
            id=str(uuid.uuid4()),
            workspace=workspace_root,
            request=plan_graph.get("goal", "Coding task"),
            files_touched=list(files_written),
            patch_summary=f"Executed plan: {plan_graph.get('goal', '')}",
            validation_status="success" if all_success else "failed",
            metadata={}
        )
        try:
            await store.save_change(change_rec)
        except Exception as e:
            click.echo(f"Warning: Failed to save change record to store: {str(e)}")


async def run_repl(workspace_root: str, mode: str, provider: Optional[ModelProvider] = None) -> None:
    state = REPLState(workspace_root=workspace_root)
    
    # Init store
    db_path = os.path.join(workspace_root, ".nak", "memory.db")
    store = SQLiteMemoryStore(db_path)
    store.connect()
    
    # Try resuming last session
    try:
        last_session = await store.get_last_session_id()
        if last_session:
            state.session_id = last_session
    except Exception:
        pass
        
    # Init provider if not passed
    if not provider:
        provider_name = await store.get_config("active_provider")
        if not provider_name:
            click.echo("Error: Active provider is not configured. Please run 'nak config [ollama|llama]' first.")
            store.close()
            return
            
        model_name = await store.get_config("active_model")
        if not model_name:
            click.echo("Error: Active model is not configured. Please run 'nak model set <model_name>' first.")
            store.close()
            return
            
        ollama_url = await store.get_config("ollama_url")
        llama_url = await store.get_config("llama_url")
        timeout_val = await store.get_config("model_timeout")
        timeout_seconds = int(timeout_val) if timeout_val else 300
        
        if provider_name == "llama":
            if not llama_url:
                click.echo("Error: Llama Local URL is not configured. Please run 'nak config llama --local <url>' first.")
                store.close()
                return
            from nak.model_adapter.providers.llama import LlamaModelProvider
            provider = LlamaModelProvider(llama_url, model_name, timeout_seconds=timeout_seconds)
        else:
            if not ollama_url:
                click.echo("Error: Ollama Local URL is not configured. Please run 'nak config ollama --local <url>' first.")
                store.close()
                return
            provider = OllamaModelProvider(ollama_url, model_name, timeout_seconds=timeout_seconds)
            
    # Check if provider is healthy/online (non-blocking warning)
    if not await provider.health():
        click.echo(f"Warning: Active provider {provider.name} is offline. Please make sure your provider is running and connected.")
        
    planner = Planner(provider)

    # Load and connect to configured MCP servers on startup
    mcp_config_str = await store.get_config("mcp_servers")
    if mcp_config_str:
        try:
            mcp_configs = json.loads(mcp_config_str)
            for name, cfg in mcp_configs.items():
                mcp_type = cfg.get("type", "stdio")
                client: Any
                if mcp_type == "stdio":
                    cmd = cfg.get("command")
                    args = cfg.get("args", [])
                    client = StdioMcpClient(cmd, args)
                else:
                    url = cfg.get("url")
                    client = HttpMcpClient(url)
                
                click.echo(f"Connecting to MCP server '{name}' ({mcp_type})...")
                try:
                    await asyncio.wait_for(client.connect(), timeout=5.0)
                    state.mcp_clients[name] = client
                    click.echo(f"  Connected to '{name}' successfully.")
                except Exception as e:
                    state.mcp_clients[name] = client  # Still store it so it displays Disconnected
                    click.echo(f"  Failed to connect to '{name}': {str(e)}")
        except Exception as e:
            click.echo(f"Warning: Failed to load MCP configurations: {str(e)}")
    
    # Setup prompt-toolkit session with keybindings and bottom toolbar
    kb = KeyBindings()
    
    @kb.add(Keys.BackTab)
    def _(event):
        if state.mode == "plan" and state.cached_plan is not None:
            state.mode = "code"
            state.auto_execute_cached = True
            event.app.exit(result="auto_execute")
        else:
            state.mode = cycle_mode(state.mode)
            event.app.invalidate()
            
    commands_completer = WordCompleter(["/chat", "/plan", "/code", "/new", "/clear", "/help", "/mcp"])
    
    def get_rprompt():
        connected_count = len([
            c for c in state.mcp_clients.values() 
            if (isinstance(c, StdioMcpClient) and c.proc and c.proc.returncode is None) 
            or (isinstance(c, HttpMcpClient) and c.is_connected)
        ])
        return HTML(f"<style bg='ansigray' fg='ansiblack'> MCP: {connected_count} </style>")
    
    session: PromptSession[Any] = PromptSession(
        key_bindings=kb,
        bottom_toolbar=lambda: HTML(f"<b>[MODE: {state.mode.upper()}]</b>"),
        rprompt=get_rprompt,
        completer=commands_completer,
        complete_while_typing=True
    )
    
    click.echo("NAK CLI REPL Shell. Press Ctrl+C or Ctrl+D to exit.")
    click.echo("Press Shift+Tab to switch modes between CODE, PLAN, and CHAT.")
    click.echo("Available slash commands: /chat, /plan, /code, /new, /clear, /help, /mcp")
    
    while True:
        try:
            # Dynamically set prompt string based on current mode
            prompt_str = f"nak ({state.mode})> "
            user_input = await session.prompt_async(prompt_str)
            
            if user_input == "auto_execute":
                click.echo("[Auto-execution triggered: switching to Code Mode and executing cached plan]")
                if state.cached_plan:
                    await execute_task_graph(state.cached_plan, workspace_root, provider, store)
                state.cached_plan = None
                state.auto_execute_cached = False
                continue
                
            if not user_input.strip():
                continue
                
            # Parse slash command
            cmd_name, should_continue = parse_slash_command(user_input)
            if not should_continue and cmd_name is not None:
                parts = cmd_name.split(None, 1)
                cmd_base = parts[0] if parts else ""
                
                if cmd_base == "clear":
                    click.clear()
                    state.cached_plan = None
                elif cmd_base == "new":
                    state.session_id = str(uuid.uuid4())
                    state.cached_plan = None
                    state.mode = "chat"
                    click.echo("Started a new chat session (mode reset to CHAT).")
                elif cmd_base == "chat":
                    state.mode = "chat"
                    click.echo("Switched to CHAT mode.")
                elif cmd_base == "plan":
                    state.mode = "plan"
                    click.echo("Switched to PLAN mode.")
                elif cmd_base == "code":
                    state.mode = "code"
                    click.echo("Switched to CODE mode.")
                elif cmd_base == "mcp":
                    mcp_args = parts[1].split() if len(parts) > 1 else []
                    if not mcp_args:
                        if not state.mcp_clients:
                            click.echo("No MCP servers configured.")
                            click.echo("Usage:")
                            click.echo("  /mcp add <name> stdio <command> [args...]")
                            click.echo("  /mcp add <name> http <url>")
                            click.echo("  /mcp reconnect <name>")
                            click.echo("  /mcp remove <name>")
                        else:
                            click.echo("Configured MCP Servers:")
                            for name, client in state.mcp_clients.items():
                                mcp_type = "stdio" if isinstance(client, StdioMcpClient) else "http"
                                status = "Disconnected"
                                if mcp_type == "stdio":
                                    if client.proc and client.proc.returncode is None:
                                        status = "Connected"
                                else:
                                    if client.is_connected:
                                        status = "Connected"
                                click.echo(f"  - {name} ({mcp_type}): {status}")
                                if status == "Connected" and client.tools:
                                    click.echo("    Tools:")
                                    for t in client.tools:
                                        t_name = t.get("name", "unknown")
                                        t_desc = t.get("description", "")
                                        if len(t_desc) > 80:
                                            t_desc = t_desc[:77] + "..."
                                        click.echo(f"      * {t_name}: {t_desc}")
                    elif mcp_args[0] == "add":
                        if len(mcp_args) < 4:
                            click.echo("Error: Invalid arguments.")
                            click.echo("Usage:")
                            click.echo("  /mcp add <name> stdio <command> [args...]")
                            click.echo("  /mcp add <name> http <url>")
                        else:
                            name = mcp_args[1]
                            mcp_type = mcp_args[2]
                            if mcp_type not in ("stdio", "http"):
                                click.echo("Error: type must be 'stdio' or 'http'.")
                            else:
                                if mcp_type == "stdio":
                                    cmd = mcp_args[3]
                                    args = mcp_args[4:]
                                    new_cfg = {"type": "stdio", "command": cmd, "args": args}
                                    client = StdioMcpClient(cmd, args)
                                else:
                                    url = mcp_args[3]
                                    new_cfg = {"type": "http", "url": url}
                                    client = HttpMcpClient(url)
                                
                                # Save to DB
                                mcp_config_str = await store.get_config("mcp_servers")
                                mcp_configs = json.loads(mcp_config_str) if mcp_config_str else {}
                                mcp_configs[name] = new_cfg
                                await store.set_config("mcp_servers", json.dumps(mcp_configs))
                                
                                # Disconnect old if exists
                                if name in state.mcp_clients:
                                    await state.mcp_clients[name].close()
                                
                                click.echo(f"Connecting to MCP server '{name}' ({mcp_type})...")
                                try:
                                    await asyncio.wait_for(client.connect(), timeout=5.0)
                                    state.mcp_clients[name] = client
                                    click.echo(f"Successfully configured and connected to '{name}'.")
                                except Exception as e:
                                    state.mcp_clients[name] = client
                                    click.echo(f"Configured but failed to connect to '{name}': {str(e)}")
                    elif mcp_args[0] == "remove":
                        if len(mcp_args) < 2:
                            click.echo("Usage: /mcp remove <name>")
                        else:
                            name = mcp_args[1]
                            mcp_config_str = await store.get_config("mcp_servers")
                            mcp_configs = json.loads(mcp_config_str) if mcp_config_str else {}
                            if name in mcp_configs:
                                del mcp_configs[name]
                                await store.set_config("mcp_servers", json.dumps(mcp_configs))
                            if name in state.mcp_clients:
                                await state.mcp_clients[name].close()
                                del state.mcp_clients[name]
                            click.echo(f"Removed MCP server '{name}'.")
                    elif mcp_args[0] == "reconnect":
                        if len(mcp_args) < 2:
                            click.echo("Usage: /mcp reconnect <name>")
                        else:
                            name = mcp_args[1]
                            mcp_config_str = await store.get_config("mcp_servers")
                            mcp_configs = json.loads(mcp_config_str) if mcp_config_str else {}
                            if name not in mcp_configs:
                                click.echo(f"Error: MCP server '{name}' is not configured.")
                            else:
                                cfg = mcp_configs[name]
                                mcp_type = cfg.get("type", "stdio")
                                if mcp_type == "stdio":
                                    cmd = cfg.get("command")
                                    args = cfg.get("args", [])
                                    client = StdioMcpClient(cmd, args)
                                else:
                                    url = cfg.get("url")
                                    client = HttpMcpClient(url)
                                
                                # Close old if exists
                                if name in state.mcp_clients:
                                    try:
                                        await state.mcp_clients[name].close()
                                    except Exception:
                                        pass
                                
                                click.echo(f"Reconnecting to MCP server '{name}' ({mcp_type})...")
                                try:
                                    await asyncio.wait_for(client.connect(), timeout=5.0)
                                    state.mcp_clients[name] = client
                                    click.echo(f"Successfully reconnected to '{name}'.")
                                except Exception as e:
                                    state.mcp_clients[name] = client
                                    click.echo(f"Failed to reconnect to '{name}': {str(e)}")
                    else:
                        click.echo("Unknown MCP subcommand. Use '/mcp', '/mcp add ...', '/mcp reconnect ...', or '/mcp remove ...'")
                elif cmd_base in ["", "help"]:
                    click.echo("Available slash commands:")
                    click.echo("  /chat  - Switch to CHAT mode")
                    click.echo("  /plan  - Switch to PLAN mode")
                    click.echo("  /code  - Switch to CODE mode")
                    click.echo("  /new   - Start a new session, clear cached plan, switch to CHAT mode")
                    click.echo("  /clear - Clear the screen and clear cached plan")
                    click.echo("  /mcp   - Manage/configure MCP connections")
                    click.echo("  /help  - Show this help message")
                else:
                    click.echo(f"Unknown slash command: /{cmd_base}")
                continue
                
            # Log history with compression for display
            compressed = compress_prompt(user_input)
            if compressed != user_input:
                click.echo(f"Prompt: {compressed}")
                
            # Run based on current mode
            if state.mode == "chat":
                history = await store.get_chat_history(state.session_id)
                await store.save_chat_message(state.session_id, "user", user_input)
                
                formatted_history = ""
                for msg in history:
                    formatted_history += f"{msg['role'].capitalize()}: {msg['content']}\n"
                    
                full_prompt = user_input
                if formatted_history:
                    full_prompt = f"Chat History:\n{formatted_history}\nUser: {user_input}"
                
                # Retrieve and format connected MCP tools
                mcp_tools = []
                for client in state.mcp_clients.values():
                    status = "Disconnected"
                    if isinstance(client, StdioMcpClient):
                        if client.proc and client.proc.returncode is None:
                            status = "Connected"
                    else:
                        if client.is_connected:
                            status = "Connected"
                    
                    if status == "Connected":
                        for t in client.tools:
                            mcp_tools.append({
                                "type": "function",
                                "function": {
                                    "name": t.get("name"),
                                    "description": t.get("description", ""),
                                    "parameters": t.get("inputSchema", {"type": "object", "properties": {}})
                                }
                            })
                
                system_prompt = "You are a helpful programming assistant."
                if mcp_tools:
                    tool_names_list = []
                    for t in mcp_tools:
                        func = t.get("function")
                        if isinstance(func, dict):
                            name = func.get("name")
                            if name:
                                tool_names_list.append(name)
                    tool_names = ", ".join(tool_names_list)
                    system_prompt += (
                        f" You are connected to the local workspace and have access to Model Context Protocol (MCP) tools: {tool_names}."
                        " You should actively use these tools to read files, search the codebase, check definitions, or inspect code structure"
                        " to answer the user's questions accurately. If you need to look at code or search the project, call the relevant tool."
                    )
                    
                click.echo("Generating response...")
                chat_req = ChatRequest(
                    system=system_prompt,
                    prompt=full_prompt,
                    response_format=None,
                    tools=mcp_tools,
                    max_tokens=2048,
                    temperature=0.7,
                    metadata={}
                )
                response = await provider.chat(chat_req)
                
                # Tool calling loop
                while response.tool_calls:
                    for tc in response.tool_calls:
                        func = tc.get("function", {})
                        func_name = func.get("name")
                        func_args_str = func.get("arguments", "{}")
                        try:
                            func_args = json.loads(func_args_str) if isinstance(func_args_str, str) else func_args_str
                        except Exception:
                            func_args = {}
                        
                        click.echo(f"Executing tool call: {func_name}({func_args})...")
                        
                        target_client = None
                        for client in state.mcp_clients.values():
                            if any(t.get("name") == func_name for t in client.tools):
                                target_client = client
                                break
                        
                        if target_client:
                            tc_res = await target_client.call_tool(func_name, func_args)
                            if tc_res.success:
                                tool_result_str = json.dumps(tc_res.result)
                            else:
                                tool_result_str = f"Error calling tool: {tc_res.error_message}"
                        else:
                            tool_result_str = f"Error: Tool '{func_name}' not found among connected MCP clients."
                        
                        click.echo(f"Tool Result: {tool_result_str}")
                        full_prompt += f"\n\n[Assistant requested tool: {func_name} with arguments {func_args}]"
                        full_prompt += f"\n[Tool Result]: {tool_result_str}"
                    
                    click.echo("Generating follow-up response...")
                    chat_req = ChatRequest(
                        system=system_prompt,
                        prompt=full_prompt,
                        response_format=None,
                        tools=mcp_tools,
                        max_tokens=2048,
                        temperature=0.7,
                        metadata={}
                    )
                    response = await provider.chat(chat_req)
                
                click.echo(response.content)
                await store.save_chat_message(state.session_id, "assistant", response.content)
                
            elif state.mode == "plan":
                changes = await store.get_changes(workspace_root)
                recent_changes = changes[-5:]
                
                click.echo("Generating execution plan...")
                plan_graph = await planner.plan(user_input, workspace_root, mode, recent_changes)
                state.cached_plan = plan_graph
                click.echo("Plan generated:")
                click.echo(json.dumps(plan_graph, indent=2))
                
            elif state.mode == "code":
                changes = await store.get_changes(workspace_root)
                recent_changes = changes[-5:]
                
                click.echo("Generating execution plan...")
                plan_graph = await planner.plan(user_input, workspace_root, mode, recent_changes)
                click.echo("Plan generated:")
                click.echo(json.dumps(plan_graph, indent=2))
                
                while True:
                    choice = click.prompt("Approve plan? [Y]es / [N]o / [E]edit", default="y").strip().lower()
                    if choice in ["y", "yes"]:
                        await execute_task_graph(plan_graph, workspace_root, provider, store)
                        break
                    elif choice in ["n", "no"]:
                        click.echo("Plan discarded.")
                        break
                    elif choice in ["e", "edit"]:
                        feedback = click.prompt("Enter additional instructions / refinement")
                        user_input = f"{user_input}\nRefinement instructions: {feedback}"
                        click.echo("Regenerating plan...")
                        plan_graph = await planner.plan(user_input, workspace_root, mode, recent_changes)
                        click.echo("New plan generated:")
                        click.echo(json.dumps(plan_graph, indent=2))
                    else:
                        click.echo("Invalid choice. Please enter Y, N, or E.")
                        
        except (KeyboardInterrupt, EOFError):
            click.echo("\nExiting REPL.")
            break
        except Exception as e:
            click.echo(f"Error: {str(e)}")
            
    # Cleanup all connected MCP clients
    for client in list(state.mcp_clients.values()):
        try:
            await client.close()
        except Exception:
            pass
    store.close()
