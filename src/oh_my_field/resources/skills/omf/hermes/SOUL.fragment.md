## OMF Skill Behavior

When OMF is active:

- Keep working through Hermes normally.
- Record important task progress to OMF.
- Prefer OMF session commands or MCP tools when available.
- If a task becomes repeatable, export it as a capability package.
- If asked to port to another runtime/model, use `omf capability export` and
  `omf capability validate`.

- Before using OMF CLI from memory, check `omf --help` and the relevant
  subcommand help such as `omf session --help`, `omf promote --help`, or
  `omf capability export --help`.
- Prefer structured MCP tools when available: `omf_record_input`,
  `omf_record_artifact`, `omf_record_validation`, and `omf_record_decision`.
- `omf promote` is strict by default; do not use `--no-strict` unless the user
  explicitly asks to promote legacy or incomplete evidence.
