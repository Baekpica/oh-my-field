# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

This project uses `uv` (Python `>=3.12`). All commands run through `uv run`.

```bash
uv sync                      # install deps (including dev group)
uv run omf --help            # run the CLI (entry point: oh_my_field.cli:app)

uv run pytest                # full test suite (129 tests)
uv run pytest tests/test_cli.py::test_help_lists_cli_name_when_invoked  # single test
uv run pytest -k orchestrate # subset by keyword

uv run ruff check .          # lint (also: ruff check --fix .)
uv run ruff format .         # format
uv run pyright               # type check (strict)
```

These three checks gate the work and are unusually strict — expect to satisfy all of them:

- **pytest** runs with `filterwarnings = ["error"]`: any warning (e.g. a deprecation) **fails the test**. `--strict-config` and `--strict-markers` are on.
- **pyright** runs in `strict` mode with extra `reportUnknown*`/`reportUnusedVariable` promoted to errors. `langgraph` is not fully typed, so this repo ships **hand-written stubs in `typings/langgraph/`**. If you use a LangGraph API surface not covered by those stubs, extend the stub rather than suppressing the error.
- **ruff** selects `ALL` rules (see `pyproject.toml` for the ignore list). Tests and `cli.py` have relaxed per-file ignores.

## What OMF is (and is not)

OMF is **not an agent runtime**. An external agent (Codex, Claude Code, Hermes, …) does the work. OMF imports that finished run, preserves the evidence, and promotes repeatable work into a **capability package** that can be reviewed, verified, hardened, and exported to other runtimes.

The first product loop is three CLI commands: `import-run` → `promote` → `health`. `omf run` chains the full pipeline as a single resumable workflow.

## Architecture

### Data model is the foundation (`models.py`)

Every model inherits `StrictModel` = `BaseModel(extra="forbid", frozen=True)`. So all domain objects are **immutable and reject unknown fields**; "mutation" is always `model.model_copy(update={...})`. Literal type aliases (e.g. `CommandRiskCategory`, `AgentImporterName`, `CapabilityStatus`) define the closed vocabularies used across the system. Capability/eval names must match `CAPABILITY_NAME_PATTERN` (`^[a-z][a-z0-9_]*$`).

### Per-stage modules are LangGraph workflows

Each pipeline stage lives in its own module: `capture`, `context`, `promote`, `replay`, `eval`, `learn`, `reflect`, `export`. They all follow the **same shape**:

- an `XxxRequest(StrictModel)` input,
- a `run_xxx_workflow(request, dependencies=None)` entry point,
- a private `_build_xxx_graph()` that wires a `StateGraph` over a `TypedDict` state, `add_node`/`add_edge` from `START` to `END`, then `.compile()`,
- the compiled graph is `.invoke()`d with an initial state dict.

`dependencies` (a frozen dataclass holding a `clock` and `token_factory`) is how time and ID generation are injected for deterministic tests — follow this pattern when adding a stage.

### `orchestrate.py` is the top-level resumable chain

`run` drives the fixed node sequence `import_evidence → promote_capability → pack_context → run_verification → evaluate_capability → record_learning_patch` (older node names are remapped via `NODE_ALIASES`). Each node's result is checkpointed into a `WorkflowRunRecord` on disk, so `resume`, `rollback`, and `status` can pick up a partially-completed run. This is a layer *above* the per-stage LangGraph workflows, not the same graph.

### `storage.py` — YAML files, not a database

All persistence is plain YAML. Default layout (paths are CLI options, but these are the defaults):

- `capabilities/<name>/` — the capability package: `capability.yaml` (canonical metadata + provenance), `instructions.md`, `harness.yaml`, `README.md` (the human "capability card"). `manifest.yaml` is a recognized legacy filename. **This package is the source of truth.**
- `.omf/{evidence,replays,evals,eval_sets,reviews,learning,learning_patches,context,reflections,exports,workflows}/` — all other artifacts.

