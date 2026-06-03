# Concepts

## Field

The field is the real working environment: a repo, process, infrastructure
surface, support workflow, or reporting task with local constraints and quality
bars.

## Evidence

Evidence is structured data from agent work: logs, prompts, context, command
outputs, diffs, test results, artifacts, feedback, and failures.

## Capability

A capability is a repo-local package built from evidence. It contains
instructions, context policy, harness checks, provenance, review signals, and
integrity metadata.

Generated capability artifacts remain owned by the user or project that created
them. The Apache-2.0 license applies to the OMF CLI and source code, not to a
team's private capability packages unless that team separately publishes them
under Apache-2.0.

## Portability

OMF separates export, import, target validation, and portable status. A bundle
is portable only after a target runtime has been validated by an actual target
run.
