# Architecture Overview

OMF is a capability packaging layer around external agent runtimes. Codex,
Claude Code, Hermes, or another runtime performs the work; OMF imports the run
artifacts, preserves evidence, promotes reusable work into a capability package,
and tracks export/import/target-validation state.

## Layers

The codebase is moving toward these boundaries:

| Layer | Path | Responsibility |
| --- | --- | --- |
| CLI | `src/oh_my_field/cli/` | Typer command registration, option parsing, request construction, output rendering |
| Application | `src/oh_my_field/application/` | Use-case workflows such as capture, import-run, promote, replay, eval, and health |
| Domain | `src/oh_my_field/domain/` | Core models and rules for evidence, capabilities, harnesses, runtime adapters, portability, review, and learning |
| Infrastructure | `src/oh_my_field/infrastructure/` | Filesystem storage, hashing, command execution, and dashboard/server implementation details |
| Adapters | `src/oh_my_field/adapters/` | Runtime-specific import/export behavior behind the runtime adapter contract |
| Schemas | `schemas/` | Committed artifact JSON Schema contracts generated from domain models |

Root-level modules such as `oh_my_field.models`, `oh_my_field.storage`, and
feature modules remain as compatibility surfaces while call sites migrate to the
layered paths.

## Dependency Direction

CLI commands should call application workflows. Application workflows compose
domain rules with infrastructure implementations. Domain code should not import
Typer, raw filesystem storage, subprocess execution, or dashboard/server code.

```text
cli -> application -> domain
                 \-> infrastructure
adapters -> domain runtime contract
infrastructure -> domain models/rules
```

This keeps product rules testable without invoking the CLI and keeps technical
details such as YAML, JSON, atomic writes, and process execution out of command
functions.

## Artifact Pipeline

The core product loop is:

```text
external agent run
  -> import-run evidence
  -> promote capability package
  -> health and review
  -> export runtime bundle
  -> import target overlay
  -> validate target run
```

The canonical capability package stays runtime neutral:

```text
capabilities/<name>/
  capability.yaml
  instructions.md
  harness.yaml
  README.md
```

Runtime-specific assets are projections of that package, not the source of
truth.

## Portability Rules

Portability lifecycle rules live in
`src/oh_my_field/domain/portability/lifecycle.py`. The important distinction is
that exported, imported, validated, and portable are separate states:

- `exported`: a runtime bundle exists.
- `imported`: a target overlay/package exists.
- `validated`: a real target run passed.
- `portable`: at least one imported target is validated.

Static validation and manual-run planning do not mark a target as validated.

## Artifact Contracts

Schema files in `schemas/` make the file contracts explicit:

- `capability.schema.json`
- `evidence.schema.json`
- `harness.schema.json`
- `export_bundle.schema.json`

`tests/test_schema_contracts.py` checks that committed schemas match the
current domain model contracts, so model changes must update the schema files in
the same change.

## Safety Boundary

Command execution and environment filtering are infrastructure concerns, but
the safety policy is part of the product contract. Risky commands are recorded
and require explicit approval before execution, and command records preserve cwd,
risk categories, approval state, shell mode, and environment policy.
