from pathlib import Path
from typing import List

class SecurityError(Exception):
    pass

class WorkspaceFS:
    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = Path(workspace_root).resolve()

    def _guard(self, path_str: str) -> Path:
        # Strip leading slashes/backslashes to avoid resolving to drive root
        cleaned = path_str.lstrip("/\\")
        
        # Prevent workspace folder doubling (e.g. "NAK-CLI/src/main.py" -> "src/main.py")
        workspace_folder_name = self.workspace_root.name
        cleaned_path = Path(cleaned)
        parts = cleaned_path.parts
        if parts and parts[0] == workspace_folder_name:
            cleaned_path = Path(*parts[1:])
            
        # Resolve target path relative to workspace root
        target = (self.workspace_root / cleaned_path).resolve()
        
        # Ensure resolved path is under the workspace root
        try:
            target.relative_to(self.workspace_root)
        except ValueError:
            raise SecurityError(
                f"Access denied: Path '{path_str}' resolves to '{target}' which is outside workspace root '{self.workspace_root}'"
            )
            
        # Block symlinks / junctions along the resolved path
        curr = target
        while curr != self.workspace_root and curr != curr.parent:
            if curr.is_symlink():
                raise SecurityError(f"Access denied: Path '{path_str}' contains a symlink at '{curr}'")
            curr = curr.parent
            
        return target

    def read_file(self, path: str) -> str:
        target = self._guard(path)
        if not target.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        return target.read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> None:
        target = self._guard(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def read_chunk(self, path: str, offset: int, limit: int) -> str:
        target = self._guard(path)
        if not target.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        with open(target, "r", encoding="utf-8") as f:
            f.seek(offset)
            return f.read(limit)

    def list_dir(self, path: str) -> List[str]:
        target = self._guard(path)
        if not target.is_dir():
            raise NotADirectoryError(f"Not a directory: {path}")
        return [item.name for item in target.iterdir()]

    def delete(self, path: str) -> None:
        target = self._guard(path)
        if target.is_file():
            target.unlink()
        elif target.is_dir():
            target.rmdir()

    def move(self, src: str, dst: str) -> None:
        target_src = self._guard(src)
        target_dst = self._guard(dst)
        target_dst.parent.mkdir(parents=True, exist_ok=True)
        target_src.rename(target_dst)
