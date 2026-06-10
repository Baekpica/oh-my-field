---
name: omf
description: Track agent work with OMF, preserve evidence, and promote reusable capabilities.
---

# OMF Meta-Skill

Use OMF as an explicit tracking and capability packaging layer. Continue using
the current agent/runtime for the actual work, and call OMF to record session
events, materialize evidence, promote reusable workflows, export capability
projections, and validate target runtime imports.

## CLI And MCP Discovery

- Before using an OMF CLI command from memory, run `omf --help` and the
  relevant subcommand help, such as `omf session --help`,
  `omf session event --help`, `omf promote --help`, and
  `omf capability export --help`.
- Prefer structured MCP tools for portable records: `omf_record_input`,
  `omf_record_artifact`, `omf_record_validation`, and `omf_record_decision`.
- If MCP is unavailable, record equivalent CLI events: `context` for inputs,
  `artifact` for outputs, `test_result` for validations, and `decision` for
  promotion rationale.
- `omf promote` uses the strict quality gate by default; do not use
  `--no-strict` unless the user explicitly asks to promote legacy or incomplete
  evidence.

