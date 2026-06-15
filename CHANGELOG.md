# Changelog

All notable changes to this project will be documented here.

## Unreleased

### Added

- Added target validation and overlay v0.2 schema contracts with explicit
  `hard_blockers`, `warnings`, advisory `portability_risk`, and advisory
  `validation_confidence` fields.
- Added `omf capability validate --run-contract-validator` to opt into the
  packaged `validators/validate_contract.py` during target validation.

### Changed

- Changed portability validation so static readiness/risk no longer blocks
  `validated`; actionable blockers such as missing tools, unresolved remaps,
  failed target runs, missing expected artifacts, and contract validator
  failures now drive `needs_adaptation`.


## 0.2.5 - 2026-06-15

### Added

- Added archive-first portability packaging: `omf capability export` now emits
  a canonical `.omfcap.tar.gz` package by default, with `package.yaml` and
  `MANIFEST.sha256` integrity metadata. Directory exports remain available with
  `--format dir`.
- Added `omf capability unpack <archive>` and `omf verify package <archive>` so
  target agents and humans can inspect or verify a package before importing it.
- Added archive and directory import support to `omf capability import`, plus
  package path fields and `next_commands` in export/import/validation summaries.
- Added security coverage for unsafe archive members, including path traversal,
  absolute paths, and symlink or hardlink escapes.

### Changed

- Updated launcher skill and runtime adapter guidance so every runtime enters a
  target project through `omf capability import`; copying a Codex, Claude Code,
  Hermes, Pi, Odysseus, or generic projection is documented as launcher
  installation only.
- Updated portability documentation, quickstart, runtime adapter docs, and OMF
  meta-skill resources around the `export -> verify package -> import ->
  validate` lifecycle.

## 0.2.4 - 2026-06-11

### Added

- Added structured session-event extraction to `import-run`: dedicated JSONL
  parsers for `claude_code` and `codex`, and a heuristic JSONL parser for the
  other runtimes, fill `tool_calls`, `generated_commands`, `execution_outputs`,
  and `cost_metrics` on the evidence record. Parsing is enrichment, never a
  gate — logs with no recognizable events import exactly as before, and the
  parser used is recorded as a run observation.
- Added a repeatable `--redact-pattern` option to `import-run` so custom
  secret formats are redacted from captured artifact text and snapshot
  previews; invalid regexes fail the import with a clear error.
- Context packing now enforces `FieldPolicy.forbidden_context` in addition to
  `ContextPolicy.forbidden`; field-policy exclusions are reported with a
  distinct reason in the pack plan.
- Command execution records any stripped env var whose name looks
  secret-bearing (`*_API_KEY`, `*_SECRET`, `*_TOKEN`, ...) in `blocked_env`
  instead of only a fixed list. The environment stays allowlist-only.
- Added tamper-detection coverage for the integrity `verify` surface
  (tampered records, tampered manifests, deleted source evidence, forged
  chain links).

### Fixed

- Secret redaction now matches env-var-style keys (`OPENAI_API_KEY=...`) and
  JSON/YAML-quoted keys (`"api_key": ...`), adds an `sk-*` value pattern, and
  covers artifact snapshot text previews, which previously re-read raw file
  bytes and bypassed redaction. Shared patterns live in
  `domain/evidence/redaction.py`.
- `omf version` and `omf doctor` now derive the package version from installed
  metadata instead of a hardcoded `__version__`, which had been stuck at
  0.2.2 since the 0.2.3 release.

## 0.2.3 - 2026-06-11

### Added

- Added launcher-style capability skill projections as the export default:
  generated `SKILL.md` files carry `omf_managed` frontmatter, direct the
  target agent into the OMF lifecycle, and no longer restate the capability
  goal. `--skill-style full` keeps the previous instruction-style projection.
- Added `lifecycle_owner` and `agent_view` (skill style, direct-execution
  flag) to the portability manifest and target overlays; validation reports
  warn when a full-style projection allows direct execution.
- Added `omf runtime install <runtime>` (controller skill + MCP config) and
  `omf runtime conformance <runtime>` static adoption-surface checks.
- Added MCP adoption tools: `omf_list_capabilities`,
  `omf_inspect_capability`, and `omf_validate_capability`.

## 0.2.2 - 2026-06-10

### Added

- Added a `privilege_escalation` command risk category: `sudo`/`su`/`doas` are
  flagged, and the wrapped command is still classified (e.g. `sudo rm -rf`
  also reads as `destructive`).
- Added GitHub token, Slack token, JWT, and private-key-block patterns to
  import-run secret redaction.
- Added an end-to-end roundtrip test covering
  import-run → promote → export → import → validate.
- Added Python 3.13 to the CI quality matrix and a pytest coverage report.

### Changed

- `import-run` now redacts secrets by default; pass `--no-redact-secrets` to
  keep raw content.
- The Hermes runtime export now includes `capability.md` (base instructions)
  and `context.policy.md`, matching the other runtime targets.

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
