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
