# NAK CLI Technical Specification v2

## Overview

NAK is a local-first, workspace-scoped AI coding CLI for users working directly on codebases who want speed, determinism, security, and auditable execution rather than open-ended assistant behavior. It operates only inside explicitly allowed repositories or folders, uses NakshastraMCP for fast context retrieval, supports guarded direct file read and write tools when extra detail is required, validates changes before considering tasks complete, and stores structured workspace memory so later commands remain grounded in actual prior work.[cite:48][cite:47][cite:31]

The design target is Windows, Linux, and macOS, using a cross-platform Python stack that is fast to install and easy to evolve. Typer is used for CLI ergonomics, uv for packaging and environment management across all three platforms, and Pydantic Settings for layered configuration and schema validation.[cite:82][cite:90][cite:91]

This version of the specification incorporates the most important architectural conclusion from local benchmarking: on the tested machine, dual-model hot residency was unstable across all tested model pairs. As a result, NAK is designed around a one-model-hot runtime with aggressive parallelization of non-model work and explicit extensibility contracts so future backends, transports, validators, and stores can be added without destabilizing the scheduler.[cite:99][cite:124]

## Goals

### Primary goals

- Execute user-directed coding tasks quickly and predictably.
- Work only inside approved workspace roots.
- Use MCP-first context retrieval for repo understanding.
- Support direct file read, patch, write, move, and delete actions through guarded tools.
- Run validation after edits and store structured memory of changes.
- Keep output concise, actionable, and audit-friendly.

### Secondary goals

- Run effectively on consumer hardware.
- Remain cross-platform across Windows, Linux, and macOS.[cite:90]
- Support future providers, transports, validators, patch engines, and memory backends through stable interfaces.
- Preserve deterministic behavior as the system grows.

### Non-goals

- NAK is not a fully autonomous coding agent.
- NAK is not an unrestricted shell execution environment by default.
- NAK is not a cloud-first collaborative coding platform in v1.
- NAK should not scan or write outside configured workspace roots.[cite:48][cite:64][cite:66]

## Product principles

- Direct over exploratory.
- Workspace-bounded over device-wide access.
- One-model-hot over fragile multi-model concurrency.
- MCP-first context over repeated repo rediscovery.
- Patch-first edits over wholesale rewrites.
- Validation as part of done.
- Memory as structured execution history, not chat transcript.
- Stable contracts over implicit behavior.

## Supported use cases

| Use case | Description |
|---|---|
| Bug fixing | Find issue, inspect files, patch code, validate affected behavior, store result |
| Refactoring | Make bounded code improvements across approved files, validate, log changes |
| Feature work | Implement user-scoped changes inside a chosen workspace |
| Code review | Inspect selected files, identify problems, optionally apply fixes |
| Repo understanding | Summarize architecture, relevant modules, and change points using MCP and direct reads |
| Follow-up tasks | Continue work from prior validated changes preserved in workspace memory |

## Benchmark findings and architecture impact

Three dual-model Ollama tests were executed on a system with 23.4 GB RAM, Intel integrated graphics, and an NVIDIA GeForce RTX 5060 Laptop GPU reporting 4 GB VRAM. All model pairs could answer concurrent requests, but none remained loaded together after warm-up and concurrent execution, showing unstable dual residency and nontrivial memory pressure.[cite:99][cite:124]

| Test pair | Warm success | Concurrent success | Both loaded after warm? | Both loaded after concurrent run? | RAM before | RAM after | Observation |
|---|---|---|---|---|---|---|---|
| deepseek-r1:7b + gemma4:e4b | Yes | Yes | No | No | 8.9 GB | 18.57 GB | High RAM growth, dual residency unstable |
| deepseek-r1:7b + qwen3.5:4b | Yes | Yes | No | No | 12.48 GB | 18.45 GB | Strong latency asymmetry, dual residency unstable |
| qwen3.5:4b + gemma4:e4b | Yes | Yes | No | No | 18.51 GB | 15.36 GB | One model active at a time, dual residency unstable |

These results justify the one-model-hot architecture and the decision to route speed gains through MCP context, file IO concurrency, validation concurrency, and bounded scheduling rather than concurrent multi-model residency.[cite:99][cite:124][cite:31]

## Recommended model strategy

`qwen3.5:4b` should be the default model because it offered the best overall balance of speed, memory footprint, and practical usefulness for coding tasks on the tested system. `deepseek-r1:7b` should act as an escalation model for difficult reasoning, debugging, or review passes when the user accepts slower runtime.[cite:99]

