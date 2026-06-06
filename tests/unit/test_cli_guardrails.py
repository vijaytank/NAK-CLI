import pytest
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

def test_cli_default_to_repl():
    from unittest.mock import patch, AsyncMock
    # Mock run_repl so it returns immediately
    with patch("nak.cli.repl.run_repl", new_callable=AsyncMock) as mock_run:
        # Run CLI without arguments (fallback should trigger)
        import sys
        original_argv = sys.argv.copy()
        try:
            sys.argv = ["nak"]
            from nak.cli.main import main
            # We catch SystemExit because Typer commands exit
            with pytest.raises(SystemExit):
                main()
            mock_run.assert_called_once()
        finally:
            sys.argv = original_argv

def test_repl_command_execution():
    from unittest.mock import patch, AsyncMock
    import os
    with patch("nak.cli.repl.run_repl", new_callable=AsyncMock) as mock_run:
        result = runner.invoke(app, ["repl", "--workspace", "."])
        assert result.exit_code == 0
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        assert os.path.abspath(args[0]) == os.path.abspath(".")
        assert args[1] == "confirm-write"



