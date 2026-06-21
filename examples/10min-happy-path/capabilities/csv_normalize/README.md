# csv_normalize

## What It Does
Normalize a messy orders CSV into strict, schema-checked JSON

## When To Use
- normalize a messy orders csv into strict json

## Package Contents
- `capability.yaml`: canonical capability metadata.
- `instructions.md`: runtime-neutral agent instruction surface.
- `harness.yaml`: verification and approval checks.
- `contracts/`: task, artifact, validation, and replay contracts.
- `validators/`: executable contract validation helpers.
- `README.md`: human-readable capability card.

## Required Context
- opus_run.log
- output/normalized.json

## Harness
- Status: pass
- agent_log_imported
- artifacts_readable
- artifact_exists:opus_run.log
- artifact_exists:validation.txt
- artifact_exists:output/normalized.json
- json_parses:output/normalized.json
- schema_valid

## Runtime Coverage
- runtime: claude_code
- tool: external_agent_log
- tool: importer:claude_code
- tool: file_system

## Portability
- Source runtime: claude_code
- Source model: not recorded
- Export status: not_exported (0)
- Import status: not_imported (0)
- Target validation: not_run

## Status
- Lifecycle: candidate
- Version: 0.1.0
- Source evidence: 20260621T071814Z-934d7d40

## Last Learning Patches
- No accepted patches recorded.
