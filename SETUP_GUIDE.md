# NAK CLI Setup & Installation Guide

This guide describes how to install, configure, and verify your `nak-cli` and `nakshastramcp` environments.

---

## 💻 System Prerequisites

Before starting, ensure your system meets the following requirements:
*   **Operating System**: Windows 10/11, macOS 12+, or Linux.
*   **Python**: Version 3.11 or higher (Python 3.13 recommended).
*   **uv**: Recommended Python packet and tool manager.

---

## 📥 Step 1: Install NAK CLI

### Option A: Via PowerShell One-Liner (Windows)
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex; uv tool install nak-cli"
```

### Option B: Via standard `uv` (Cross-Platform)
```bash
uv tool install nak-cli
```

### Option C: From Source (Development)
```bash
git clone https://github.com/vijaytank/NAK-CLI.git
cd NAK-CLI
uv sync
uv run pytest
```

---

## 📥 Step 2: Install NakshAstraMCP

`nakshastramcp` is the high-performance local AST codebase indexing and semantic search server. It is packaged as a **Secure Binary Wheel** to preserve full privacy and optimal speed.

### Option A: Install via `uv` (Recommended)
Download and install the secure wheel from the official releases of [NakshAstraMCP-Docs](https://github.com/vijaytank/NakshAstraMCP-Docs):

```powershell
# Install the secure wheel
uv tool install https://github.com/vijaytank/NakshAstraMCP-Docs/releases/download/v3.19.0/nakshastramcp-3.19.0-cp313-cp313-win_amd64.whl --force
```

### Option B: Install via standard Pip
```powershell
python -m pip install .\nakshastramcp-3.19.0-cp313-cp313-win_amd64.whl
```

---

## 🩺 Step 3: Verify the MCP Server

Once installed, verify that `nakshastramcp` is accessible in your path and correctly configured:

```bash
# Check status and verify pathing
nakshastramcp status

# Perform a full environment diagnostic audit
nakshastramcp doctor
```

---

## 🔌 Step 4: Configure MCP Servers in NAK CLI REPL

You can add, list, and verify MCP servers directly from within the `nak repl` shell using the `/mcp` command.

### 1. Launch the REPL
```bash
nak repl
```

### 2. Configure a local Stdio MCP server (e.g. NakshAstraMCP)
In the REPL, type:
```text
nak (chat)> /mcp add nakshastra stdio nakshastramcp start
```
This registers a stdio server named `nakshastra` running `nakshastramcp start`. The configuration is stored persistently in the local SQLite database.

### 3. Configure a remote HTTP MCP server
```text
nak (chat)> /mcp add remote_helper http http://localhost:8000/mcp
```

### 4. Inspect connection status and tools
To see all configured MCP servers, their type, connection status, and list of exposed tools:
```text
nak (chat)> /mcp
```

### 5. Reconnect to a disconnected server
If a server goes offline or fails to connect, you can trigger a reconnection:
```text
nak (chat)> /mcp reconnect nakshastra
```

The connected count is displayed on the right-hand side of your prompt: `MCP: N`.

---

## 🧭 Further Reading
For advanced usage and behavioral guidelines for agents, consult:
*   [COMMANDS.md](COMMANDS.md) - Full NAK CLI Command Reference.
*   [AGENTS.md](AGENTS.md) - System-prompt guidelines for AI coding agents.
*   [NakshAstraMCP Docs](https://github.com/vijaytank/NakshAstraMCP-Docs) - Main documentation portal.
