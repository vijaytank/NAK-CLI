import os
import pytest
from unittest.mock import patch
from nak.validator.autodetect import resolve_executable

def test_resolve_executable_via_shutil_which():
    # If shutil.which finds it, it should return that path directly
    with patch("shutil.which", return_value="/usr/local/bin/ruff") as mock_which:
        path = resolve_executable("ruff")
        assert path == "/usr/local/bin/ruff"
        mock_which.assert_called_once_with("ruff")

def test_resolve_executable_via_virtual_env_windows():
    # If shutil.which fails, it should check VIRTUAL_ENV environment variable
    # For Windows
    environ = {
        "VIRTUAL_ENV": "C:\\my_project\\.venv"
    }
    
    with patch("shutil.which", return_value=None), \
         patch.dict(os.environ, environ), \
         patch("os.path.exists", return_value=True), \
         patch("os.name", "nt"):
        path = resolve_executable("ruff")
        # On Windows it should look in C:\my_project\.venv\Scripts\ruff.exe
        assert path.replace("\\", "/") == "C:/my_project/.venv/Scripts/ruff.exe"

def test_resolve_executable_via_virtual_env_unix():
    # For Unix systems
    environ = {
        "VIRTUAL_ENV": "/home/user/project/.venv"
    }
    
    with patch("shutil.which", return_value=None), \
         patch.dict(os.environ, environ), \
         patch("os.path.exists", return_value=True), \
         patch("os.name", "posix"):
        path = resolve_executable("ruff")
        # On Unix it should look in /home/user/project/.venv/bin/ruff
        assert path.replace("\\", "/") == "/home/user/project/.venv/bin/ruff"

def test_resolve_executable_not_found():
    with patch("shutil.which", return_value=None), \
         patch.dict(os.environ, {}, clear=True):
        with pytest.raises(FileNotFoundError):
            resolve_executable("nonexistent_binary_abc_123")
