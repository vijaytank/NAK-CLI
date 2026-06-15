import pytest
from nak.model_adapter.circuit_breaker import CircuitBreaker, CircuitOpenError

def test_circuit_breaker_closed_initially():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
    assert cb.state == "closed"
    
    # Calls succeed normally
    res = cb.call(lambda: "success")
    assert res == "success"

def test_circuit_breaker_opens_on_failures():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
    
    # Simulate 3 failures
    for _ in range(3):
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("failed")))
            
    # Now it should be open
    assert cb.state == "open"
    
    # Call should fail fast with CircuitOpenError
    with pytest.raises(CircuitOpenError):
        cb.call(lambda: "won't run")

def test_circuit_breaker_recovers_after_timeout():
    current_time = 100.0
    def mock_time():
        return current_time
        
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=10, time_func=mock_time)
    
    # Trip the circuit
    for _ in range(2):
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("failed")))
            
    assert cb.state == "open"
    
    # Move time forward by 11 seconds (greater than recovery_timeout of 10)
    current_time += 11
    
    # Next call should be in "half-open" state. If it succeeds, it should close the circuit
    res = cb.call(lambda: "recovered")
    assert res == "recovered"
    assert cb.state == "closed"


def test_circuit_breaker_max_half_open_attempts():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=10, max_half_open_attempts=2)

    # Trip circuit
    for _ in range(2):
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("failed")))
    assert cb.state == "open"

    # Advance time to allow recovery
    cb.last_failure_time = 0.0
    cb.time_func = lambda: 15.0

    # First attempt in half-open succeeds
    res = cb.call(lambda: "ok1")
    assert res == "ok1"
    # Should still be half-open because max_half_open_attempts is 2
    assert cb.state == "half-open"

    # Second attempt succeeds -> closes circuit
    res = cb.call(lambda: "ok2")
    assert res == "ok2"
    assert cb.state == "closed"


def test_circuit_breaker_exponential_backoff():
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=10, max_half_open_attempts=1)

    # Trip circuit
    with pytest.raises(ValueError):
        cb.call(lambda: (_ for _ in ()).throw(ValueError("failed")))
    assert cb.state == "open"
    assert cb.current_recovery_timeout == 10.0

    # Advance time to allow recovery
    cb.last_failure_time = 0.0
    cb.time_func = lambda: 15.0

    # Attempt in half-open fails
    with pytest.raises(ValueError):
        cb.call(lambda: (_ for _ in ()).throw(ValueError("failed")))

    # Should transition back to open and recovery timeout is doubled
    assert cb.state == "open"
    assert cb.current_recovery_timeout == 20.0


@pytest.mark.asyncio
async def test_circuit_breaker_async_health_probe():
    health_calls = []

    async def mock_health():
        health_calls.append(True)
        return True

    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=10, max_half_open_attempts=1)
    cb.health_check = mock_health

    async def failing_func():
        raise ValueError("failed")

    async def succeeding_func():
        return "ok"

    # Trip circuit
    with pytest.raises(ValueError):
        await cb.call_async(failing_func)
    assert cb.state == "open"

    # Advance time
    cb.last_failure_time = 0.0
    cb.time_func = lambda: 15.0

    # Call async should trigger health check and transition to half-open, then succeed and close
    res = await cb.call_async(succeeding_func)
    assert res == "ok"
    assert cb.state == "closed"
    assert len(health_calls) == 1

