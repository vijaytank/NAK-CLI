from typing import Protocol, Any, Dict, List, Optional
from dataclasses import dataclass

@dataclass
class ChangeRecord:
    id: str
    workspace: str
    request: str
    files_touched: List[str]
    patch_summary: str
    validation_status: str
    metadata: Dict[str, Any]

class MemoryStore(Protocol):
    async def save_change(self, change: ChangeRecord) -> str:
        ...

    async def get_changes(self, workspace: str) -> List[ChangeRecord]:
        ...

    async def get_by_id(self, id: str) -> Optional[ChangeRecord]:
        ...

    @property
    def schema_version(self) -> str:
        ...
