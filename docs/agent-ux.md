# Agent UX

OMF is an agent-facing capability substrate, not an agent runtime. A human
should be able to say "/omf" or "track this task with OMF"; the current agent
keeps doing the real work and uses OMF as the evidence, session, capability,
and portability layer.

## Human UX

Human-facing prompts should stay short:

- "/omf"
- "Track this task with OMF."
- "Turn this workflow into a capability."
- "Export this capability to Hermes."
- "Show this capability's portability status."

## Agent Internal UX

When OMF is active, the agent should translate those short requests into the
stable machine interface:

```bash
omf session start --runtime <runtime> --model <model> --goal "..."
omf session event <session_id> --type command --summary "..."
omf session finish <session_id> --outcome success|failure|unknown
omf session materialize <session_id>
omf promote <evidence_id> --name <capability_name> --description "..."
omf capability export <capability_name> --target <runtime> --out <path>
omf capability import <bundle_path> --runtime <runtime> --validate
omf capability validate <capability_name> --target <runtime> --run-command "..."
```

The CLI is the fallback interface. When MCP tools are available, the agent can
use structured tool calls for the same workflow.

## Activation Semantics

`$omf`, `/omf`, "use OMF", "track this task", "make this reusable", and
"export this capability" activate OMF behavior. Activation changes how the
agent records the work; it does not replace the runtime or require a separate
agent loop.

## Meta-Skill vs Capability Skill

| Surface | Purpose |
| --- | --- |
| OMF meta-skill | Teaches the agent when and how to call OMF during ordinary work. |
| Capability skill | Runtime-specific projection of one reusable capability. |
| MCP tools | Structured agent-native calls into OMF workflows. |
| CLI | Universal machine interface and manual fallback. |

## Session Tracking Flow

Session tracking is a working-state sidecar:

```text
session start/event/finish
  -> AgentSession
  -> session materialize
  -> EvidenceRecord
  -> promote
  -> CapabilityManifest
```

Evidence remains the immutable source for promotion; sessions can collect
incremental goal, context, command, diff, test, artifact, decision, and feedback
events before materialization.

## Export, Import, Validate

Runtime-specific files are projections:

```text
canonical capability package
  -> capability export
  -> runtime bundle
  -> capability import
  -> target overlay
  -> capability validate
  -> validated target run
```

Exported and imported are not the same as validated. A capability becomes
portable only after at least one target import passes a real target run.

## Safety Boundary

OMF should not secretly watch terminals, shell history, or project-wide file
changes. The agent records events explicitly through session commands or MCP
tools. Risky commands remain record-first and require explicit approval before
execution through OMF.