| Model | Role | Why |
|---|---|---|
| qwen3.5:4b | Default fast model | Best default tradeoff for planning, small edits, tool calls, and general coding tasks |
| deepseek-r1:7b | Escalation model | Better for deeper reasoning and harder debugging when latency is acceptable |
| gemma4:e4b | Optional experiment model | Available, but not a better default than qwen3.5:4b on this hardware |

## High-level architecture

NAK is made of isolated modules with explicit contracts between them.

| Module | Responsibility |
|---|---|
| `cli` | Commands, flags, output, prompts, confirmations |
| `config` | Load and validate layered settings |
| `session` | Current run lifecycle and correlation IDs |
| `planner` | Convert prompt and context into task graph JSON |
| `scheduler` | Execute dependency-aware tasks with bounded concurrency |
| `model_adapter` | Normalize provider behavior behind one API |
| `mcp_client` | Access NakshastraMCP and future MCP servers |
| `workspace_fs` | Safe file operations inside approved roots only |
| `validator` | Validation orchestration via plugins |
| `patch_engine` | Patch application and rollback strategies |
| `memory` | Workspace change journal and retrieval |
| `approval` | Approval evaluation policies |
| `audit` | Immutable action trail and integrity checks |

## Execution flow

1. Resolve workspace and permission mode.
2. Load workspace memory and recent validated changes.
3. Fetch compact repo context from NakshastraMCP.
4. Send prompt plus compact context to planner.
5. Planner returns strict task graph JSON.
6. Scheduler executes independent context and read tasks in parallel.[cite:31]
7. Edit tasks apply changes through file and patch interfaces.
8. Validation tasks run on changed scope.
9. Memory persists the resulting change record.
10. CLI returns concise execution output.

## Security and workspace boundaries

The model never receives unrestricted host access. Every requested file path must be canonicalized and proven to stay under an allowed workspace root, which is the correct defense against traversal attacks and aligns with MCP’s explicit consent and bounded-access model.[cite:48][cite:60][cite:64][cite:66]

### Permission modes

| Mode | Read | Write | Delete | Confirmation level |
|---|---|---|---|---|
| `read-only` | Yes | No | No | None |
| `workspace-write` | Yes | Yes | Optional by policy | Medium |
| `confirm-write` | Yes | Yes | Optional by policy | High |
| `trusted-local` | Yes | Yes | Policy driven | Minimal but audited |

### Security rules

- Only approved roots may be accessed.[cite:64][cite:66]
- Symlinks and junctions are blocked by default.[cite:64]
- Destructive actions are policy-gated.[cite:48]
- Shell execution is disabled by default.
- Network operations are disabled by default.
- All writes are audit logged.

## MCP integration

MCP is the primary context and tool layer. The protocol separates prompts, resources, and tools, which allows NAK to use prompts for reusable instruction templates, resources for structured context, and tools for concrete actions.[cite:77][cite:45][cite:47]

### MCP operating model

- NakshastraMCP is used first for repo and file context.
- The planner sees compact summaries, not raw full-repo dumps.
- Direct file reads are used only when MCP context is insufficient.
- Writes happen through host tools, not arbitrary MCP side effects.

### MCP transport strategy

Both `stdio` and HTTP transports are implemented and fully supported for local and remote integration, while gRPC remains future-compatible. Transport differences must not leak into planner, scheduler, or workspace logic.[cite:16][cite:20]

## File tools

| Tool | Purpose |
|---|---|
| `fs.list_dir(path)` | Enumerate directory contents |
| `fs.read_file(path)` | Read a file when needed |
| `fs.read_chunk(path, offset, limit)` | Read specific ranges from large files |
| `fs.search(path, pattern)` | Search for symbols, strings, or imports |
| `fs.write_file(path, content)` | Create or replace a file |
| `fs.apply_patch(path, diff)` | Apply minimal textual or semantic edits |
| `fs.move(src, dst)` | Move or rename files |
| `fs.delete(path)` | Optional destructive action under policy |

Patch-first editing is preferred for accuracy, reviewability, rollback support, and audit integrity.

## Command surface

| Command | Purpose |
|---|---|
| `nak code "..."` | Main entry point for coding tasks |
| `nak plan "..."` | Generate plan without applying changes |
| `nak apply plan.json` | Run a saved task graph |
| `nak validate` | Run validation on current or last changed scope |
| `nak changes` | Show recent workspace changes |
| `nak memory` | Show stored memory records |
| `nak undo` | Revert last tracked change set |
| `nak doctor` | Environment and runtime diagnostics |
| `nak config show` | Display merged config |
| `nak models list` | Display configured model profiles |

