import os
import asyncio
from pathlib import Path
from enum import Enum
from typing import Optional
import typer
from rich.console import Console

from nak.memory.sqlite_store import SQLiteMemoryStore
from nak.model_adapter.providers.ollama import OllamaModelProvider

app = typer.Typer(help="NAK CLI - Local-first AI coding workflow manager")
console = Console()

class PermissionMode(str, Enum):
    read_only = "read-only"
    workspace_write = "workspace-write"
    confirm_write = "confirm-write"
    trusted_local = "trusted-local"

def validate_workspace(workspace: str) -> str:
    path = Path(workspace).resolve()
    if not path.exists():
        raise typer.BadParameter(f"Workspace path '{workspace}' does not exist.")
    if not path.is_dir():
        raise typer.BadParameter(f"Workspace path '{workspace}' is not a directory.")
    return str(path)

@app.command()
def code(
    prompt: str = typer.Argument(..., help="Prompt describing the coding task"),
    workspace: str = typer.Option(
        ".",
        "--workspace",
        "-w",
        callback=validate_workspace,
        help="Workspace root path"
    ),
    mode: PermissionMode = typer.Option(
        PermissionMode.confirm_write,
        "--mode",
        "-m",
        help="Execution permission mode"
    )
) -> None:
    """
    Run user-directed coding tasks end-to-end.
    """
    console.print(f"[green]Executing task:[/green] {prompt}")
    console.print(f"[blue]Workspace:[/blue] {workspace}")
    console.print(f"[blue]Permission Mode:[/blue] {mode.value}")

@app.command()
def plan(
    prompt: str = typer.Argument(..., help="Prompt describing the coding task"),
    workspace: str = typer.Option(
        ".",
        "--workspace",
        "-w",
        callback=validate_workspace,
        help="Workspace root path"
    ),
    mode: PermissionMode = typer.Option(
        PermissionMode.confirm_write,
        "--mode",
        "-m",
        help="Execution permission mode"
    )
) -> None:
    """
    Generate execution plan without applying changes.
    """
    console.print(f"[green]Planning task:[/green] {prompt}")

@app.command()
def repl(
    workspace: str = typer.Option(
        ".",
        "--workspace",
        "-w",
        callback=validate_workspace,
        help="Workspace root path"
    ),
    mode: PermissionMode = typer.Option(
        PermissionMode.confirm_write,
        "--mode",
        "-m",
        help="Execution permission mode"
    )
) -> None:
    """
    Start the interactive REPL shell.
    """
    from nak.cli.repl import run_repl
    asyncio.run(run_repl(workspace, mode.value))

# Configuration Command Group
config_app = typer.Typer(help="Manage AI provider configurations")
app.add_typer(config_app, name="config")

@config_app.command(name="show")
def config_show(
    workspace: str = typer.Option(
        ".",
        "--workspace",
        "-w",
        callback=validate_workspace,
        help="Workspace root path"
    )
) -> None:
    """Show the current AI provider configurations."""
    async def show_impl():
        db_path = os.path.join(workspace, ".nak", "memory.db")
        store = SQLiteMemoryStore(db_path)
        store.connect()
        try:
            provider = await store.get_config("active_provider") or "ollama"
            model = await store.get_config("active_model") or "qwen3.5:4b"
            ollama_url = await store.get_config("ollama_url") or "http://localhost:11434/v1"
            llama_url = await store.get_config("llama_url") or "http://localhost:8080/v1"
            
            console.print("[bold cyan]NAK-CLI Configuration Summary:[/bold cyan]")
            console.print(f"  Active Provider:  [green]{provider}[/green]")
            console.print(f"  Active Model:     [green]{model}[/green]")
            console.print(f"  Ollama Local URL: [green]{ollama_url}[/green]")
            console.print(f"  Llama Local URL:  [green]{llama_url}[/green]")
        finally:
            store.close()
            
    asyncio.run(show_impl())

