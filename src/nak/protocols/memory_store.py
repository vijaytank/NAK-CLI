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

    async def save_chat_message(self, session_id: str, role: str, content: str) -> None:
        ...

    async def get_chat_history(self, session_id: str) -> List[Dict[str, Any]]:
        ...

    async def clear_chat_history(self, session_id: str) -> None:
        ...

    async def get_last_session_id(self) -> Optional[str]:
        ...

    async def get_config(self, key: str) -> Optional[str]:
        ...

    async def set_config(self, key: str, value: str) -> None:
        ...

    @property
    def schema_version(self) -> str:
        ...
