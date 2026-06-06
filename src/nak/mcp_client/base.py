import json
import asyncio
from typing import Optional, Dict, Any, List
import httpx
from nak.protocols.mcp_transport import McpTransport, ToolCallResult

class FallbackMcpTransport(McpTransport):
    def __init__(self, stdio_transport: McpTransport, http_transport: McpTransport) -> None:
        self.stdio_transport = stdio_transport
        self.http_transport = http_transport
        self.active_transport: Optional[McpTransport] = None

    async def connect(self) -> None:
        try:
            await self.stdio_transport.connect()
            self.active_transport = self.stdio_transport
        except Exception:
            # Fall back to HTTP transport on failure (e.g. stdio daemon locked)
            await self.http_transport.connect()
            self.active_transport = self.http_transport

    async def call_tool(self, name: str, args: dict) -> ToolCallResult:
        if not self.active_transport:
            raise RuntimeError("McpTransport not connected. Call connect() first.")
        return await self.active_transport.call_tool(name, args)

    async def close(self) -> None:
        if self.active_transport:
            await self.active_transport.close()
            self.active_transport = None
        # Ensure both are closed in case one was partially initialized
        try:
            await self.stdio_transport.close()
        except Exception:
            pass
        try:
            await self.http_transport.close()
        except Exception:
            pass


# MCP Specification (v2024-11-05) Client Lifecycle & Handshake Implementation
# Standard Clause: Section 3.1 (Initialization Handshake Protocol)
class StdioMcpClient(McpTransport):
    def __init__(self, command: str, args: List[str]) -> None:
        self.command = command
        self.args = args
        self.proc: Optional[asyncio.subprocess.Process] = None
        self.request_id = 1
        self.pending_responses: Dict[int, asyncio.Future] = {}
        self.read_task: Optional[asyncio.Task] = None
        self.tools: List[Dict[str, Any]] = []

    async def connect(self) -> None:
        self.proc = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL
        )
        self.read_task = asyncio.create_task(self._read_loop())
        
        # 1. Send 'initialize' request
        await self.request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "nak-cli-client", "version": "0.1.0"}
        })
        
        # 2. Send 'notifications/initialized' notification
        await self.notify("notifications/initialized", {})
        
        # 3. Retrieve exposed tools list
        tools_res = await self.request("tools/list", {})
        self.tools = tools_res.get("tools", [])

    async def _read_loop(self) -> None:
        while self.proc and self.proc.stdout:
            line = await self.proc.stdout.readline()
            if not line:
                break
            try:
                data = json.loads(line.decode("utf-8"))
                if "id" in data:
                    req_id = data["id"]
                    if req_id in self.pending_responses:
                        self.pending_responses[req_id].set_result(data)
            except Exception:
                pass

    async def request(self, method: str, params: dict) -> dict:
        if not self.proc or not self.proc.stdin:
            raise RuntimeError("Subprocess is not running")
        req_id = self.request_id
        self.request_id += 1
        future = asyncio.get_running_loop().create_future()
        self.pending_responses[req_id] = future
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params
        }
        self.proc.stdin.write(json.dumps(payload).encode("utf-8") + b"\n")
        await self.proc.stdin.drain()
        response = await asyncio.wait_for(future, timeout=10.0)
        del self.pending_responses[req_id]
        if "error" in response:
            raise RuntimeError(response["error"].get("message", "Unknown error"))
        return response.get("result", {})

    async def notify(self, method: str, params: dict) -> None:
        if not self.proc or not self.proc.stdin:
            raise RuntimeError("Subprocess is not running")
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }
        self.proc.stdin.write(json.dumps(payload).encode("utf-8") + b"\n")
        await self.proc.stdin.drain()

    async def call_tool(self, name: str, args: dict) -> ToolCallResult:
        try:
            res = await self.request("tools/call", {"name": name, "arguments": args})
            return ToolCallResult(
                success=not res.get("isError", False),
                result=res.get("content", []),
                error_code=None,
                error_message=None,
                metadata={}
            )
        except Exception as e:
            return ToolCallResult(
                success=False,
                result=None,
                error_code="CALL_FAILED",
                error_message=str(e),
                metadata={}
            )

    async def close(self) -> None:
        if self.read_task:
            self.read_task.cancel()
            self.read_task = None
        if self.proc:
            try:
                self.proc.terminate()
                await self.proc.wait()
            except Exception:
                pass
            self.proc = None


# MCP Specification (v2024-11-05) HTTP Transport Client Implementation
class HttpMcpClient(McpTransport):
    def __init__(self, url: str) -> None:
        self.url = url
        self.client = httpx.AsyncClient()
        self.request_id = 1
        self.tools: List[Dict[str, Any]] = []
        self.is_connected = False

    async def connect(self) -> None:
        # Perform initialize handshake over HTTP POST (standard JSON-RPC)
        payload = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "nak-cli-client", "version": "0.1.0"}
            }
        }
        self.request_id += 1
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        response = await self.client.post(self.url, json=payload, headers=headers, timeout=5.0)
        if response.status_code == 200:
            self.is_connected = True
            
            # Fetch tools
            tools_payload = {
                "jsonrpc": "2.0",
                "id": self.request_id,
                "method": "tools/list",
                "params": {}
            }
            self.request_id += 1
            tools_res = await self.client.post(self.url, json=tools_payload, headers=headers, timeout=5.0)
            if tools_res.status_code == 200:
                result = tools_res.json().get("result", {})
                self.tools = result.get("tools", [])
        else:
            raise RuntimeError(f"HTTP init failed: Status {response.status_code}")

    async def call_tool(self, name: str, args: dict) -> ToolCallResult:
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": self.request_id,
                "method": "tools/call",
                "params": {"name": name, "arguments": args}
            }
            self.request_id += 1
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            }
            response = await self.client.post(self.url, json=payload, headers=headers, timeout=10.0)
            if response.status_code == 200:
                res = response.json().get("result", {})
                return ToolCallResult(
                    success=not res.get("isError", False),
                    result=res.get("content", []),
                    error_code=None,
                    error_message=None,
                    metadata={}
                )
            else:
                return ToolCallResult(
                    success=False,
                    result=None,
                    error_code="HTTP_ERROR",
                    error_message=f"HTTP status {response.status_code}",
                    metadata={}
                )
        except Exception as e:
            return ToolCallResult(
                success=False,
                result=None,
                error_code="CALL_FAILED",
                error_message=str(e),
                metadata={}
            )

    async def close(self) -> None:
        await self.client.aclose()
        self.is_connected = False
