import time
from enum import Enum
from typing import Callable, Any, Optional

class CircuitBreakerState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"

class CircuitOpenError(Exception):
    pass

class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 120.0,
        time_func: Callable[[], float] = time.time,
        max_half_open_attempts: int = 1,
        health_check: Optional[Callable[[], Any]] = None
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.time_func = time_func
        self.max_half_open_attempts = max_half_open_attempts
        self.health_check = health_check
        
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.current_recovery_timeout = recovery_timeout
        self.half_open_attempts = 0

    def _check_state(self) -> None:
        if self.state == CircuitBreakerState.OPEN:
            now = self.time_func()
            if self.last_failure_time is not None and (now - self.last_failure_time) > self.current_recovery_timeout:
                self.state = CircuitBreakerState.HALF_OPEN
                self.half_open_attempts = 0

    async def _check_state_async(self) -> None:
        if self.state == CircuitBreakerState.OPEN:
            now = self.time_func()
            if self.last_failure_time is not None and (now - self.last_failure_time) > self.current_recovery_timeout:
                if self.health_check:
                    try:
                        healthy = await self.health_check()
                        if healthy:
                            self.state = CircuitBreakerState.HALF_OPEN
                            self.half_open_attempts = 0
                        else:
                            self.last_failure_time = now
                            self.current_recovery_timeout *= 2
                    except Exception:
                        self.last_failure_time = now
                        self.current_recovery_timeout *= 2
                else:
                    self.state = CircuitBreakerState.HALF_OPEN
                    self.half_open_attempts = 0

    def record_success(self) -> None:
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.half_open_attempts += 1
            if self.half_open_attempts >= self.max_half_open_attempts:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                self.current_recovery_timeout = self.recovery_timeout
        else:
            self.failure_count = 0
            self.state = CircuitBreakerState.CLOSED

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = self.time_func()
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.half_open_attempts += 1
            if self.half_open_attempts >= self.max_half_open_attempts:
                self.state = CircuitBreakerState.OPEN
                self.current_recovery_timeout *= 2
        else:
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitBreakerState.OPEN

    def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        self._check_state()
        if self.state == CircuitBreakerState.OPEN:
            raise CircuitOpenError("Circuit is open. Fast failing.")
            
        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            raise

    async def call_async(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        await self._check_state_async()
        if self.state == CircuitBreakerState.OPEN:
            raise CircuitOpenError("Circuit is open. Fast failing.")
            
        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            raise

