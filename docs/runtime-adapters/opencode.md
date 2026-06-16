# OpenCode Runtime Adapter

Implementation: `src/oh_my_field/adapters/runtime_export/opencode.py`,
registered through `oh_my_field.adapters.runtime_export`.

## Source Basis

OpenCode discovers project skills from `.opencode/skills/<name>/SKILL.md`,
global skills from `~/.config/opencode/skills/<name>/SKILL.md`, and MCP servers
from the `mcp` object in `opencode.json`. OpenCode skill names are lowercase
hyphen-separated, so OMF maps capability IDs such as `repo_issue_triage` to
skill directories such as `repo-issue-triage`.

Sources: <https://opencode.ai/docs/skills/>,
<https://opencode.ai/docs/config/>, <https://opencode.ai/docs/mcp-servers>.

## Generated Files

- `.opencode/skills/<capability-slug>/SKILL.md`
- `.opencode/skills/<capability-slug>/references/capability.md` (full style only)
- `.opencode/skills/<capability-slug>/references/context.policy.md`
- `.opencode/skills/<capability-slug>/references/harness.md`
- `.opencode/skills/<capability-slug>/references/task_contract.yaml`
- `.opencode/skills/<capability-slug>/references/artifacts.yaml`
- `.opencode/skills/<capability-slug>/references/validation.md`
- `.opencode/skills/<capability-slug>/references/replay_plan.yaml`

## Adoption Surface

```bash
omf runtime install opencode        # controller skill + MCP config
omf runtime conformance opencode    # verify the adoption surface
```

`omf install skill --runtime opencode` writes the controller skill to
`~/.config/opencode/skills/omf/SKILL.md` by default. Project scope writes
`<project>/.opencode/skills/omf/SKILL.md`.

`omf install mcp --client opencode` patches
`~/.config/opencode/opencode.json` by default. Project scope patches
`<project>/opencode.json`.

## Manual Import

```bash
omf capability export repo_issue_triage \
  --target opencode \
  --out .omf/exports/repo_issue_triage-opencode

omf verify package .omf/exports/repo_issue_triage-opencode.omfcap.tar.gz

omf capability import .omf/exports/repo_issue_triage-opencode.omfcap.tar.gz \
  --runtime opencode \
  --project target-repo \
  --validate
```

## Validation Command

```bash
omf capability validate repo_issue_triage \
  --target opencode \
  --run-command "opencode run --prompt 'Run the repo_issue_triage capability against this repo'" \
  --approve-command-risk
```

## Known Limitations

Static import validation checks files and metadata only. It does not prove
OpenCode can perform the task in the target project or that the user's
OpenCode provider/model configuration is available.

## Target Run Example

Run OpenCode with the generated skill installed, save the run log and expected
artifacts, then import the log with
`omf import-run opencode --outcome success|failure|unknown`.