### Common flags

- `--workspace <path>`
- `--profile fast|deep|hybrid|review|refactor`
- `--provider ollama`
- `--model <name>`
- `--parallel <n>`
- `--mode read-only|workspace-write|confirm-write|trusted-local`
- `--json`
- `--stream`
- `--dry-run`
- `--no-mcp`

## Configuration schema

Configuration must merge in this order: defaults, global config, user config, workspace config, environment variables, CLI flags. Pydantic Settings is the validation layer.[cite:91]

```yaml
app:
  name: nak
  default_profile: fast

workspace:
  roots:
    - D:\Projects\my-app
  mode: trusted-local
  allow_delete: false
  follow_symlinks: false

models:
  provider: ollama
  default_model: qwen3.5:4b
  escalation_model: deepseek-r1:7b
  ollama:
    base_url: http://127.0.0.1:11434/v1
  timeout_seconds: 120

runtime:
  parallel_non_model_tasks: 8
  parallel_model_tasks: 1
  max_retries: 2
  stream: true
  adaptive_scheduler: true

mcp:
  enabled: true
  servers:
    nakshastra:
      transport: stdio
      command: nakshastramcp
      args: []

validation:
  auto_detect: true
  default:
    - name: lint
      command: auto
    - name: tests
      command: auto

memory:
  enabled: true
  store: .nak/memory.db

security:
  require_confirm_for:
    - delete
    - move
    - overwrite-large-file
```

## Planner contract

The planner must return strict JSON and never freeform prose so the scheduler can remain deterministic.

```json
{
  "goal": "fix auth token refresh bug",
  "workspace": "D:\\Projects\\my-app",
  "mode": "trusted-local",
  "tasks": [
    {
      "id": "t1",
      "kind": "context",
      "action": "fetch_auth_context",
      "depends_on": [],
      "tools": ["mcp:nakshastra"]
    },
    {
      "id": "t2",
      "kind": "read",
      "action": "inspect_auth_files",
      "depends_on": ["t1"],
      "tools": ["fs.read_chunk"],
      "read_paths": ["src/auth", "src/middleware"]
    },
    {
      "id": "t3",
      "kind": "edit",
      "action": "patch_token_refresh",
      "depends_on": ["t2"],
      "tools": ["fs.apply_patch"],
      "write_paths": ["src/auth/token_service.py"]
    },
    {
      "id": "t4",
      "kind": "validate",
      "action": "run_auth_tests",
      "depends_on": ["t3"],
      "tools": ["validate.test"]
    },
    {
      "id": "t5",
      "kind": "remember",
      "action": "store_change_record",
      "depends_on": ["t4"],
      "tools": ["memory.store"]
    }
  ]
}
```

## Scheduler design

The scheduler is the stable core of the system. It must remain isolated from provider-specific quirks and transport-specific behavior.

### Scheduler rules

- Independent context tasks may run concurrently.[cite:31]
- Independent file reads and searches may run concurrently.[cite:31]
- Validation preparation may run concurrently.[cite:31]
- Writes to the same file are serialized.
- Writes to unrelated files may run concurrently only if task dependencies allow.
- Model tasks run through a bounded queue.
- On the tested hardware, default `parallel_model_tasks` is `1`.[cite:99][cite:124]
- The scheduler must degrade concurrency when memory pressure or latency spikes are detected.

### Scheduler interface

```python
class Scheduler:
    async def run(self, tasks: list[Task]) -> list[TaskResult]:
        ...
```

The scheduler must consume only structured task graphs and normalized task results. It must never depend on raw provider outputs.

## One-model-hot runtime

The runtime assumes one active model in memory at a time. This is a hard architectural default, not merely a tuning suggestion.[cite:99][cite:124]

### Runtime behavior

- `qwen3.5:4b` stays hot by default.
- `deepseek-r1:7b` is loaded only when escalation criteria are met.
- The runtime returns to the default profile when escalation work ends, if appropriate.
- Model switching is treated as expensive and visible in logs.

### Model profiles

| Profile | Model strategy | Purpose |
|---|---|---|
| `fast` | qwen3.5:4b only | Planning, small edits, tool calls, fast coding |
| `deep` | deepseek-r1:7b only | Hard debugging, reasoning, deeper review |
| `hybrid` | qwen3.5:4b default + deepseek-r1:7b escalation | Best general profile |
| `review` | Select by review depth | Audit and code review workflow |

## Validation framework

