## OMF Tracking

When OMF is active, keep working through Claude Code normally. Use OMF commands
or MCP tools to record goal, assumptions, context, commands, diffs, tests, final
outcome, and user feedback. If the workflow is reusable, promote it as an OMF
capability and keep runtime-specific skill files as projections.

- Before using OMF CLI from memory, check `omf --help` and the relevant
  subcommand help such as `omf session --help`, `omf promote --help`, or
  `omf capability export --help`.
- Prefer structured MCP tools when available: `omf_record_input`,
  `omf_record_artifact`, `omf_record_validation`, and `omf_record_decision`.
- `omf promote` is strict by default; do not use `--no-strict` unless the user
  explicitly asks to promote legacy or incomplete evidence.
