from typing import Protocol, Any, Dict, Optional
from dataclasses import dataclass

@dataclass
class PatchRequest:
    path: str
    original_content: str
    proposal: str
    dry_run: bool
    metadata: Dict[str, Any]

@dataclass
class PatchResult:
    success: bool
    applied: bool
    new_content: Optional[str]
    error_message: Optional[str]
    patch_metadata: Dict[str, Any]

class PatchEngine(Protocol):
    async def apply(self, request: PatchRequest) -> PatchResult:
        ...

    async def rollback(self, request: PatchRequest) -> bool:
        ...
