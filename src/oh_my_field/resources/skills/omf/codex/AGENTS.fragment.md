## OMF Tracking

When the user activates OMF with "$omf", "/omf", or asks to track/export a
reusable process:

- Treat `omf` as a tracking and capability packaging tool.
- Continue doing the actual coding work normally.
- Use OMF commands to record session events, artifacts, tests, diffs, and user
  feedback.
- At the end, summarize whether the workflow should become a capability.

- Before using OMF CLI from memory, check `omf --help` and the relevant
  subcommand help such as `omf session --help`, `omf promote --help`, or
  `omf capability export --help`.
- Prefer structured MCP tools when available: `omf_record_input`,
  `omf_record_artifact`, `omf_record_validation`, and `omf_record_decision`.
- `omf promote` is strict by default; do not use `--no-strict` unless the user
  explicitly asks to promote legacy or incomplete evidence.
