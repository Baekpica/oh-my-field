# Codex Runtime Adapter

## Generated Files

- `AGENTS.md`
- `capability.md`
- `context.policy.md`
- `harness.md`

## Expected Install Location

Copy or merge the generated files into the target Codex project root. Keep the
OMF export directory as provenance until the target run has been validated.

## Manual Import

```bash
omf capability export repo_issue_triage \
  --target codex \
  --out .omf/exports/repo_issue_triage-codex

omf capability import .omf/exports/repo_issue_triage-codex \
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

Run Codex with the generated `AGENTS.md`, then import the resulting log with
`omf import-run codex --outcome success|failure|unknown`.
