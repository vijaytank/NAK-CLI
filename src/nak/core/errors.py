from typing import Any, Dict, Optional

class AppError(Exception):
    def __init__(
        self,
        component: str,
        code: str,
        message: str,
        recoverable: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        self.component = component
        self.code = code
        self.message = message
        self.recoverable = recoverable
        self.metadata = metadata or {}
        super().__init__(f"[{component}] {code}: {message}")
