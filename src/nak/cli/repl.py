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

from nak.memory.sqlite_store import SQLiteMemoryStore
from nak.model_adapter.providers.ollama import OllamaModelProvider
from nak.planner.planner import Planner
from nak.protocols.model_provider import ChatRequest, ModelProvider
from nak.scheduler.scheduler import Scheduler, Task, TaskResult

class REPLState:
    def __init__(self, workspace_root: str = ".") -> None:
        self.mode: str = "code"
        self.session_id: str = str(uuid.uuid4())
        self.cached_plan: Optional[Dict[str, Any]] = None
        self.workspace_root: str = workspace_root
        self.auto_execute_cached: bool = False

def cycle_mode(current: str) -> str:
    modes = ["code", "plan", "chat"]
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

async def execute_task_graph(plan_graph: Dict[str, Any]) -> None:
    scheduler = Scheduler()
    tasks = []
    
    for t in plan_graph.get("tasks", []):
        task_id = t["id"]
        action_desc = t.get("action", "unknown action")
        
        async def make_action(tid=task_id, desc=action_desc):
            click.echo(f"  Executing task {tid}: {desc}...")
            await asyncio.sleep(0.05)
            return TaskResult(success=True, output=f"result-{tid}", error_message=None)
            
        tasks.append(
            Task(
                id=task_id,
                kind=t.get("kind", "non-model"),
                depends_on=t.get("depends_on", []),
                action=make_action,
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
        provider_name = await store.get_config("active_provider") or "ollama"
        model_name = await store.get_config("active_model") or "qwen3.5:4b"
        ollama_url = await store.get_config("ollama_url") or "http://localhost:11434/v1"
        llama_url = await store.get_config("llama_url") or "http://localhost:8080/v1"
        
        if provider_name == "llama":
            from nak.model_adapter.providers.llama import LlamaModelProvider
            provider = LlamaModelProvider(llama_url, model_name)
        else:
            provider = OllamaModelProvider(ollama_url, model_name)
        
    planner = Planner(provider)
    
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
            
    session: PromptSession[Any] = PromptSession(
        key_bindings=kb,
        bottom_toolbar=lambda: HTML(f"<b>[MODE: {state.mode.upper()}]</b>")
    )
    
    click.echo("NAK CLI REPL Shell. Press Ctrl+C or Ctrl+D to exit.")
    click.echo("Press Shift+Tab to switch modes between CODE, PLAN, and CHAT.")
    click.echo("Available slash commands: /new (new session), /clear (clear screen)")
    
    while True:
        try:
            # Dynamically set prompt string based on current mode
            prompt_str = f"nak ({state.mode})> "
            user_input = await session.prompt_async(prompt_str)
            
            if user_input == "auto_execute":
                click.echo("[Auto-execution triggered: switching to Code Mode and executing cached plan]")
                if state.cached_plan:
                    await execute_task_graph(state.cached_plan)
                state.cached_plan = None
                state.auto_execute_cached = False
                continue
                
            if not user_input.strip():
                continue
                
            # Parse slash command
            cmd_name, should_continue = parse_slash_command(user_input)
            if not should_continue:
                if cmd_name == "clear":
                    click.clear()
                elif cmd_name == "new":
                    state.session_id = str(uuid.uuid4())
                    state.cached_plan = None
                    click.echo("Started a new chat session.")
                else:
                    click.echo(f"Unknown slash command: /{cmd_name}")
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
                    
                click.echo("Generating response...")
                chat_req = ChatRequest(
                    system="You are a helpful programming assistant.",
                    prompt=full_prompt,
                    response_format=None,
                    tools=[],
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
                        await execute_task_graph(plan_graph)
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
            
    store.close()
