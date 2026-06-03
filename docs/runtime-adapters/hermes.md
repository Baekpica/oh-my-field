# Hermes Runtime Adapter

## Generated Files

- `SOUL.md`
- `skills/<capability>.md`
- `profile.patch.yaml`
- `harness.md`

## Expected Install Location

Apply `profile.patch.yaml` to the target Hermes profile and place generated
skills under the target profile's skills directory. Keep `harness.md` with the
capability export for validation.

## Manual Import

```bash
omf capability export repo_issue_triage \
  --target hermes \
  --out .omf/exports/repo_issue_triage-hermes

omf capability import .omf/exports/repo_issue_triage-hermes \
  --runtime hermes \
  --project target-repo \
  --validate
```

## Validation Command

```bash
omf capability validate repo_issue_triage \
  --target hermes \
  --run-command "hermes-code --profile target --skill repo_issue_triage" \
  --approve-command-risk
```

## Known Limitations

Hermes profile layouts can vary. Treat generated profile patches as reviewable
input, not an automatic overwrite.

## Target Run Example

Run Hermes with the generated skill, save the run log and expected artifacts,
then import the log with `omf import-run hermes --outcome success|failure|unknown`.
