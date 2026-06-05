from typing import Optional
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
