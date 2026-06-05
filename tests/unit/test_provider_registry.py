import pytest
from nak.model_adapter.registry import ProviderRegistry, ProviderNotFoundError
from nak.protocols.model_provider import ModelProvider

class MockModelProvider(ModelProvider):
    @property
    def name(self) -> str:
        return "mock"
        
    @property
    def version(self) -> str:
        return "model-provider/1"

    async def chat(self, request):
        pass

    async def health(self) -> bool:
        return True

def test_registry_register_and_get():
    registry = ProviderRegistry()
    registry.register("mock", lambda: MockModelProvider())
    
    provider = registry.get("mock")
    assert provider.name == "mock"
    assert provider.version == "model-provider/1"
    
def test_registry_not_found():
    registry = ProviderRegistry()
    with pytest.raises(ProviderNotFoundError):
        registry.get("invalid")

def test_registry_list():
    registry = ProviderRegistry()
    registry.register("mock1", lambda: MockModelProvider())
    registry.register("mock2", lambda: MockModelProvider())
    assert sorted(registry.list()) == ["mock1", "mock2"]
