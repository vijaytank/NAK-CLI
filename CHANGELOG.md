# Changelog

## [0.2.0] - 2026-06-07
- Implemented `/mcp` slash command in REPL to add, list, reconnect, and remove MCP servers.
- Added support for both `stdio` and `http` transports in `src/nak/mcp_client/base.py` for Model Context Protocol integration.
- Added prompt-toolkit `rprompt` display showing the active connected MCP count: `MCP: N`.
- Implemented automated MCP tool discovery and execution loop in REPL Chat Mode, making Ollama and Llama models capable of running local workspace tools (e.g. search_codebase, deep_context, etc.) and receiving results.
- Added extensive test coverage for `StdioMcpClient`, `HttpMcpClient`, `/mcp reconnect`, and Chat Mode tool calling loop in `tests/unit/test_repl.py`.
- Created detailed `SETUP_GUIDE.md` and `COMMANDS.md` for end-user onboarding.

## [0.1.0] - 2026-06-05
- Initial MVP development starts.
