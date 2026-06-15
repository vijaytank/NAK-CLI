from nak.core.errors import AppError

def test_app_error_structure():
    err = AppError(
        component="model_adapter",
        code="model_unavailable",
        message="Ollama offline",
        recoverable=True,
        metadata={"attempts": 3}
    )
    assert err.component == "model_adapter"
    assert err.code == "model_unavailable"
    assert err.message == "Ollama offline"
    assert err.recoverable is True
    assert err.metadata == {"attempts": 3}


def test_app_error_to_dict():
    err = AppError(
        component="test_comp",
        code="test_code",
        message="test_msg",
        recoverable=False,
        metadata={"foo": "bar"}
    )
    d = err.to_dict()
    assert d == {
        "component": "test_comp",
        "code": "test_code",
        "message": "test_msg",
        "recoverable": False,
        "metadata": {"foo": "bar"}
    }


def test_app_error_subclasses():
    from nak.core.errors import (
        SchedulerError,
        PlannerError,
        MemoryError,
        AuditError,
        ConfigError
    )

    se = SchedulerError("sched_fail", "scheduler failed", recoverable=True)
    assert se.component == "scheduler"
    assert se.code == "sched_fail"
    assert se.message == "scheduler failed"
    assert se.recoverable is True

    pe = PlannerError("plan_fail", "planner failed")
    assert pe.component == "planner"
    assert pe.code == "plan_fail"

    me = MemoryError("mem_fail", "memory failed")
    assert me.component == "memory"
    assert me.code == "mem_fail"

    ae = AuditError("audit_fail", "audit failed")
    assert ae.component == "audit"
    assert ae.code == "audit_fail"

    ce = ConfigError("config_fail", "config failed")
    assert ce.component == "config"
    assert ce.code == "config_fail"