Writes are atomic (temp file + rename) and **refuse to overwrite** an existing file (`DuplicateWriteError`). Use the existing `write_*`/`load_*`/`list_*` helpers rather than touching files directly.

### Integrity chain (`integrity.py`)

Artifacts carry an `integrity_chain` of sha256 links. `model_sha256` hashes the canonical JSON of a model **excluding `integrity_chain` itself**; `append_integrity_link` chains a new link onto a copy. The `verify` command walks this chain to detect tampering (e.g. an altered source-evidence record).

### Safety / permission model (`execution.py`)

Commands are classified into risk categories: `write`, `destructive`, `external_call`, `credential_access`, `production_write`, `paid_operation`. Risky commands are **recorded as intent but not executed** unless the user passes `--approve-command-risk`. Capability **exports are gated** behind `--approve-export`. Preserve this record-don't-execute default when extending command handling.

Two more defaults round out the boundary:

- **Minimal command environment.** Executed commands get only the `DEFAULT_ENV_ALLOWLIST` (`PATH`, `HOME`, `TMPDIR`); secret-bearing vars (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `AWS_*`, `GITHUB_TOKEN`, …) are stripped and the blocked names are recorded. Opt a variable back in with `--allow-env NAME`.
- **Artifact-import safety (`adapters.py`).** `import-run --artifact-root` skips `.git/`, `.venv/`, `node_modules/`, `.env*`, private-key patterns, and symlinks; honors `.omfignore`/`--exclude`; caps traversal via `--max-artifact-count`/`--max-total-artifact-bytes`; and stores binary/oversized files metadata-only.

### Runtime portability (`adapters.py`, `portability.py`, `export.py`)

- **Import** external runs via `adapters.py` importers, keyed by `AgentImporterName` = `codex | claude_code | hermes`.
- **Export** a capability package to a runtime target via `omf capability export` (targets: `codex`, `claude_code`, `hermes`, `generic` skill bundle).
- The `capability` subcommands cover the rest of the lifecycle: `import` (materialize a bundle in a target project + write a validation report), `validate` (re-check an imported target, optionally folding a real `--run-command` exit code into the eval), `remap` (record a context remap plan), `adapt` (apply instruction/context/review overrides).

**Portability is three independent status axes, never one flag** — keep them distinct when touching this code. `ExportStatus` (`not_exported|exported`), `ImportStatus` (`not_imported|imported`), and `TargetValidationStatus` (`not_run|needs_validation|needs_adaptation|validated`) are separate fields, and `omf health` reports each per imported target. "Can be exported" ≠ "imported" ≠ "actually validated on the target."

## CLI surface (`cli.py`)

Thin Typer layer: each command builds a `*Request` model and calls the matching `run_*_workflow`, then prints `summary.model_dump_json()`. Errors are caught as the stage's `*Error` / `StorageError` / `ValidationError` and re-raised as `typer.Exit(code=1)`. Commands group into: ingest (`import-run`, `capture`), build (`promote`, `run`, `resume`, `rollback`, `status`), verify (`replay`, `eval`, `regression-case`, `verify`), review (`approve`, `reject`, `revise`, `review`, `learn-patch`), learning (`learn`, `reflect`), operate (`health`, `harden`, `card`, `registry`, `dashboard`, `inspect`, `context`), diagnose (`version`, `doctor` — these print a `diagnostics.py` summary rather than a workflow result), and portability (`export`, `capability export|import|validate|remap|adapt`).

## Conventions

- Match the existing module shape (Request model + `run_*_workflow` + `_build_*_graph`) when adding pipeline functionality.
- Keep new I/O behind `storage.py` helpers and new time/ID needs behind injected `dependencies` so tests stay deterministic.
- Tests live in `tests/test_<area>_cli.py` and exercise the CLI via `typer.testing.CliRunner` or call `run_*_workflow` directly with stub dependencies. See `AGENTS.md` for the project's behavioral guidelines (simplicity-first, surgical changes, goal-driven verification).
