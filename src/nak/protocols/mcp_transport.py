from typing import Protocol, Any, Dict, Optional
from dataclasses import dataclass

@dataclass
class ToolCallResult:
    success: bool
    result: Optional[Any]
    error_code: Optional[str]
    error_message: Optional[str]
    metadata: Dict[str, Any]

class McpTransport(Protocol):
    async def connect(self) -> None:
        ...

    async def call_tool(self, name: str, args: dict) -> ToolCallResult:
        ...

    async def close(self) -> None:
        ...
