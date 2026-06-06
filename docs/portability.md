# Portability

OMF keeps runtime conversion separate from target validation.

- `exported`: a capability has been converted into a target runtime bundle.
- `imported`: the bundle has been materialized in a target project.
- `validated`: an actual target run passed under the target runtime/model.
- `portable`: at least one target import has been validated.

Static import validation can show that files and metadata are present, but it
does not prove the target runtime can perform the task.

## Implementation Layout

The public import path remains `oh_my_field.portability`, but it is a
compatibility shim. New code should import the layered modules directly:

- `oh_my_field.domain.portability.models` for portability artifacts.
- `oh_my_field.domain.portability.readiness` for transfer and readiness rules.
- `oh_my_field.application.portability.*_workflow` for use-case execution.
- `oh_my_field.adapters.runtime_export` for target runtime bundle rendering.
- `oh_my_field.infrastructure.portability` for bundle and overlay file I/O.

Runtime export adapters only render target-specific files. They do not own the
canonical capability package, evidence provenance, import overlay, or target
validation report.

```bash
omf capability export repo_issue_triage \
  --target hermes \
  --out .omf/exports/repo_issue_triage-hermes

omf capability import .omf/exports/repo_issue_triage-hermes \
  --runtime hermes \
  --validate

omf capability validate repo_issue_triage \
  --target hermes \
  --run-command "hermes-code --profile target --skill repo_issue_triage" \
  --approve-command-risk
```


## Pi And Odysseus Capability Flow

Pi exports render a project-local `.pi/skills/<capability>/SKILL.md` tree plus a
`package.json` with a Pi manifest. That gives users two native import paths:
copy `.pi/skills/<capability>` into a project, or run `pi install /path/to/runtime/pi`
against the exported runtime package.

Odysseus exports render `data/skills/omf/<capability>/SKILL.md` with Odysseus'
structured sections (`When to Use`, `Procedure`, `Pitfalls`, `Verification`). To
import into a running Odysseus checkout, copy the generated `data/skills/omf/`
subtree into the Odysseus project data directory and reload/restart Odysseus so
its skill scanner sees the file.

For cross-agent portability, keep the OMF export bundle as the canonical source.
The native Pi/Odysseus skill files are projections. After copying or installing a
projection, run `omf capability import ... --runtime pi|odysseus --validate` in
the target project, then run an actual target-agent task and record the result
with `omf import-run pi|odysseus` or OMF session evidence before marking the
capability portable.
