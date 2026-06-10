# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

The human-facing version of this guidance — setup, gates, architecture, and conventions — is [docs/development.md](docs/development.md); contribution workflow is [CONTRIBUTING.md](CONTRIBUTING.md); agent behavioral guidelines are [AGENTS.md](AGENTS.md). Keep this file and `docs/development.md` consistent when either changes.

## Commands

This project uses `uv` (Python `>=3.12`). All commands run through `uv run`.

```bash
uv sync                      # install deps (including dev group)
uv run omf --help            # run the CLI (entry point: oh_my_field.cli:app)

uv run pytest                # full test suite (213 tests)
uv run pytest tests/test_cli.py::test_help_lists_cli_name_when_invoked  # single test
uv run pytest -k orchestrate # subset by keyword

uv run ruff check .          # lint (also: ruff check --fix .)
uv run ruff format .         # format
uv run pyright               # type check (strict)
```

These three checks gate the work and are unusually strict — expect to satisfy all of them:

- **pytest** runs with `filterwarnings = ["error"]`: any warning (e.g. a deprecation) **fails the test**. `--strict-config` and `--strict-markers` are on.
- **pyright** runs in `strict` mode with extra `reportUnknown*`/`reportUnusedVariable` promoted to errors. `langgraph` is not fully typed, so this repo ships **hand-written stubs in `typings/langgraph/`**. If you use a LangGraph API surface not covered by those stubs, extend the stub rather than suppressing the error.
- **ruff** selects `ALL` rules (see `pyproject.toml` for the ignore list). `tests/**` and `cli/commands/*.py` have relaxed per-file ignores.

## What OMF is (and is not)

OMF is **not an agent runtime**. An external agent (Codex, Claude Code, Hermes, …) does the work. OMF imports that finished run, preserves the evidence, and promotes repeatable work into a **capability package** that can be reviewed, verified, hardened, and exported to other runtimes.

The first product loop is three CLI commands: `import-run` → `promote` → `health`. `omf run` chains the full pipeline as a single resumable workflow.

## Architecture

### Layered layout + compatibility shims (read this first)

The codebase is **mid-migration from a flat module layout to a layered one**, and both coexist. New code is organized into layers:

