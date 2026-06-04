# Install

## Persistent CLI Install

```bash
pipx install oh-my-field
omf --help
```

## Try Without Installing

```bash
uvx oh-my-field --help
```

## Development Install

```bash
git clone https://github.com/Baekpica/oh-my-field.git
cd oh-my-field
uv sync --all-extras --dev
uv run omf --help
```

## Agent Activation

OMF can be used manually from the CLI, but the intended loop is agent-assisted.
Activation installs an OMF meta-skill (and optionally an MCP config) so an agent
knows when and how to call OMF during ordinary work.

### Install The Meta-Skill

```bash
omf install skill --runtime codex
omf install skill --runtime claude_code
omf install skill --runtime hermes
omf install skill --runtime generic
```

Every install writes the shared `SKILL.md` plus runtime-specific resources under
the output directory (default `<project>/.omf/agent/omf-skill`), and reports a
`next_action` in its JSON summary. What each runtime targets differs:

| Runtime | Target it writes/patches | Resources written |
| --- | --- | --- |
| `codex` | `<project>/AGENTS.md` | `codex/AGENTS.fragment.md` |
| `claude_code` | `<project>/CLAUDE.md` | `claude_code/CLAUDE.fragment.md` |
| `hermes` | `<out>/hermes/SOUL.fragment.md` | `hermes/SOUL.fragment.md`, `hermes/profile.patch.yaml` |
| `generic` | `<out>/generic/skill.md` | `generic/skill.md` |

For `codex` and `claude_code`, OMF writes the fragment into the project's agent
memory file (`AGENTS.md` / `CLAUDE.md`). If that file already exists and you did
not pass `--overwrite`, OMF does **not** modify it — instead it writes a
`patch-plan.md` next to the fragment so you can merge it manually. For `hermes`
and `generic`, the assets are laid down in the output directory and you wire them
into the runtime yourself (for Hermes, apply `profile.patch.yaml`).

### Skill Install Options

| Option | Default | Purpose |
| --- | --- | --- |
| `--runtime` | (required) | `codex`, `claude_code`, `hermes`, or `generic` |
| `--project` | `.` | Project root used to resolve the target file and relative `--out` |
| `--profile` | none | Runtime profile name (reserved for profile-aware runtimes) |
| `--out` | `.omf/agent/omf-skill` | Output directory for skill resources (relative paths resolve under `--project`) |
| `--dry-run` | off | Plan the writes without touching the filesystem |
| `--overwrite` | off | Replace an existing target file instead of writing a patch plan |

Preview an install without writing anything:

```bash
omf install skill --runtime claude_code --dry-run
```

### Install An MCP Config

For clients that can call OMF as a structured tool surface, generate a config and
run the stdio server:

```bash
omf install mcp --client generic --out .omf/mcp.json
omf mcp serve
```

`--client` currently supports `generic`. The generated config points the client
at the OMF stdio server:

```json
{
  "mcpServers": {
    "oh-my-field": { "command": "omf", "args": ["mcp", "serve"] }
  }
}
```

Add this config to your agent client's MCP settings, then the agent can use the
OMF tool surface (`omf_start_session`, `omf_record_event`,
`omf_materialize_session`, `omf_promote_capability`, `omf_export_capability`,
`omf_health`). The MCP options mirror the skill installer: `--client`,
`--project`, `--out` (default `.omf/mcp.json`), `--dry-run`, `--overwrite`. See
[mcp.md](mcp.md) and [agent-ux.md](agent-ux.md).

After activation, a human can drive OMF with short prompts:

```text
/omf
track this task with OMF
```

## Verify The Install

```bash
omf --help
omf version --json
omf doctor --json
omf import-run --help
omf capability export --help
omf install skill --runtime generic --out /tmp/omf-skill
omf install mcp --client generic --out /tmp/omf-mcp.json
```

From a source checkout, use `uv run omf ...`.
