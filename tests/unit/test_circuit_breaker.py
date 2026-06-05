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
