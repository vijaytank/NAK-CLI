import os
import asyncio
from pathlib import Path
from enum import Enum
from typing import Optional
import typer
from rich.console import Console

from nak.memory.sqlite_store import SQLiteMemoryStore
from nak.model_adapter.providers.ollama import OllamaModelProvider
from nak.core.errors import AppError

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
    
    # Symlink/junction detection
    curr = path
    while curr != curr.parent:
        if curr.is_symlink():
            raise typer.BadParameter(f"Workspace path '{workspace}' contains a symlink at '{curr}'.")
        curr = curr.parent

    # .nak directory checks
    nak_dir = path / ".nak"
    if not nak_dir.exists():
        import sys
        import click
        click.echo(f"Warning: Workspace '.nak' directory is missing in '{workspace}'.")
        try:
            if sys.stdin and sys.stdin.isatty():
                should_create = click.confirm("Would you like to create the '.nak' directory?", default=True)
            else:
                should_create = True
            
            if should_create:
                nak_dir.mkdir(parents=True, exist_ok=True)
                click.echo(f"Created '.nak' directory at '{nak_dir}'.")
            else:
                click.echo("Warning: Proceeding without creating '.nak' directory. Some features may fail.")
        except Exception:
            nak_dir.mkdir(parents=True, exist_ok=True)

    # Check memory.db writability
    db_path = nak_dir / "memory.db"
    try:
        if db_path.exists():
            with open(db_path, "a"):
                pass
        else:
            if nak_dir.exists():
                with open(db_path, "a"):
                    pass
                db_path.unlink()
    except Exception as e:
        raise typer.BadParameter(f"Workspace database '{db_path}' is not writable. Error: {str(e)}")

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
            provider = await store.get_config("active_provider")
            model = await store.get_config("active_model")
            ollama_url = await store.get_config("ollama_url")
            llama_url = await store.get_config("llama_url")
            model_timeout = await store.get_config("model_timeout")
            
            console.print("[bold cyan]NAK-CLI Configuration Summary:[/bold cyan]")
            has_config = False
            if provider is not None:
                console.print(f"  Active Provider:  [green]{provider}[/green]")
                has_config = True
            if model is not None:
                console.print(f"  Active Model:     [green]{model}[/green]")
                has_config = True
            if ollama_url is not None:
                console.print(f"  Ollama Local URL: [green]{ollama_url}[/green]")
                has_config = True
            if llama_url is not None:
                console.print(f"  Llama Local URL:  [green]{llama_url}[/green]")
                has_config = True
            if model_timeout is not None:
                console.print(f"  Model Timeout:    [green]{model_timeout} seconds[/green]")
                has_config = True
                
            if not has_config:
                console.print(r"  No configurations found. Use 'nak config \[ollama|llama]' to configure a provider.")
        finally:
            store.close()
            
    asyncio.run(show_impl())

@config_app.command(name="set")
def config_set(
    key: str = typer.Argument(..., help="Configuration parameter key to set (e.g. model_timeout, active_model)"),
    value: str = typer.Argument(..., help="Configuration parameter value"),
    workspace: str = typer.Option(
        ".",
        "--workspace",
        "-w",
        callback=validate_workspace,
        help="Workspace root path"
    )
) -> None:
    """Set a configuration parameter."""
    async def set_impl():
        db_path = os.path.join(workspace, ".nak", "memory.db")
        store = SQLiteMemoryStore(db_path)
        store.connect()
        try:
            await store.set_config(key, value)
            console.print(f"{key} set to: {value}")
        finally:
            store.close()
            
    asyncio.run(set_impl())


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
            model = await store.get_config("active_model")
            if model is not None:
                console.print(f"Active model: [green]{model}[/green]")
            else:
                console.print("Active model: Not configured")
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
            provider_name = await store.get_config("active_provider")
            if provider_name is None:
                console.print(r"[red]Error: No active provider configured. Please configure one using 'nak config \[ollama|llama]'.[/red]")
                raise typer.Exit(code=1)
                
            ollama_url = await store.get_config("ollama_url")
            llama_url = await store.get_config("llama_url")
            
            if provider_name == "llama":
                if llama_url is None:
                    console.print("[red]Error: Llama Local URL is not configured. Please run 'nak config llama --local <url>' first.[/red]")
                    raise typer.Exit(code=1)
                from nak.model_adapter.providers.llama import LlamaModelProvider
                provider = LlamaModelProvider(llama_url, "default")
            else:
                if ollama_url is None:
                    console.print("[red]Error: Ollama Local URL is not configured. Please run 'nak config ollama --local <url>' first.[/red]")
                    raise typer.Exit(code=1)
                provider = OllamaModelProvider(ollama_url, "default")
                
            # Check provider health
            if not await provider.health():
                console.print(f"[red]Error: Please make sure your {provider_name} is running and connected.[/red]")
                raise typer.Exit(code=1)
                
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
    try:
        app()
    except AppError as e:
        console.print(f"[bold red]Error: {e.message}[/bold red]")
        sys.exit(1)

if __name__ == "__main__":
    main()


