from typing import Protocol, Any, Dict, List
from dataclasses import dataclass

@dataclass
class ValidationRequest:
    workspace: str
    changed_files: List[str]
    level: str
    metadata: Dict[str, Any]

@dataclass
class ValidationResult:
    status: str
    errors: List[str]
    warnings: List[str]
    summary: str
    raw_output: Dict[str, Any]

class Validator(Protocol):
    @property
    def name(self) -> str:
        ...

    @property
    def supported_languages(self) -> List[str]:
        ...

    async def run(self, request: ValidationRequest) -> ValidationResult:
        ...
