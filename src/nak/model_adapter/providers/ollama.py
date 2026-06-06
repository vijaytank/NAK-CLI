import httpx
from typing import Dict, Any, List
from nak.protocols.model_provider import ModelProvider, ChatRequest, ChatResponse
from nak.core.errors import AppError

class OllamaModelProvider(ModelProvider):
    def __init__(self, base_url: str, model_name: str, timeout_seconds: int = 300) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def version(self) -> str:
        return "model-provider/1"

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # v1/models is standard for OpenAI-compatible endpoint
                response = await client.get(f"{self.base_url}/models")
                return response.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> List[str]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/models")
                if response.status_code == 200:
                    data = response.json()
                    if "data" in data:
                        return [m["id"] for m in data["data"]]
        except Exception:
            pass
        return []

    async def chat(self, request: ChatRequest) -> ChatResponse:
        messages = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": request.temperature,
        }
        if request.max_tokens > 0:
            payload["max_tokens"] = request.max_tokens
            
        if request.response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        if request.tools:
            payload["tools"] = request.tools

        try:
            async with httpx.AsyncClient(timeout=float(self.timeout_seconds)) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code != 200:
                    raise AppError(
                        component="model_adapter",
                        code="invalid_request" if response.status_code == 400 else "internal_error",
                        message=f"Ollama returned error status code: {response.status_code}. Response: {response.text}",
                        recoverable=False
                    )
                    
                data = response.json()
                choice = data["choices"][0]
                message = choice["message"]
                
                return ChatResponse(
                    content=message.get("content") or "",
                    tool_calls=message.get("tool_calls") or [],
                    finish_reason=choice.get("finish_reason") or "stop",
                    usage=data.get("usage") or {},
                    raw_provider_response=data
                )
                
        except httpx.TimeoutException as e:
            raise AppError(
                component="model_adapter",
                code="timeout",
                message=f"Connection to Ollama timed out: {str(e)}",
                recoverable=True
            )
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            raise AppError(
                component="model_adapter",
                code="model_unavailable",
                message=f"Ollama server is unavailable: {str(e)}",
                recoverable=True
            )
        except AppError:
            raise
        except Exception as e:
            raise AppError(
                component="model_adapter",
                code="internal_error",
                message=f"Unexpected error communicating with Ollama: {str(e)}",
                recoverable=False
            )
