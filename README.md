# NAK CLI

NAK is a local-first, workspace-scoped, language-agnostic AI coding CLI. It operates exclusively inside explicitly allowed repositories, uses NakshastraMCP for fast context retrieval, runs validation after edits, and stores structured memory of workspace changes.

## 🌟 Key Features with Confirm-Write Support

### Workspace-Scoped Isolation
Rejects path traversal and escapes. Blocks symlinks/junctions by default to ensure safe execution within explicitly allowed repositories.

### One-Model-Hot Queueing
Sequentially executes model tasks while parallelizing directory reads and background lint checks for resource-constrained hardware environments.

### Transactional Persistency
Leverages an `ExecuteTransaction` context manager wrapping SQLite change records and size-bounded audit log files to prevent partial or orphaned commits. This ensures all changes are properly recorded before the next session starts.

### Fuzzy Patch Engine
Applies unified diff patches fuzzy-matching original context lines, tolerating minor model indentation/newline offsets for easier code generation workflows.

### Dynamic Multi-Provider Registry
Modular provider interface allowing quick local Ollama integration or remote models without hardcoding configurations.

### Resilient MCP Client
Connects via stdio transport and automatically falls back to HTTP mode when encountering daemon locks, ensuring reliable context retrieval across different environments.

## 📦 Installation

### 1. NAK CLI Installation (Windows PowerShell)
```powershell
# Install using uv package manager
irm https://astral.sh/uv/install.ps1 | iex; \
vu tool install nak-cli --force
```

### 2. Codebase Context Engine (NakshAstraMCP)
To enable AST-aware local repository indexing and fast semantic search, use:
```powershell
cd E:\Projects\NAK-CLI
uv sync
uv run pytest tests/
```
For full details on client configuration and platform support, refer to the [NakshAstraMCP-Docs](https://github.com/vijaytank/NakshAstraMCP-Docs) repository.

### 3. From Source (Development)
To clone from source:
```bash
git clone https://github.com/vijaytank/NAK-CLI.git
cd NAK-CLI
uv sync
```
Then run tests to verify the safety layers, transactions, and adapters.

## 📖 Complete Documentation Guides
*   For a detailed onboarding guide, refer to [Setup Guide](SETUP_GUIDE.md).
*   For a full command and slash command reference, refer to [Commands Reference](COMMANDS.md).

---

## 🔐 Permission Mode Workflow (Confirm-Write)
The NAK CLI supports explicit permission modes for controlled code changes. The `confirm-write` mode is designed for:
1. **Review Phase**: Review proposed edits before applying them.
2. **Validation Check**: Run validators and linters on the new content.
3. **Commit Decision**: Confirm or reject based on validation results.

### Example Usage: Plan a Task (Dry Run)
Inspect a parsed task graph JSON without applying any file edits:
```bash
# Review mode - shows proposed changes but doesn't apply them yet
nak plan "fix auth token refresh loop" --workspace ./my-repo --mode confirm-write
```
This will display the planned modifications and allow you to review before committing.

### Example Usage: Execute Code Task (Apply Changes)
To actually make code changes:
```bash
# Apply all proposed edits with validation
nak code "add docstrings to all functions in src/utils/" --workspace ./my-repo
```
The CLI will execute the full workflow including context retrieval, model planning, file patching, validator plugins, and SQLite journaling.

## 🧪 Testing
The codebase relies on a **test-first** architecture with a complete pytest suite. To verify safety layers:
```bash
cd E:\Projects\NAK-CLI
uv run pytest tests/
```
To run quality checks (lint, type checking):
```bash
# Run linter and mypy checkers
uv run ruff check src/ tests/
uv run mypy src/
```

## 📄 License
NAK CLI is licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for more details.
