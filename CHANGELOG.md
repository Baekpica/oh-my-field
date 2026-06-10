# Changelog

All notable changes to this project will be documented here.

## Unreleased

- Nothing yet.

## 0.2.1 - 2026-06-10

### Fixed

- Constrained artifact snapshotting to project-root paths before reading
  metadata or text previews, including absolute, relative, and symlink escapes.
- Stopped pathless validation summaries from becoming expected artifacts while
  preserving their commands and summaries as validation evidence.

## 0.2.0 - 2026-06-10

### Added

- Added hardened canonical evidence records with run observations, artifact
  snapshots, artifact contracts, task contracts, validation results, and record
  quality metadata.
- Added contract bundle files (`task_contract.yaml`, `artifacts.yaml`,
  `validation.md`, `replay_plan.yaml`) and a generated contract validator to
  promoted capability packages and runtime exports.
- Added structured MCP recording tools: `omf_record_input`,
  `omf_record_artifact`, `omf_record_validation`, and `omf_record_decision`.
- Added runtime skill guidance that tells agents to inspect `omf --help` and
  relevant subcommand help before using remembered CLI syntax.
- Added public release CI gates for lint, format, type checking, tests, build,
  and distribution smoke tests.
- Added public onboarding, security, contribution, and release documentation.

### Changed

- `omf promote` and `omf_promote_capability` now use the strict quality gate by
  default; pass `--no-strict` or `strict=false` only for intentional legacy
  evidence promotion.
- `capture`, `session materialize`, and `import-run` now feed the same hardened
  record path so downstream promote/export receives richer canonical evidence.
- Runtime exports for Codex, Claude Code, Hermes, Pi, Odysseus, and Generic now
  include machine-readable task, artifact, validation, and replay contracts.
- Split imported-run capture quality from task outcome in promotion metrics.
- Hardened shell command execution records with minimal environment handling.
- Added shell-free `--run-argv` execution and `--require-cwd-inside-project`
  containment to `omf capability validate`; execution records now report the
  shell mode used.
- Added artifact root import excludes, `.omfignore`, and traversal limits.

### Fixed

- Kept quickstart, import-run, orchestrate, verify, and release smoke paths
  compatible with strict default promotion.

## 0.1.0

- Initial alpha CLI for capturing evidence, promoting capabilities, replaying
  checks, evaluating results, exporting runtime assets, and inspecting local
  workflow state.
