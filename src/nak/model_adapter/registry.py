from typing import Dict, Callable, List
from nak.protocols.model_provider import ModelProvider

class ProviderNotFoundError(Exception):
    pass

class ProviderRegistry:
    def __init__(self) -> None:
        self._registry: Dict[str, Callable[[], ModelProvider]] = {}

    def register(self, name: str, factory: Callable[[], ModelProvider]) -> None:
        self._registry[name] = factory

    def get(self, name: str) -> ModelProvider:
        if name not in self._registry:
            raise ProviderNotFoundError(f"Provider '{name}' not found in registry.")
        return self._registry[name]()

    def list(self) -> List[str]:
        return list(self._registry.keys())
