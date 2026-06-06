# Pi Runtime Adapter

Implementation: `src/oh_my_field/adapters/runtime_export/pi.py`, registered
through `oh_my_field.adapters.runtime_export`.

## Source Basis

Pi documents Agent Skills support through user skills at `~/.pi/agent/skills/`,
project skills at `.pi/skills/`, and package resources declared in `package.json`
under the `pi` key. Pi MCP support is provided by `pi-mcp-adapter`, installed via
`pi install npm:pi-mcp-adapter`, which reads standard `.mcp.json` files and
`~/.pi/agent/mcp.json`.

Sources: <https://pi.dev/docs/latest/skills>, <https://pi.dev/docs/latest/packages>,
<https://pi.dev/packages/pi-mcp-adapter>.

## Generated Files

- `.pi/skills/<capability>/SKILL.md`
- `.pi/skills/<capability>/references/capability.md`
- `.pi/skills/<capability>/references/context.policy.md`
- `.pi/skills/<capability>/references/harness.md`
- `package.json` with `pi.skills` pointing at `./.pi/skills`

## Expected Install Location

Use either native Pi path:

```bash
# Project-local copy
cp -R runtime/pi/.pi/skills/<capability> /target/project/.pi/skills/

# Or install the exported runtime package
pi install /absolute/path/to/runtime/pi
```

For the OMF meta-skill itself:

```bash
omf install skill --runtime pi
omf install skill --runtime pi --scope project --project /target/project
```

For MCP:

```bash
pi install npm:pi-mcp-adapter
omf install mcp --client pi
# or project-local
omf install mcp --client pi --scope project --project /target/project
```

## Manual Import

```bash
omf capability export repo_issue_triage   --target pi   --out .omf/exports/repo_issue_triage-pi

omf capability import .omf/exports/repo_issue_triage-pi   --runtime pi   --project target-repo   --validate
```

## Validation Command

```bash
omf capability validate repo_issue_triage   --target pi   --run-command "pi -p 'Run the repo_issue_triage capability against this repo'"   --approve-command-risk
```

## Known Limitations

Static import validation checks files and metadata only. It does not prove Pi can
perform the task in the target project or that `pi-mcp-adapter` is installed in
the user's Pi environment.
