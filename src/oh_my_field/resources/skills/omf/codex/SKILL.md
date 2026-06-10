---
name: omf
description: Track Codex work with OMF, preserve evidence, and promote reusable capabilities.
---

# OMF Skill For Codex

Use OMF as an explicit tracking and capability packaging layer. Continue using
Codex for the actual task, and call OMF only to record session events,
materialize evidence, promote reusable workflows, export capability projections,
and validate target runtime imports.

## Activation

Activate this skill when the user says any of the following:

- "$omf"
- "/omf"
- "use OMF"
- "track this task with OMF"
- "extract this capability"
- "make this reusable"
- "export this capability"

## Operating Rules

1. Keep working through Codex normally.
2. Start an OMF session when the task begins.
3. Record meaningful goal, assumption, command, diff, test, artifact, decision,
   and feedback events.
4. Prefer OMF MCP tools when available; otherwise use the OMF CLI.
5. Do not run risky commands through OMF unless the user explicitly approves.
6. At completion, materialize evidence and promote the workflow only when it is
   meaningfully reusable.

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

## Typical Flow

1. `omf session start --runtime codex --model <model> --goal "..."`
2. `omf session event <session_id> --type command --summary "..."`
3. `omf session finish <session_id> --outcome success|failure|unknown`
4. `omf session materialize <session_id>`
5. `omf promote <evidence_id> --name <capability_name> --description "..."`
6. `omf capability export <capability_name> --target <runtime> --out <path>`