Validation is plug-in based and required for completion unless explicitly disabled.

### Validation levels

| Level | Scope |
|---|---|
| File-level | Formatter, lint, syntax checks |
| Module-level | Type checks and targeted tests |
| Project-level | Full build and full test suite |

### Validation state model

- `planned`
- `running`
- `changed`
- `validated`
- `failed`
- `rolled_back`

## Memory model

The memory subsystem stores structured workspace records rather than chat logs. SQLite is the default store because it is simple, local, durable, and fast enough for the MVP, but the system must be designed so future storage backends can be added without touching scheduler logic.

### Stored fields

- workspace
- request text
- task graph
- files touched
- before and after hashes
- patch summary
- validations run
- validation result
- final status
- open follow-up notes

## Audit and rollback

All writes are auditable. Rollback must work for both patch-based edits and optional Git-aware flows.

### Audit fields

- timestamp
- workspace
- task ID
- file path
- action type
- hash before
- hash after
- approval decision
- patch summary

## Extensibility pressure and contract design

The largest long-term risk is interface drift across providers, transports, validators, patch engines, approval policies, and memory stores. The scheduler must remain stable even as these modules evolve. The solution is explicit stable interfaces, versioned contracts, edge normalization, and startup compatibility checks.

## Stable extensibility interfaces

### ModelProvider

The provider layer must normalize backend-specific behavior from Ollama now and future providers later.

#### Requirements

- Input is `ChatRequest`.
- Output is normalized `ChatResponse`.
- Errors are typed and standardized.
- Structured JSON output is enforced when requested.
- Provider differences are handled at the adapter edge.

#### Contract version

- Interface version: `model-provider/1`
- Scheduler checks provider contract version at startup.
- Incompatible providers fail early.

#### Interface

```python
class ModelProvider(Protocol):
    async def chat(self, request: ChatRequest) -> ChatResponse: ...
    async def health(self) -> bool: ...
    @property
    def name(self) -> str: ...
    @property
    def version(self) -> str: ...
```

### ChatRequest

```python
@dataclass
class ChatRequest:
    system: str
    prompt: str
    response_format: str | None
    tools: list[dict]
    max_tokens: int
    temperature: float
    metadata: dict[str, Any]
```

### ChatResponse

```python
@dataclass
class ChatResponse:
    content: str
    tool_calls: list[dict]
    finish_reason: str
    usage: dict[str, Any]
    raw_provider_response: dict[str, Any]
```

### Standard provider errors

- `invalid_request`
- `timeout`
- `model_unavailable`
- `invalid_output`
- `rate_limited`
- `internal_error`

## McpTransport

Transport differences must remain isolated from planner and scheduler logic.

#### Requirements

- Same tool call contract across `stdio`, HTTP, and future transports.
- Built-in timeout and retry behavior.
- Security and origin checks isolated in transport layer.
- Transport failures return typed tool-call errors.

#### Interface

```python
class McpTransport(Protocol):
    async def connect(self) -> None: ...
    async def call_tool(self, name: str, args: dict) -> ToolCallResult: ...
    async def close(self) -> None: ...
```

### ToolCallResult

```python
@dataclass
class ToolCallResult:
    success: bool
    result: Any | None
    error_code: str | None
    error_message: str | None
    metadata: dict[str, Any]
```

## Validator plugin API

Validation must support common stacks automatically and custom stacks explicitly via plugins.

#### Requirements

- Standardized input and output.
- Structured reporting.
- Stable exit semantics.
- Explicit registration for custom validators.

#### Interface

```python
class Validator(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def supported_languages(self) -> list[str]: ...
    async def run(self, request: ValidationRequest) -> ValidationResult: ...
```

### ValidationRequest

```python
@dataclass
class ValidationRequest:
    workspace: str
    changed_files: list[str]
    level: str
    metadata: dict[str, Any]
```

### ValidationResult

```python
@dataclass
class ValidationResult:
    status: str
    errors: list[str]
    warnings: list[str]
    summary: str
    raw_output: dict[str, Any]
```

Exit code convention:

- `0` pass
- `1` validation fail
- `2` validator execution error

## PatchEngine API

Patch strategy must be swappable without breaking rollback or audit.

#### Requirements

- Support text patching now, semantic patching later.
- Mandatory dry-run capability.
- Mandatory rollback support.
- Mandatory audit metadata.

#### Interface

```python
class PatchEngine(Protocol):
    async def apply(self, request: PatchRequest) -> PatchResult: ...
    async def rollback(self, request: PatchRequest) -> bool: ...
```