@config_app.command(name="ollama")
def config_ollama(
    local: Optional[str] = typer.Option(None, "--local", help="Ollama local service URL"),
    workspace: str = typer.Option(
        ".",
        "--workspace",
        "-w",
        callback=validate_workspace,
        help="Workspace root path"
    )
) -> None:
    """Configure Ollama as the active AI provider."""
    async def config_impl():
        db_path = os.path.join(workspace, ".nak", "memory.db")
        store = SQLiteMemoryStore(db_path)
        store.connect()
        try:
            await store.set_config("active_provider", "ollama")
            if local is not None:
                await store.set_config("ollama_url", local)
                console.print(f"Ollama URL set to: {local}")
            console.print("Active provider set to: ollama")
        finally:
            store.close()
            
    asyncio.run(config_impl())

@config_app.command(name="llama")
def config_llama(
    local: Optional[str] = typer.Option(None, "--local", help="Llama local service URL"),
    workspace: str = typer.Option(
        ".",
        "--workspace",
        "-w",
        callback=validate_workspace,
        help="Workspace root path"
    )
) -> None:
    """Configure Llama as the active AI provider."""
    async def config_impl():
        db_path = os.path.join(workspace, ".nak", "memory.db")
        store = SQLiteMemoryStore(db_path)
        store.connect()
        try:
            await store.set_config("active_provider", "llama")
            if local is not None:
                await store.set_config("llama_url", local)
                console.print(f"Llama URL set to: {local}")
            console.print("Active provider set to: llama")
        finally:
            store.close()
            
    asyncio.run(config_impl())


# Model Command Group
model_app = typer.Typer(help="Manage active AI models", invoke_without_command=True)
app.add_typer(model_app, name="model")

@model_app.callback()
def model_main(
    ctx: typer.Context,
    workspace: str = typer.Option(
        ".",
        "--workspace",
        "-w",
        callback=validate_workspace,
        help="Workspace root path"
    )
) -> None:
    """Manage the active AI model. Running without a subcommand displays the active model."""
    if ctx.invoked_subcommand is not None:
        return
        
    async def get_active_model_impl():
        db_path = os.path.join(workspace, ".nak", "memory.db")
        store = SQLiteMemoryStore(db_path)
        store.connect()
        try:
            model = await store.get_config("active_model") or "qwen3.5:4b"
            console.print(f"Active model: [green]{model}[/green]")
        finally:
            store.close()
            
    asyncio.run(get_active_model_impl())

@model_app.command(name="set")
def model_set(
    model_name: str = typer.Argument(..., help="Model name to set as active"),
    workspace: str = typer.Option(
        ".",
        "--workspace",
        "-w",
        callback=validate_workspace,
        help="Workspace root path"
    )
) -> None:
    """Set the active AI model."""
    async def set_model_impl():
        db_path = os.path.join(workspace, ".nak", "memory.db")
        store = SQLiteMemoryStore(db_path)
        store.connect()
        try:
            await store.set_config("active_model", model_name)
            console.print(f"Active model set to: {model_name}")
        finally:
            store.close()
            
    asyncio.run(set_model_impl())

@model_app.command(name="list")
def model_list(
    workspace: str = typer.Option(
        ".",
        "--workspace",
        "-w",
        callback=validate_workspace,
        help="Workspace root path"
    )
) -> None:
    """List available models from the active provider."""
    async def list_models_impl():
        db_path = os.path.join(workspace, ".nak", "memory.db")
        store = SQLiteMemoryStore(db_path)
        store.connect()
        try:
            provider_name = await store.get_config("active_provider") or "ollama"
            ollama_url = await store.get_config("ollama_url") or "http://localhost:11434/v1"
            llama_url = await store.get_config("llama_url") or "http://localhost:8080/v1"
            
            if provider_name == "llama":
                from nak.model_adapter.providers.llama import LlamaModelProvider
                provider = LlamaModelProvider(llama_url, "default")
            else:
                provider = OllamaModelProvider(ollama_url, "default")
                
            console.print(f"Fetching models from active provider [cyan]'{provider_name}'[/cyan]...")
            models = await provider.list_models()
            console.print("[bold cyan]Available Models:[/bold cyan]")
            for m in models:
                console.print(f"  - {m}")
        finally:
            store.close()
            
    asyncio.run(list_models_impl())


def main() -> None:
    import sys
    if len(sys.argv) == 1:
        sys.argv.append("repl")
    app()

if __name__ == "__main__":
    main()


