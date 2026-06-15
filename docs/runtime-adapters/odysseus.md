# Odysseus Runtime Adapter

Implementation: `src/oh_my_field/adapters/runtime_export/odysseus.py`, registered
through `oh_my_field.adapters.runtime_export`.

## Source Basis

Odysseus describes its Agent surface as built on opencode, MCP, files, shell,
skills, and memory. Its skill storage code reads `SKILL.md` files under
`data/skills/<category>/<name>/` with YAML frontmatter and structured sections
such as `When to Use`, `Procedure`, `Pitfalls`, and `Verification`. Its MCP route
registers servers through the admin-only `/api/mcp/servers` endpoint and stores
server metadata in Odysseus state rather than reading a shared MCP JSON file.

Sources: <https://github.com/pewdiepie-archdaemon/odysseus>,
<https://raw.githubusercontent.com/pewdiepie-archdaemon/odysseus/main/services/memory/skill_format.py>,
<https://raw.githubusercontent.com/pewdiepie-archdaemon/odysseus/main/routes/mcp_routes.py>.

## Generated Files

- `data/skills/omf/<capability>/SKILL.md`
- `data/skills/omf/<capability>/references/capability.md`
- `data/skills/omf/<capability>/references/context.policy.md`
- `data/skills/omf/<capability>/references/harness.md`
- `data/skills/omf/<capability>/references/task_contract.yaml`
- `data/skills/omf/<capability>/references/artifacts.yaml`
- `data/skills/omf/<capability>/references/validation.md`
- `data/skills/omf/<capability>/references/replay_plan.yaml`

## Expected Install Location

Copy the generated `data/skills/omf/<capability>/` directory into the target
Odysseus checkout's `data/skills/omf/` directory, then restart or reload
Odysseus so its skill scanner sees the new file.

This only installs the native launcher projection. It does not import the
capability into the target project's OMF registry. Run `omf capability import`
against the canonical package before validating a web workspace run.

For the OMF meta-skill itself:

```bash
omf install skill --runtime odysseus --project /path/to/odysseus
```

For MCP, OMF writes a reviewable Odysseus API payload:

```bash
omf install mcp --client odysseus --project /path/to/odysseus
cat /path/to/odysseus/.omf/agent/odysseus/oh-my-field.add-server.json
```

Post that payload's `form` fields to `/api/mcp/servers` as an Odysseus admin, or
add the same stdio server in Settings > MCP.

## Manual Import

```bash
omf capability export repo_issue_triage \
  --target odysseus \
  --out .omf/exports/repo_issue_triage-odysseus

omf verify package .omf/exports/repo_issue_triage-odysseus.omfcap.tar.gz

omf capability import .omf/exports/repo_issue_triage-odysseus.omfcap.tar.gz \
  --runtime odysseus \
  --project target-repo \
  --validate
```

## Validation Command

Odysseus is a web workspace, so validation is usually a manual target run: run
the task in Odysseus with the generated skill available, export or capture the
resulting log/artifacts, then import that evidence:

```bash
omf import-run odysseus \
  --log /path/to/odysseus-run.log \
  --goal "Validate repo_issue_triage in Odysseus" \
  --outcome success
```

## Known Limitations

OMF does not write directly into the Odysseus database or bypass Odysseus admin
authentication. The MCP installer creates an API registration payload so the
operator can apply it through the native Odysseus admin/settings flow.
