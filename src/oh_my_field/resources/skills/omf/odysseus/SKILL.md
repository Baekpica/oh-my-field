---
name: omf
description: Track Odysseus agent work with OMF, preserve evidence, and promote reusable capabilities.
category: omf
status: published
source: imported
---

# OMF Skill For Odysseus

Use OMF as an explicit tracking and capability packaging layer. Continue using
Odysseus for the actual task, and call OMF only to record session events,
materialize evidence, promote reusable workflows, export capability projections,
and validate target runtime imports.

## When to Use

Activate this skill when the user asks to use OMF, track a task, extract a
capability, make a workflow reusable, or export a capability.

## Procedure

1. Start an OMF session when the task begins.
2. Record meaningful goal, assumption, command, diff, test, artifact, decision,
   and feedback events.
3. Prefer OMF MCP tools when the Odysseus MCP server is connected; otherwise use
   the OMF CLI.
4. Finish the session with success, failure, or unknown.
5. Materialize evidence and promote only workflows that are meaningfully
   reusable.
6. For cross-runtime use, export the canonical `.omfcap.tar.gz` package, verify
   it, import it into the target project, then validate with target evidence or
   a target run.

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

## Pitfalls

- Do not treat OMF as the Odysseus runtime.
- Do not run risky commands through OMF unless the user explicitly approves.
- Do not treat copying `data/skills/omf/<capability>/` as an OMF import; it
  only installs the native launcher projection.

## Verification

- OMF session contains goal, evidence, and verification events.
- Reusable workflows are promoted from materialized evidence.
