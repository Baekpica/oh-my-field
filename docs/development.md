# Development Guide

This is the canonical guide for working on the OMF codebase. Behavioral
guidelines for agents live in [AGENTS.md](../AGENTS.md); the contribution
workflow lives in [CONTRIBUTING.md](../CONTRIBUTING.md).

## Setup

This project uses `uv` (Python `>=3.12`).

```bash
uv sync --all-extras --dev
uv run omf --help
```

## The Gates

Three checks gate every change, and they are intentionally strict. Run the same
ones CI runs:

```bash
uv run ruff format --check .   # formatting
uv run ruff check .            # lint  (auto-fix: ruff check --fix .)
uv run pyright                 # type check (strict)
uv run pytest                  # tests
uv build                       # packaging smoke
```

What "strict" means here:

- **pytest** runs with `filterwarnings = ["error"]`, so any warning (e.g. a
  deprecation) **fails the test**. `--strict-config` and `--strict-markers` are
  on.
- **pyright** runs in `strict` mode with `reportUnknown*` and
  `reportUnusedVariable` promoted to errors. `langgraph` is not fully typed, so
  the repo ships hand-written stubs in `typings/langgraph/`. If you touch a
  LangGraph API surface the stubs do not cover, extend the stub rather than
  suppressing the error.
- **ruff** selects `ALL` rules (see `pyproject.toml` for the ignore list).
  `tests/**` and `src/oh_my_field/cli/commands/*.py` have relaxed per-file
  ignores.

Useful test invocations:

```bash
uv run pytest tests/test_cli.py::test_help_lists_cli_name_when_invoked  # single test
uv run pytest -k orchestrate                                            # by keyword
```

## Architecture And Layering

OMF is organized into layers. See
[architecture/overview.md](architecture/overview.md) for the dependency
direction and per-concept layout.

| Layer | Path | Responsibility |
| --- | --- | --- |
| CLI | `src/oh_my_field/cli/` | Typer command surface, option parsing, output rendering |
| Application | `src/oh_my_field/application/` | use-case workflows |
| Domain | `src/oh_my_field/domain/` | models, rules, lifecycle |
| Infrastructure | `src/oh_my_field/infrastructure/` | storage, hashing, command execution |
| Adapters | `src/oh_my_field/adapters/` | runtime-specific import/export/install behavior |
| Schemas | `schemas/` | committed artifact JSON Schema contracts |

**Compatibility shims.** The flat top-level modules (`oh_my_field.models`,
`oh_my_field.storage`, `oh_my_field.promote`, …) still exist. Migrated ones are
now re-export shims pointing at their layered home, and internal code still
imports through these shim paths **on purpose** — do not "fix" a shim import. To
find a stage's real implementation, follow the shim's re-export or look for
`application/<stage>/workflow.py`. Stages not yet migrated remain real top-level
modules.

```text
cli -> application -> domain
                 \-> infrastructure
adapters -> domain runtime contract
infrastructure -> domain models/rules
```

Domain code must not import Typer, raw filesystem storage, subprocess execution,
or dashboard/server code.

## Conventions

- **Module shape.** A pipeline stage is an `XxxRequest(StrictModel)` input, a
  `run_xxx_workflow(request, dependencies=None)` entry point, and a private
  `_build_xxx_graph()` that wires a LangGraph `StateGraph` over a `TypedDict`
  state from `START` to `END`, then `.compile()`. The compiled graph is
  `.invoke()`d with an initial state dict. Match this shape and place new code in
  the layer that fits.
- **Immutability.** Every model inherits `StrictModel`
  (`BaseModel(extra="forbid", frozen=True)`): domain objects are immutable and
  reject unknown fields. "Mutation" is `model.model_copy(update={...})`.
- **Determinism.** Keep new I/O behind the storage helpers
  (`infrastructure/fs/storage.py`) and inject time/IDs through a per-workflow
  dependencies dataclass (a frozen dataclass holding a `clock` and
  `token_factory`) so tests stay deterministic. Not every stage needs one.
- **Atomic writes.** Storage writes are atomic (temp file + rename) and refuse to
  overwrite an existing file (`DuplicateWriteError`). Use the `write_*`/`load_*`/
  `list_*` helpers rather than touching files directly.
- **Integrity.** Artifacts carry an `integrity_chain` of sha256 links
  (`infrastructure/fs/hashing.py`). `model_sha256` hashes a model's canonical
  JSON excluding `integrity_chain` itself; the `verify` command walks the chain
  to detect tampering.

## Schema Contracts

Schema files in `schemas/` make the artifact file contracts explicit
(`capability.schema.json`, `evidence.schema.json`, `harness.schema.json`,
`export_bundle.schema.json`). `tests/test_schema_contracts.py` checks that
committed schemas match the current domain model contracts, so **a domain model
change must update the schema files in the same change**.

## Safety Model Is A Contract

Command execution and environment filtering are infrastructure concerns
(`infrastructure/process/execution.py`), but the safety policy is part of the
product contract — preserve the defaults when extending command handling:

- Risky commands (`write`, `destructive`, `external_call`, `credential_access`,
  `production_write`, `paid_operation`, `privilege_escalation`) are recorded as
  intent and **not executed** without `--approve-command-risk`. Exports are
  gated by `--approve-export`.
- Commands run with a minimal environment (`PATH`, `HOME`, `TMPDIR`);
  secret-bearing variables are stripped and recorded.
- `import-run --artifact-root` skips dangerous paths, honors
  `.omfignore`/`--exclude`, and caps traversal.

See [security.md](security.md) for the full boundary.

## Tests

Tests live in `tests/test_<area>_cli.py` and exercise the CLI via
`typer.testing.CliRunner` or call `run_*_workflow` directly with stub
dependencies. Add tests for behavior changes before calling the work done.
