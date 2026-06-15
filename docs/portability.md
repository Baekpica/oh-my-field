# Portability

OMF keeps runtime conversion separate from target validation.

- `exported`: a capability has been packaged as a canonical `.omfcap.tar.gz`
  archive, with optional target runtime projections.
- `imported`: the archive or directory package has been materialized in a
  target project's OMF registry.
- `validated`: an actual target run passed under the target runtime/model.
- `portable`: at least one target import has been validated.

Static import validation can show that files and metadata are present, but it
does not prove the target runtime can perform the task.

## Skill Portability Is Not Capability Portability

- Skill portability: one agent can read another agent's instructions.
- Capability portability: one agent can re-run a validated unit of work
  inside the OMF lifecycle on another runtime.

OMF does not treat agent-native skills as capabilities. A skill is only an
adapter surface that lets an agent enter the OMF lifecycle. The capability
itself remains managed by OMF, including context materialization, runtime
adaptation, harness execution, evidence collection, and report generation.
Without an OMF report, a runtime execution is considered unverified.

## Canonical Capability Packages

`omf capability export` produces an archive package by default:

```bash
omf capability export repo_issue_triage \
  --target hermes \
  --out .omf/exports/repo_issue_triage-hermes
```

The canonical transferable artifact is the resulting `.omfcap.tar.gz` package.
It includes the runtime-neutral capability, runtime projection files,
`package.yaml`, and `MANIFEST.sha256`. Directory exports remain available for
review and legacy workflows with `--format dir`, but copying runtime projection
files is not an import. Every target runtime must import the package into the
target project before treating the capability as available:

```bash
omf capability import repo_issue_triage-hermes.omfcap.tar.gz \
  --runtime hermes \
  --project target-repo \
  --validate
```

Archive packages include `package.yaml` and `MANIFEST.sha256`. Use
`omf verify package <package.omfcap.tar.gz>` before importing untrusted
packages, or `omf capability unpack <package.omfcap.tar.gz>` to inspect one
without installing it.

Export/import/validate summaries include package path fields such as
`package_path`, `unpacked_path`, and `imported_package_path`, plus
`next_commands` so an agent does not have to infer the follow-up lifecycle
from prose.

## Launcher Skill Projections

`omf capability export` renders the per-capability skill as a **launcher** by
default: the generated `SKILL.md` carries `omf_managed: true` frontmatter,
tells the agent to import the canonical package and enter the OMF lifecycle
(`omf capability import`, `omf card`, `omf capability validate`, `omf session
start … materialize`), and does not restate the capability goal or procedure.
The goal stays in the OMF package and is inspected through `omf card <name>` or
the `omf_inspect_capability` MCP tool.

Pass `--skill-style full` to render the previous instruction-style projection
instead. Full-style exports set `agent_view.direct_execution_allowed: true` in
`portability.yaml`, and import/validation reports warn that the target agent
can bypass the OMF lifecycle from the skill surface.

## Runtime Conformance

`omf runtime install <runtime>` installs the OMF controller (meta) skill plus
the MCP client config for an agent runtime. `omf runtime conformance
<runtime>` then statically checks the adoption surface:

1. the OMF controller skill is installed,
2. the MCP client config is present,
3. the `omf` CLI is reachable on PATH,
4. installed skills matching a known OMF capability are launchers
   (`omf_managed` frontmatter) — unrelated native skills are ignored,
5. imported targets for that runtime have been validated.

A failed check returns `status: degraded` with a recommendation per check.
Conformance never invokes the agent runtime; folding a real target run into
the eval stays on `omf capability validate --run-command/--run-argv`. That is
also the current pattern for OMF-led execution: pass the target agent CLI as
the validation run command and gate `validated` status on its exit code.

## Contract Files

Promotion and export carry the hardened run contract forward. The canonical
capability package includes:

- `contracts/task_contract.yaml`: required inputs, expected artifacts, and checks.
- `contracts/artifacts.yaml`: artifact kind, path, role, and validation mapping.
- `contracts/validation.md`: human-readable validation guide.
- `contracts/replay_plan.yaml`: replay and target-run expectations.
- `validators/validate_contract.py`: generic contract validator.

Dedicated runtime projections copy the same contract into `references/` next to
the generated skill. The generic projection keeps the `contracts/` and
`validators/` directories directly in the runtime export. Target agents should
read those files before deciding that a generated output is complete.

## Implementation Layout

The public import path remains `oh_my_field.portability`, but it is a
compatibility shim. New code should import the layered modules directly:

- `oh_my_field.domain.portability.models` for portability artifacts.
- `oh_my_field.domain.portability.readiness` for transfer and readiness rules.
- `oh_my_field.application.portability.*_workflow` for use-case execution.
- `oh_my_field.adapters.runtime_export` for target runtime projection rendering.
- `oh_my_field.infrastructure.portability` for package, projection, and overlay
  file I/O.

Runtime export adapters only render target-specific files. They do not own the
canonical capability package, evidence provenance, import overlay, or target
validation report.

```bash
omf capability export repo_issue_triage \
  --target hermes \
  --out .omf/exports/repo_issue_triage-hermes

omf capability import .omf/exports/repo_issue_triage-hermes.omfcap.tar.gz \
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

For cross-agent portability, keep the OMF `.omfcap.tar.gz` archive as the
canonical source. The native Pi/Odysseus skill files are projections. After
copying or installing a projection, run
`omf capability import ... --runtime pi|odysseus --validate` in the target
project, then run an actual target-agent task and record the result with
`omf import-run pi|odysseus` or OMF session evidence before marking the
capability portable.
