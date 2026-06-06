# NAK CLI Command Reference

This file documents all the commands and configuration options available in NAK CLI.

---

## 🚀 Interactive REPL Shell (Default)

The NAK REPL shell is the primary interface for running chat sessions, code generation tasks, and project planning.

```bash
# Starts the REPL (default mode is chat)
nak repl [options]
```

### Slash Commands in REPL

| Command | Action / Mode | Description |
| :--- | :--- | :--- |
| `/chat` | Switch to CHAT | Discuss logic, questions, or refactorings without code file edits. |
| `/plan` | Switch to PLAN | Describe a goal and inspect the proposed JSON task graph. |
| `/code` | Switch to CODE | Generate, review, edit, validate, and commit code tasks. |
| `/new` | Reset Session | Starts a new chat session, clears cached plan, and resets mode to CHAT. |
| `/clear` | Clear Screen | Clears the terminal screen and clears the cached plan. |
| `/mcp` | MCP Manager | View configured MCP servers, connection status, and exposed tools. |
| `/mcp add` | Configure Server | Add a stdio or http MCP server. (e.g. `/mcp add nakshastra stdio nakshastramcp start`) |
| `/mcp reconnect` | Reconnect Server | Reconnect to a configured MCP server (e.g. `/mcp reconnect nakshastra`). |
| `/mcp remove` | Remove Server | Remove a configured MCP server (e.g. `/mcp remove nakshastra`). |
| `/help` | Help Menu | Display the list of available commands. |

*   **Keyboard Shortcut**: Press `Shift+Tab` to cycles modes or automatically execute a cached plan in PLAN mode.

---

## 🛠️ Direct CLI Commands

You can run individual code and planning tasks directly from the shell without launching the REPL.

### `nak code`
Run user-directed coding tasks end-to-end, applying file edits and triggering validators automatically.
```bash
nak code "add docstrings to all functions in src/utils/" --workspace ./my-repo --mode confirm-write
```

*   `--workspace` / `-w`: The target workspace folder (defaults to current directory `.`).
*   `--mode` / `-m`: The permission level to run with. Options are:
    *   `confirm-write` (default) - Prompts for approval before writing files.
    *   `workspace-write` - Automatically writes files without prompting.
    *   `read-only` - Only reads files without modifying them.
    *   `trusted-local` - Fully trusted execution environment.

### `nak plan`
Generate and view the parsed task execution graph JSON without modifying any source files (dry run).
```bash
nak plan "fix auth token refresh loop" --workspace ./my-repo --mode confirm-write
```

---

## ⚙️ Configuration Commands

Config settings are persisted locally in `.nak/memory.db`.

### Show Configurations
```bash
nak config show
```

### Set Configuration Parameters
```bash
nak config set <key> <value>
```
*   Example: `nak config set model_timeout 180` (sets provider timeout to 180 seconds).

### Configure Ollama
Set Ollama as the active local AI provider.
```bash
nak config ollama --local "http://localhost:11434/v1"
```

### Configure Llama.cpp
Set Llama.cpp as the active local AI provider.
```bash
nak config llama --local "http://localhost:8080/v1"
```

---

## 🤖 Model Management Commands

### Show Active Model
```bash
nak model
```

### Set Active Model
```bash
nak model set <model_name>
```
*   Example: `nak model set qwen3.5:4b`

### List Available Models
Fetches and lists all active models exposed by your selected local provider.
```bash
nak model list
```
*(Requires the provider to be configured and running).*
