import os
import tempfile
from pathlib import Path
import pytest
from nak.workspace_fs.fs import WorkspaceFS, SecurityError

@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create some files inside the workspace
        workspace_path = Path(tmpdir).resolve()
        test_file = workspace_path / "test.txt"
        test_file.write_text("hello world")
        
        sub_dir = workspace_path / "subdir"
        sub_dir.mkdir()
        sub_file = sub_dir / "sub.txt"
        sub_file.write_text("sub content")
        
        yield workspace_path

def test_workspace_fs_allowed_reads(temp_workspace):
    fs = WorkspaceFS(str(temp_workspace))
    
    # Read relative path
    assert fs.read_file("test.txt") == "hello world"
    assert fs.read_file("subdir/sub.txt") == "sub content"
    
    # Read absolute path resolved to workspace
    abs_path = str(temp_workspace / "test.txt")
    assert fs.read_file(abs_path) == "hello world"

def test_workspace_fs_blocked_traversal(temp_workspace):
    fs = WorkspaceFS(str(temp_workspace))
    
    # Traversal relative path
    with pytest.raises(SecurityError):
        fs.read_file("../test.txt")
        
    # Traversal relative path further out
    with pytest.raises(SecurityError):
        fs.read_file("../../some_file.txt")

def test_workspace_fs_blocked_absolute_outside(temp_workspace):
    fs = WorkspaceFS(str(temp_workspace))
    
    # Absolute path outside workspace
    outside_file = tempfile.NamedTuple if False else "/etc/passwd" if os.name != "nt" else "C:\\Windows\\win.ini"
    with pytest.raises(SecurityError):
        fs.read_file(outside_file)

def test_workspace_fs_write_and_delete(temp_workspace):
    fs = WorkspaceFS(str(temp_workspace))
    
    # Write new file
    fs.write_file("new.txt", "new file content")
    assert (temp_workspace / "new.txt").read_text() == "new file content"
    
    # Delete file
    fs.delete("new.txt")
    assert not (temp_workspace / "new.txt").exists()

def test_workspace_fs_list_dir(temp_workspace):
    fs = WorkspaceFS(str(temp_workspace))
    files = fs.list_dir(".")
    assert "test.txt" in files
    assert "subdir" in files
