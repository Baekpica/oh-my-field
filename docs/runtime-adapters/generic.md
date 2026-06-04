# Generic Runtime Adapter

Implementation: `src/oh_my_field/adapters/runtime_export/generic.py`,
registered through `oh_my_field.adapters.runtime_export`.

## Generated Files

- `skill.md`
- `context.policy.yaml`
- `harness.yaml`
- `eval_set.yaml`

## Expected Install Location

Use the generic export when the target runtime does not have a dedicated OMF
adapter. Place the files in the target project's capability or runbook folder.

## Manual Import

```bash
omf capability export repo_issue_triage \
  --target generic \
  --out .omf/exports/repo_issue_triage-generic

omf capability import .omf/exports/repo_issue_triage-generic \
  --runtime generic \
  --project target-repo \
  --validate
```

## Validation Command

```bash
omf capability validate repo_issue_triage \
  --target generic \
  --run-command "./run-capability-check.sh" \
  --approve-command-risk
```

## Known Limitations

Generic bundles do not encode runtime-specific memory or profile behavior. The
target owner must map the files into the local agent workflow.

## Target Run Example

Run the target agent or script with `skill.md` and `harness.yaml`, save the log,
then import it with the matching `omf import-run` adapter if available.
