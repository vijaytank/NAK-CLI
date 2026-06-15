# NAK CLI

NAK is a local-first, workspace-scoped, language-agnostic AI coding CLI. It operates exclusively inside explicitly allowed repositories, uses NakshastraMCP for fast context retrieval, runs validation after edits, and stores structured memory of workspace changes.

---

## 🌟 Key Features

- **Workspace-Scoped Isolation**: Rejects path traversal and escapes. Blocks symlinks/junctions by default.
- **One-Model-Hot Queueing**: Sequentially executes model tasks to support resource-constrained hardware while parallelizing directory reads and background lint checks.
- **Transactional Persistency**: Leverages an `ExecuteTransaction` context manager wrapping SQLite change records and size-bounded audit log files to prevent partial/orphaned commits.
- **Fuzzy Patch Engine**: Applies unified diff patches fuzzy-matching original context lines to easily tolerate minor model indentation/newline offsets.
- **Dynamic Multi-Provider Registry**: Modular provider interface allowing quick local Ollama integration or remote models.
- **Resilient MCP Client**: Connects via stdio transport and automatically falls back to HTTP mode when encountering daemon locks.
- **Language Agnostic Validators**: Dynamically locates linters/compilers (e.g. `ruff`, `eslint`, `mvn`) without hardcoded path configurations.

---

## 📦 Installation

### 1. NAK CLI Installation
```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex; uv tool install nak-cli"

# Cross-Platform (uv / pip)
uv tool install nak-cli
# or
pip install nak-cli
```

### 2. Codebase Context Engine (NakshAstraMCP)
To enable AST-aware local repository indexing and fast semantic search, install `nakshastramcp` using `uv`:
```powershell
uv tool install https://github.com/vijaytank/NakshAstraMCP-Docs/releases/download/v3.19.0/nakshastramcp-3.19.0-cp313-cp313-win_amd64.whl --force
```
For full details on client configuration and platform support, refer to the [NakshAstraMCP-Docs](https://github.com/vijaytank/NakshAstraMCP-Docs) repository.

### 3. From Source (Development)
```bash
git clone https://github.com/vijaytank/NAK-CLI.git
cd NAK-CLI
uv sync
uv run pytest
```

---

## 📖 Complete Documentation Guides
*   For a detailed onboarding guide, refer to the [Setup Guide](SETUP_GUIDE.md).
*   For a full command and slash command reference, refer to the [Commands Reference](COMMANDS.md).

---

## 🔌 Interactive Usage Examples

### 📋 Check CLI Help (Interactive)
```bash
# Show all available commands with descriptions
nak --help
```

### 💡 Plan a Task (Dry Run - No Edits Applied)
Inspect a parsed task graph JSON without applying any file edits:
```bash
# Dry run to see what would happen if you ran this command
nak plan "fix auth token refresh loop" --workspace ./my-repo --mode confirm-write
```

### 🛠️ Execute Code Task (Interactive)
Run context retrieval, model planning, file patching, validator plugins, and SQLite journaling end-to-end:
```bash
# Interactive code execution with full logging
nak code "add docstrings to all functions in src/utils/" --workspace ./my-repo
```

### 🧪 Run Tests (Interactive)
To verify the safety layers, transactions, and adapters interactively:
```bash
uv run pytest tests/
test output will be displayed with interactive markers
code coverage report: uv run mypy src/
quality checks complete!
```

---

## 📄 License
NAK CLI is licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for more details.