### PatchRequest

```python
@dataclass
class PatchRequest:
    path: str
    original_content: str
    proposal: str
    dry_run: bool
    metadata: dict[str, Any]
```

### PatchResult

```python
@dataclass
class PatchResult:
    success: bool
    applied: bool
    new_content: str | None
    error_message: str | None
    patch_metadata: dict[str, Any]
```

## ApprovalPolicy API

Approval logic must be pluggable so stricter environments do not require core rewrites.

#### Requirements

- Stateless decision logic.
- Clear risk classification input.
- Explicit decision output.

#### Interface

```python
class ApprovalPolicy(Protocol):
    def evaluate(self, request: ApprovalRequest) -> ApprovalDecision: ...
```

### ApprovalRequest

```python
@dataclass
class ApprovalRequest:
    action: str
    paths: list[str]
    risk_level: str
    metadata: dict[str, Any]
```

### ApprovalDecision

```python
@dataclass
class ApprovalDecision:
    approved: bool
    reason: str
    policy_name: str
```

## MemoryStore API

The memory layer must support SQLite now and future stores later without exposing raw schema handling to the rest of the application.

#### Requirements

- Schema versioning.
- Startup compatibility checks.
- Reversible migrations.
- Stable CRUD interface.

#### Interface

```python
class MemoryStore(Protocol):
    async def save_change(self, change: ChangeRecord) -> str: ...
    async def get_changes(self, workspace: str) -> list[ChangeRecord]: ...
    async def get_by_id(self, id: str) -> ChangeRecord | None: ...
    @property
    def schema_version(self) -> str: ...
```

### ChangeRecord

```python
@dataclass
class ChangeRecord:
    id: str
    workspace: str
    request: str
    files_touched: list[str]
    patch_summary: str
    validation_status: str
    metadata: dict[str, Any]
```

## Versioning and compatibility rules

To stop extensibility from breaking determinism, every major interface must advertise a contract version and support startup compatibility checks.

### Rules

- Scheduler supports one contract generation at a time.
- Providers and stores declare version strings.
- Incompatible versions fail fast at startup.
- Migrations are explicit, logged, and reversible where possible.
- Raw provider or plugin payloads are never consumed directly by the scheduler.

## Error model

Every pluggable component must map errors into a stable application-level error shape.

```python
@dataclass
class AppError:
    component: str
    code: str
    message: str
    recoverable: bool
    metadata: dict[str, Any]
```

This prevents transport, provider, or plugin-specific failures from leaking chaotic behavior into core execution.

## Recommended stack

| Component | Choice |
|---|---|
| Language | Python 3.11+ |
| CLI | Typer |
| Package manager | uv |
| Config | pydantic-settings |
| HTTP client | httpx |
| Terminal UI | rich |
| Local store | SQLite |
| Async runtime | asyncio TaskGroup |

Python 3.11+ is required to use TaskGroup-based structured concurrency, which is the preferred foundation for grouped async work.[cite:31]

## Cross-platform setup example

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv init nak
cd nak
uv venv
.venv\Scripts\Activate.ps1
uv add typer rich httpx pydantic pydantic-settings
```

uv supports Windows, Linux, and macOS, which makes it appropriate for the portability goal.[cite:90][cite:96]

## MVP scope

Version 1 should include:

- Ollama provider implementing `model-provider/1`
- NakshastraMCP via `stdio`
- Workspace-bounded file tools
- One-model-hot scheduler
- Validation plugin base plus common autodetect validators
- SQLite memory store implementing versioned memory API
- Patch-first engine with rollback
- Approval policy system
- Full audit trail
- Windows, Linux, and macOS support

## Recommended defaults

| Setting | Value |
|---|---|
| Default model | `qwen3.5:4b` |
| Escalation model | `deepseek-r1:7b` |
| Loaded models | 1 |
| Parallel model tasks | 1 |
| Parallel non-model tasks | 8 |
| MCP | Enabled |
| Validation | Enabled |
| Memory store | SQLite |
| Default profile | `hybrid` |
| Safer profile | `confirm-write` |
| Personal machine profile | `trusted-local` |

## Final recommendation

NAK should be built as a secure, workspace-scoped, local-first coding runtime centered on one active model, MCP-backed context, explicit file and patch tools, validation-first completion semantics, and a strongly versioned extensibility layer. This keeps the system fast on consumer hardware while protecting the scheduler from interface drift as new providers, transports, validators, patch engines, approval policies, and memory backends are added over time.[cite:99][cite:124][cite:48][cite:31]
