from pathlib import Path
from enum import Enum
import typer
from rich.console import Console

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

def main() -> None:
    app()

if __name__ == "__main__":
    main()
