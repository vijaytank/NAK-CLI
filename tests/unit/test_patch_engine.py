import tempfile
from pathlib import Path
import pytest
from nak.patch_engine.engine import UnifiedDiffPatchEngine
from nak.protocols.patch_engine import PatchRequest

@pytest.fixture
def temp_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "code.py"
        original_content = (
            "def hello():\n"
            "    print('Hello World')\n"
            "\n"
            "def goodbye():\n"
            "    print('Goodbye World')\n"
        )
        file_path.write_text(original_content, encoding="utf-8")
        yield file_path, original_content

@pytest.mark.asyncio
async def test_patch_engine_apply_success(temp_file):
    file_path, original_content = temp_file
    engine = UnifiedDiffPatchEngine()
    
    # Unified diff proposal
    proposal = (
        "--- a/code.py\n"
        "+++ b/code.py\n"
        "@@ -1,3 +1,3 @@\n"
        " def hello():\n"
        "-    print('Hello World')\n"
        "+    print('Hello NAK')\n"
        " \n"
    )
    
    req = PatchRequest(
        path=str(file_path),
        original_content=original_content,
        proposal=proposal,
        dry_run=False,
        metadata={}
    )
    
    result = await engine.apply(req)
    assert result.success is True
    assert result.applied is True
    
    expected_content = (
        "def hello():\n"
        "    print('Hello NAK')\n"
        "\n"
        "def goodbye():\n"
        "    print('Goodbye World')\n"
    )
    assert result.new_content == expected_content
    assert file_path.read_text(encoding="utf-8") == expected_content

@pytest.mark.asyncio
async def test_patch_engine_dry_run(temp_file):
    file_path, original_content = temp_file
    engine = UnifiedDiffPatchEngine()
    
    proposal = (
        "--- a/code.py\n"
        "+++ b/code.py\n"
        "@@ -1,3 +1,3 @@\n"
        " def hello():\n"
        "-    print('Hello World')\n"
        "+    print('Hello NAK')\n"
        " \n"
    )
    
    req = PatchRequest(
        path=str(file_path),
        original_content=original_content,
        proposal=proposal,
        dry_run=True,
        metadata={}
    )
    
    result = await engine.apply(req)
    assert result.success is True
    assert result.applied is False
    assert result.new_content == (
        "def hello():\n"
        "    print('Hello NAK')\n"
        "\n"
        "def goodbye():\n"
        "    print('Goodbye World')\n"
    )
    # File should remain unmodified
    assert file_path.read_text(encoding="utf-8") == original_content

@pytest.mark.asyncio
async def test_patch_engine_apply_failure(temp_file):
    file_path, original_content = temp_file
    engine = UnifiedDiffPatchEngine()
    
    # Diff doesn't match original content (wrong context)
    proposal = (
        "--- a/code.py\n"
        "+++ b/code.py\n"
        "@@ -1,3 +1,3 @@\n"
        " def hello():\n"
        "-    print('Wrong Context Line')\n"
        "+    print('Hello NAK')\n"
        " \n"
    )
    
    req = PatchRequest(
        path=str(file_path),
        original_content=original_content,
        proposal=proposal,
        dry_run=False,
        metadata={}
    )
    
    result = await engine.apply(req)
    assert result.success is False
    assert result.applied is False
    assert result.error_message is not None

@pytest.mark.asyncio
async def test_patch_engine_rollback(temp_file):
    file_path, original_content = temp_file
    engine = UnifiedDiffPatchEngine()
    
    # First apply the patch
    proposal = (
        "--- a/code.py\n"
        "+++ b/code.py\n"
        "@@ -1,3 +1,3 @@\n"
        " def hello():\n"
        "-    print('Hello World')\n"
        "+    print('Hello NAK')\n"
        " \n"
    )
    req = PatchRequest(
        path=str(file_path),
        original_content=original_content,
        proposal=proposal,
        dry_run=False,
        metadata={}
    )
    await engine.apply(req)
    
    # Rollback should restore the original content
    rollback_success = await engine.rollback(req)
    assert rollback_success is True
    assert file_path.read_text(encoding="utf-8") == original_content
