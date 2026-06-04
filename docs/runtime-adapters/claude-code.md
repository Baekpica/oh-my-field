# Claude Code Runtime Adapter

Implementation: `src/oh_my_field/adapters/runtime_export/claude_code.py`,
registered through `oh_my_field.adapters.runtime_export`.

## Generated Files

- `CLAUDE.md`
- `capability.md`
- `examples.md`
- `checks.md`

## Expected Install Location

Copy or merge `CLAUDE.md` into the target Claude Code project root. Keep the
supporting markdown files near the project memory or in a documented capability
folder.

## Manual Import

```bash
omf capability export repo_issue_triage \
  --target claude_code \
  --out .omf/exports/repo_issue_triage-claude

omf capability import .omf/exports/repo_issue_triage-claude \
  --runtime claude_code \
  --project target-repo \
  --validate
```

## Validation Command

```bash
omf capability validate repo_issue_triage \
  --target claude_code \
  --run-command "claude < task.md" \
  --approve-command-risk
```

## Known Limitations

Claude Code project memory may already contain local instructions. Review
conflicts before merging generated `CLAUDE.md` content.

## Target Run Example

Run Claude Code in the target project, save the transcript or log, then import
it with `omf import-run claude_code --outcome success|failure|unknown`.
