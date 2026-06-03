# Portability

OMF keeps runtime conversion separate from target validation.

- `exported`: a capability has been converted into a target runtime bundle.
- `imported`: the bundle has been materialized in a target project.
- `validated`: an actual target run passed under the target runtime/model.
- `portable`: at least one target import has been validated.

Static import validation can show that files and metadata are present, but it
does not prove the target runtime can perform the task.

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
