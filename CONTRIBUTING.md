# Contributing to NAK-CLI

Thank you for contributing to NAK-CLI! This document provides an architectural overview and guidelines for development, focusing on the interactive REPL shell and local-first memory store.

---

## 🏗️ Architectural Overview

NAK-CLI is a secure, local-first, workspace-scoped AI coding manager. The core codebase is divided into several modules:
- **`cli/`**: Entry points, Click/Typer commands, and the interactive REPL shell (`repl.py`).
- **`planner/`**: Generates structured JSON task execution graphs from user prompts via the Model Provider.
- **`scheduler/`**: Executes task graphs asynchronously using structured concurrency (`asyncio.TaskGroup`) with bounded parallelism.
- **`model_adapter/`**: Pluggable provider adapter (currently backing local Ollama).
- **`memory/`**: SQLite-backed persistent memory store for change histories and conversational REPL histories.
- **`workspace_fs/`**: Guarded filesystem interactions restricting reading and writing to approved workspace roots.

---

## 💬 Interactive REPL Shell

To start the REPL, run:
```bash
nak repl
# or simply run without arguments to fallback:
nak
```

### Modes of Operation
You can cycle between three distinct interactive modes by pressing `Shift+Tab` (`Keys.BackTab`):
1. **`Code Mode`**: Prompts the user, generates a task graph, displays it, and requests confirmation (`Yes` / `No` / `Edit`).
2. **`Plan Mode`**: Generates and displays the JSON task execution graph without executing or requesting confirmation.
3. **`Chat Mode`**: Serves as a direct conversational interface with the AI model, persisting prompt history.

The current mode is displayed at the bottom of the prompt in a styled toolbar: `[MODE: CODE]`, `[MODE: PLAN]`, or `[MODE: CHAT]`.

### 🔄 Shift+Tab Auto-Execution
If you are in **`Plan Mode`** and have successfully generated a plan, pressing `Shift+Tab` to transition to **`Code Mode`** will automatically approve and execute the plan immediately.

### 🗑️ Slash Commands
Inside the REPL prompt, the following slash commands are parsed and processed locally:
- `/new`: Resets the active chat session by generating a new session ID (clears active thread context).
- `/clear`: Clears the screen using Click's standard screen clear command.

### 📋 Multiline Paste Compression
To keep the REPL output clean, if a user pastes a multiline prompt exceeding **5 lines**, the display will compress the output representation to:
`[Pasted: N lines]`

---

## 💾 Workspace Database & Memory Boundaries

All REPL histories, configurations, and change records are stored locally within the workspace directory at:
`<workspace-root>/.nak/memory.db`

This database stores the following tables:
- `changes`: Stores successful execution change records (`ChangeRecord`s).
- `repl_chat_history`: Stores messages, roles, and timestamps mapped by `session_id`.

**Zero Context Leakage**: Memory is strictly workspace-scoped. No records are shared across workspaces.

---

## 🧪 Testing

Every feature requires corresponding tests. Run the test suite:
```bash
uv run pytest
```
Ensure that `ruff check` and `mypy` pass before proposing changes.
