# Hermes Runtime Adapter

Implementation: `src/oh_my_field/adapters/runtime_export/hermes.py`, registered
through `oh_my_field.adapters.runtime_export`.

## Generated Files

- `skills/<capability>/SKILL.md` (launcher by default; see below)
- `skills/<capability>/references/capability.md` (full style only)
- `skills/<capability>/references/harness.md`
- `skills/<capability>/references/context.policy.md`
- `skills/<capability>/references/task_contract.yaml`
- `skills/<capability>/references/artifacts.yaml`
- `skills/<capability>/references/validation.md`
- `skills/<capability>/references/replay_plan.yaml`

## Launcher Skill

By default the generated `SKILL.md` is an OMF launcher (`omf_managed: true`):
it instructs Hermes to enter the OMF lifecycle (`omf card`, `omf capability
validate`, `omf session start … materialize`) instead of executing the
capability goal directly, and the goal text is not restated in the skill.
Use `--skill-style full` to render the instruction-style projection instead.

## Adoption Surface

```bash
omf runtime install hermes        # controller skill + MCP config
omf runtime conformance hermes    # verify the adoption surface
```

## Expected Install Location

Copy `skills/<capability>/` into the target Hermes skill directory. Keep the OMF
export directory as provenance until the target run has been validated.

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

Hermes profile layouts can vary. OMF exports an installable skill directory, but
does not automatically modify Hermes profiles during capability export.

## Target Run Example

Run Hermes with the generated skill, save the run log and expected artifacts,
then import the log with `omf import-run hermes --outcome success|failure|unknown`.
