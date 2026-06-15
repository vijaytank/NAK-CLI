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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component": self.component,
            "code": self.code,
            "message": self.message,
            "recoverable": self.recoverable,
            "metadata": self.metadata,
        }

class SchedulerError(AppError):
    def __init__(self, code: str, message: str, recoverable: bool = False, metadata: Optional[Dict[str, Any]] = None) -> None:
        super().__init__("scheduler", code, message, recoverable, metadata)

class PlannerError(AppError):
    def __init__(self, code: str, message: str, recoverable: bool = False, metadata: Optional[Dict[str, Any]] = None) -> None:
        super().__init__("planner", code, message, recoverable, metadata)

class MemoryError(AppError):
    def __init__(self, code: str, message: str, recoverable: bool = False, metadata: Optional[Dict[str, Any]] = None) -> None:
        super().__init__("memory", code, message, recoverable, metadata)

class AuditError(AppError):
    def __init__(self, code: str, message: str, recoverable: bool = False, metadata: Optional[Dict[str, Any]] = None) -> None:
        super().__init__("audit", code, message, recoverable, metadata)

class ConfigError(AppError):
    def __init__(self, code: str, message: str, recoverable: bool = False, metadata: Optional[Dict[str, Any]] = None) -> None:
        super().__init__("config", code, message, recoverable, metadata)

