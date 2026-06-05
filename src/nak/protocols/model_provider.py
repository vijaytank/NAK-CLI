from typing import Protocol, Any, Dict, List, Optional
from dataclasses import dataclass

@dataclass
class ChatRequest:
    system: str
    prompt: str
    response_format: Optional[str]
    tools: List[Dict[str, Any]]
    max_tokens: int
    temperature: float
    metadata: Dict[str, Any]

@dataclass
class ChatResponse:
    content: str
    tool_calls: List[Dict[str, Any]]
    finish_reason: str
    usage: Dict[str, Any]
    raw_provider_response: Dict[str, Any]

class ModelProvider(Protocol):
    async def chat(self, request: ChatRequest) -> ChatResponse:
        ...

    async def health(self) -> bool:
        ...

    @property
    def name(self) -> str:
        ...

    @property
    def version(self) -> str:
        ...
