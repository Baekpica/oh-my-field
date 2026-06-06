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

## Pitfalls

- Do not treat OMF as the Odysseus runtime.
- Do not run risky commands through OMF unless the user explicitly approves.

## Verification

- OMF session contains goal, evidence, and verification events.
- Reusable workflows are promoted from materialized evidence.
