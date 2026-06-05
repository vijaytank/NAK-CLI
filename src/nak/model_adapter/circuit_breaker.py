import time
from typing import Callable, Any, Optional

class CircuitOpenError(Exception):
    pass

class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 120.0,
        time_func: Callable[[], float] = time.time
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.time_func = time_func
        self.state = "closed"  # closed, open, half-open
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None

    def _check_state(self) -> None:
        if self.state == "open":
            now = self.time_func()
            if self.last_failure_time and (now - self.last_failure_time) > self.recovery_timeout:
                self.state = "half-open"
                
    def record_success(self) -> None:
        self.failure_count = 0
        self.state = "closed"

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = self.time_func()
        if self.failure_count >= self.failure_threshold:
            self.state = "open"

    def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        self._check_state()
        if self.state == "open":
            raise CircuitOpenError("Circuit is open. Fast failing.")
            
        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            raise

    async def call_async(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        self._check_state()
        if self.state == "open":
            raise CircuitOpenError("Circuit is open. Fast failing.")
            
        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            raise
