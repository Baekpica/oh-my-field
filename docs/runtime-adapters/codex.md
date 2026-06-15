# Codex Runtime Adapter

Implementation: `src/oh_my_field/adapters/runtime_export/codex.py`, registered
through `oh_my_field.adapters.runtime_export`.

## Generated Files

- `.agents/skills/<capability>/SKILL.md`
- `.agents/skills/<capability>/references/capability.md`
- `.agents/skills/<capability>/references/context.policy.md`
- `.agents/skills/<capability>/references/task_contract.yaml`
- `.agents/skills/<capability>/references/artifacts.yaml`
- `.agents/skills/<capability>/references/validation.md`
- `.agents/skills/<capability>/references/replay_plan.yaml`
- `.agents/skills/<capability>/references/harness.md`

## Expected Install Location

Copy the generated `.agents/skills/<capability>/` directory into the target
Codex project root, or into the user-level skill directory if the capability is
intended to be global. Keep the OMF export directory as provenance until the
target run has been validated.

Skill installation only makes Codex discover the launcher. It does not import
the capability into the target project. Run `omf capability import` against the
canonical package before using the launcher for a target run.

## Manual Import

```bash
omf capability export repo_issue_triage \
  --target codex \
  --out .omf/exports/repo_issue_triage-codex

omf verify package .omf/exports/repo_issue_triage-codex.omfcap.tar.gz

omf capability import .omf/exports/repo_issue_triage-codex.omfcap.tar.gz \
  --runtime codex \
  --project target-repo \
  --validate
```

## Validation Command

```bash
omf capability validate repo_issue_triage \
  --target codex \
  --run-command "codex exec --full-auto < task.md" \
  --approve-command-risk
```

## Known Limitations

Static import validation checks files and metadata only. It does not prove Codex
can perform the task in the target project.

## Target Run Example

Run Codex with the generated skill installed, then import the resulting log with
`omf import-run codex --outcome success|failure|unknown`.
