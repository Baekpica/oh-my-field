---
name: omf
description: Track agent work with OMF, preserve evidence, and promote reusable capabilities.
---

# OMF Skill

## Purpose

Use OMF to turn useful agent work into evidence-backed, reusable capabilities.
OMF is not the agent runtime. Continue using the current agent/runtime for the
actual task.

## Activation

Activate this skill when the user says any of the following:

- "$omf"
- "/omf"
- "use OMF"
- "use omf skill"
- "track this task with OMF"
- "extract this capability"
- "export this capability to another agent/runtime"
- "make this reusable"

## Operating Rules

1. Do not interrupt the user's normal task flow.
2. Start an OMF session when the task begins.
3. Record the user's goal, assumptions, constraints, files touched, commands,
   diffs, tests, artifacts, and feedback.
4. Prefer structured OMF commands or MCP tools over ad-hoc notes.
5. Do not run risky commands through OMF unless the user explicitly approves.
6. At task completion, decide whether the process is reusable.
7. If reusable, suggest or run capability promotion.
8. If the user asks to use the process in another runtime, export the
   canonical archive package and runtime projection.
9. Keep canonical capability source in OMF; runtime-specific skill files are
   projections.
10. Treat copying a runtime projection as launcher installation only; the
    target project must still run `omf capability import`.

## CLI And MCP Discovery

- Before using an OMF CLI command from memory, run `omf --help` and the
  relevant subcommand help, such as `omf session --help`,
  `omf session event --help`, `omf promote --help`, and
  `omf capability export --help`. For portability work, also check
  `omf capability import --help`, `omf capability unpack --help`,
  `omf capability validate --help`, and `omf verify package --help`.
- Prefer structured MCP tools for portable records: `omf_record_input`,
  `omf_record_artifact`, `omf_record_validation`, and `omf_record_decision`.
- If MCP is unavailable, record equivalent CLI events: `context` for inputs,
  `artifact` for outputs, `test_result` for validations, and `decision` for
  promotion rationale.
- `omf promote` uses the strict quality gate by default; do not use
  `--no-strict` unless the user explicitly asks to promote legacy or incomplete
  evidence.

## Typical Flow

1. Start tracking:
   `omf session start --runtime <runtime> --model <model> --goal "..."`
2. Record events:
   `omf session event <session_id> --type command --summary "..."`
3. Finish session:
   `omf session finish <session_id> --outcome success|failure|unknown`
4. Materialize evidence:
   `omf session materialize <session_id>`
5. Promote capability if useful:
   `omf promote <evidence_id> --name <capability_name> --description "..."`
6. Export capability if requested:
   `omf capability export <capability_name> --target <runtime> --out <path>`
7. Verify the package:
   `omf verify package <path>.omfcap.tar.gz`
8. Import into the target project before any target run:
   `omf capability import <path>.omfcap.tar.gz --runtime <runtime> --project <target_project> --validate`
9. Validate with target evidence or a target run:
   `omf capability validate <capability_name> --target <runtime> --run-command "..."`
