# Claude Code Runtime Adapter

Implementation: `src/oh_my_field/adapters/runtime_export/claude_code.py`,
registered through `oh_my_field.adapters.runtime_export`.

## Generated Files

- `.claude/skills/<capability>/SKILL.md`
- `.claude/skills/<capability>/references/capability.md`
- `.claude/skills/<capability>/references/examples.md`
- `.claude/skills/<capability>/references/checks.md`

## Expected Install Location

Copy the generated `.claude/skills/<capability>/` directory into the target
Claude Code project root, or into the user-level skill directory if the
capability is intended to be global.

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
conflicts between project memory and the generated capability skill before
validating the target run.

## Target Run Example

Run Claude Code in the target project, save the transcript or log, then import
it with `omf import-run claude_code --outcome success|failure|unknown`.
