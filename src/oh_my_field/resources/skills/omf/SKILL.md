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
8. If the user asks to use the process in another runtime, export the capability.
9. Keep canonical capability source in OMF; runtime-specific skill files are
   projections.

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
