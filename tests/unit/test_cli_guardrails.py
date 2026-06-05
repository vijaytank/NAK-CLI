from typer.testing import CliRunner
from nak.cli.main import app

runner = CliRunner()

def test_cli_requires_valid_mode():
    # If an invalid mode is provided, it should fail before execution
    result = runner.invoke(app, ["code", "fix bug", "--mode", "invalid-mode"])
    assert result.exit_code != 0
    assert "invalid" in result.output.lower() or "choose from" in result.output.lower()

def test_cli_requires_existing_workspace():
    # If a non-existent workspace is provided, it should fail immediately
    result = runner.invoke(app, ["code", "fix bug", "--workspace", "C:\\nonexistent_dir_123_xyz"])
    assert result.exit_code != 0
    assert "does not exist" in result.output.lower() or "invalid" in result.output.lower()