- `domain/` — immutable models and pure domain logic (`domain/models.py` holds the bulk; per-concept views live under `domain/<concept>/` — capability, evidence, harness, learning, portability, review, runtime, session, skill).
- `application/` — use-case workflows, one package per stage (`application/<stage>/workflow.py`).
- `infrastructure/` — I/O and side effects: `infrastructure/fs/` (storage, hashing), `infrastructure/process/` (command execution), `infrastructure/portability/`, `infrastructure/session/`, `infrastructure/dashboard/`, `infrastructure/install/`.
- `adapters/` — runtime boundary: `adapters/agent_import.py` (import external runs), `adapters/runtime_export/` (export per target), `adapters/skill_install/` (install activation assets).
- `cli/` — the Typer surface (see [CLI surface](#cli-surface-cli)).

The **flat top-level modules still exist** (`models.py`, `storage.py`, `promote.py`, …). Migrated ones are now **re-export shims** (e.g. `models.py` → `domain.models`, `storage.py` → `infrastructure.fs.storage`, `promote.py` → `application.promote`). **Internal code still imports through these shim paths on purpose** — `from oh_my_field.models import ...` and `from oh_my_field.storage import ...` are everywhere and are *not* legacy to be "fixed."

So when locating a stage's real implementation: open the flat module; if it's a shim, follow its re-export (or look for `application/<stage>/workflow.py`). Stages **not yet migrated** are still implemented as real top-level modules — currently `orchestrate.py`, `export.py`, `context.py`, `learn.py`, `reflect.py`, `review.py`, `learning_patch.py`, `rollback.py`, `verify.py`, `eval_set.py`, `eval_support.py`, `registry.py`, `inspection.py`, `diagnostics.py`.

### Data model is the foundation (`domain/models.py`)

Every model inherits `StrictModel` = `BaseModel(extra="forbid", frozen=True)`. So all domain objects are **immutable and reject unknown fields**; "mutation" is always `model.model_copy(update={...})`. Literal type aliases (e.g. `CommandRiskCategory`, `AgentImporterName`, `CapabilityStatus`) define the closed vocabularies used across the system. Capability/eval names must match `CAPABILITY_NAME_PATTERN` (`^[a-z][a-z0-9_]*$`). `domain/base.py` re-surfaces `StrictModel` plus the cross-cutting schema-version / id / hash constants.

### Per-stage workflows are LangGraph graphs (`application/<stage>/workflow.py`)

Each migrated pipeline stage (`capture`, `promote`, `replay`, `eval`, `health`) is an `application/<stage>/` package; the not-yet-migrated stages above keep the same shape as a flat module. The shape is:

- an `XxxRequest(StrictModel)` input,
- a `run_xxx_workflow(request, dependencies=None)` entry point,
- a private `_build_xxx_graph()` that wires a `StateGraph` over a `TypedDict` state, `add_node`/`add_edge` from `START` to `END`, then `.compile()`,
- the compiled graph is `.invoke()`d with an initial state dict.

For time and ID generation, each workflow defines its **own** frozen dependencies dataclass (e.g. `CaptureDependencies` holding a `clock` and `token_factory`) and falls back to `_default_dependencies()` when none is passed — this is how determinism is injected in tests. Not every stage needs it: `run_promote_workflow(request)` takes no dependencies. Follow this pattern when adding a stage. (`import-run` is the exception to the `run_*_workflow` shape: `application/import_run/` dispatches through the `adapters` runtime registry via `import_agent_run`.)

### `orchestrate.py` is the top-level resumable chain

`run` drives the fixed node sequence `import_evidence → promote_capability → pack_context → run_verification → evaluate_capability → record_learning_patch` (older node names are remapped via `NODE_ALIASES`). Each node's result is checkpointed into a `WorkflowRunRecord` on disk, so `resume`, `rollback`, and `status` can pick up a partially-completed run. This is a layer *above* the per-stage LangGraph workflows, not the same graph.

### Storage — YAML files, not a database (`infrastructure/fs/storage.py`)

All persistence is plain YAML. Default layout (paths are CLI options, but these are the defaults):

- `capabilities/<name>/` — the capability package: `capability.yaml` (canonical metadata + provenance), `instructions.md`, `harness.yaml`, `README.md` (the human "capability card"). `manifest.yaml` is a recognized legacy filename. **This package is the source of truth.**
- `.omf/{evidence,replays,evals,eval_sets,reviews,learning,learning_patches,context,reflections,exports,workflows}/` — all other artifacts.

Writes are atomic (temp file + rename) and **refuse to overwrite** an existing file (`DuplicateWriteError`). Use the existing `write_*`/`load_*`/`list_*` helpers rather than touching files directly.

### Integrity chain (`infrastructure/fs/hashing.py`)

Artifacts carry an `integrity_chain` of sha256 links. `model_sha256` hashes the canonical JSON of a model **excluding `integrity_chain` itself**; `append_integrity_link` chains a new link onto a copy. The `verify` command walks this chain to detect tampering (e.g. an altered source-evidence record).

### Safety / permission model (`infrastructure/process/execution.py`)

Commands are classified into risk categories: `write`, `destructive`, `external_call`, `credential_access`, `production_write`, `paid_operation`, `privilege_escalation`. Risky commands are **recorded as intent but not executed** unless the user passes `--approve-command-risk`. Capability **exports are gated** behind `--approve-export`. Preserve this record-don't-execute default when extending command handling.

Two more defaults round out the boundary:

- **Minimal command environment.** Executed commands get only the `DEFAULT_ENV_ALLOWLIST` (`PATH`, `HOME`, `TMPDIR`); secret-bearing vars (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `AWS_*`, `GITHUB_TOKEN`, …) are stripped and the blocked names are recorded. Opt a variable back in with `--allow-env NAME`.
- **Artifact-import safety (`adapters/agent_import.py`).** `import-run --artifact-root` skips `.git/`, `.venv/`, `node_modules/`, `.env*`, private-key patterns, and symlinks; honors `.omfignore`/`--exclude`; caps traversal via `--max-artifact-count`/`--max-total-artifact-bytes`; stores binary/oversized files metadata-only; and **redacts secrets by default** (key/value secrets, bearer/GitHub/Slack tokens, AWS keys, JWTs, private-key blocks — opt out with `--no-redact-secrets`).

### Runtime portability (`adapters/`, `domain/portability/`, `export.py`)

- **Import** external runs via `adapters/agent_import.py` importers, keyed by `AgentImporterName` = `codex | claude_code | hermes`.
- **Export** a capability package to a runtime target via `omf capability export` (per-target renderers under `adapters/runtime_export/`: `codex`, `claude_code`, `hermes`, `generic` skill bundle).
- The `capability` subcommands cover the rest of the lifecycle: `import` (materialize a bundle in a target project + write a validation report), `validate` (re-check an imported target, optionally folding a real `--run-command` exit code into the eval), `remap` (record a context remap plan), `adapt` (apply instruction/context/review overrides).

**Portability is three independent status axes, never one flag** — keep them distinct when touching this code. `ExportStatus` (`not_exported|exported`), `ImportStatus` (`not_imported|imported`), and `TargetValidationStatus` (`not_run|needs_validation|needs_adaptation|validated`) are separate fields, and `omf health` reports each per imported target. "Can be exported" ≠ "imported" ≠ "actually validated on the target."

### Agent activation assets (`resources/`, `adapters/skill_install/`, `mcp/`)

OMF ships activation assets so an agent runtime can use OMF itself: the meta-skill and per-runtime fragments live under `src/oh_my_field/resources/skills/omf/` (and a generic MCP config under `resources/mcp/`); both are declared as wheel `artifacts` in `pyproject.toml`. `omf install skill --runtime <target>` and `omf install mcp --client <client>` materialize them via `adapters/skill_install/`. `omf mcp serve` runs a stdio MCP server (`mcp/server.py`) exposing OMF tools.

## CLI surface (`cli/`)

Thin Typer layer, now a package rather than a single file. `cli/app.py` builds the `app` and the `capability` / `install` / `session` / `mcp` sub-Typers, then calls each command module's `register(app)`. Each command lives in `cli/commands/<name>.py`, builds a `*Request` model, calls the matching `run_*_workflow`, and prints the result via `emit_json` (`cli/output.py`, one JSON line). Errors are mapped to `typer.Exit(code=1)` by the `cli_errors(...)` context manager (`cli/errors.py`), which always handles `StorageError`/`ValidationError` plus any stage `*Error` you pass in. Shared option definitions live in `cli/options.py`.

Commands group into: ingest (`import-run`, `capture`, `init`), build (`promote`, `run`, `resume`, `rollback`, `status`), verify (`replay`, `eval`, `regression-case`, `verify`), review (`approve`, `reject`, `revise`, `review`, `learn-patch`), learning (`learn`, `reflect`, `dataset-export`), operate (`health`, `harden`, `card`, `registry`, `dashboard`, `inspect`, `context`, `diff`), explain (`explain`/`why`), portability (`export`, `capability export|import|validate|remap|adapt`), activation (`install skill|mcp`, `session start|event|finish`, `mcp serve`), and diagnose (`version`, `doctor` — these print a `diagnostics.py` summary rather than a workflow result).

## Conventions

- Match the existing module shape (Request model + `run_*_workflow` + `_build_*_graph`) when adding pipeline functionality, and place new stages under the layer that fits (`domain` / `application` / `infrastructure` / `adapters`). Don't "fix" the flat shim imports — they are intentional.
- Keep new I/O behind the storage helpers (`infrastructure/fs/storage.py`) and new time/ID needs behind an injected per-workflow dependencies dataclass so tests stay deterministic.
- Tests live in `tests/test_<area>_cli.py` and exercise the CLI via `typer.testing.CliRunner` or call `run_*_workflow` directly with stub dependencies. See `AGENTS.md` for the project's behavioral guidelines (simplicity-first, surgical changes, goal-driven verification).
