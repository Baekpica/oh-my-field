---
name: omf
description: Track Claude Code work with OMF, preserve evidence, and promote reusable capabilities.
---

# OMF Skill For Claude Code

Use OMF as an explicit tracking and capability packaging layer. Continue using
Claude Code for the actual task, and call OMF only to record session events,
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

1. Keep working through Claude Code normally.
2. Start an OMF session when the task begins.
3. Record meaningful goal, assumption, command, diff, test, artifact, decision,
   and feedback events.
4. Prefer OMF MCP tools when available; otherwise use the OMF CLI.
5. Do not run risky commands through OMF unless the user explicitly approves.
6. At completion, materialize evidence and promote the workflow only when it is
   meaningfully reusable.

## Typical Flow

1. `omf session start --runtime claude_code --model <model> --goal "..."`
2. `omf session event <session_id> --type command --summary "..."`
3. `omf session finish <session_id> --outcome success|failure|unknown`
4. `omf session materialize <session_id>`
5. `omf promote <evidence_id> --name <capability_name> --description "..."`
6. `omf capability export <capability_name> --target <runtime> --out <path>`
