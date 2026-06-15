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
omf install skill --runtime pi
omf install skill --runtime odysseus --project /path/to/odysseus
omf install skill --runtime generic --scope export
```

`--scope auto` is the default. For Codex, Claude Code, Hermes, and Pi,
`auto` resolves to `user` and writes directly to the runtime's user-level skill
discovery path. For Odysseus, `auto` resolves to `project` because Odysseus
stores skills under its app data directory. For `generic`, `auto` resolves to
`export` and writes reviewable assets under `--out`.

| Runtime | `user` target | `project` target | `export` layout |
| --- | --- | --- | --- |
| `codex` | `~/.agents/skills/omf/SKILL.md` | `<project>/.agents/skills/omf/SKILL.md` | `<out>/codex/.agents/skills/omf/SKILL.md` |
| `claude_code` | `~/.claude/skills/omf/SKILL.md` | `<project>/.claude/skills/omf/SKILL.md` | `<out>/claude_code/.claude/skills/omf/SKILL.md` |
| `hermes` | `~/.hermes/skills/omf/SKILL.md` | unsupported | `<out>/hermes/skills/omf/SKILL.md` |
| `pi` | `~/.pi/agent/skills/omf/SKILL.md` | `<project>/.pi/skills/omf/SKILL.md` | `<out>/pi/.pi/skills/omf/SKILL.md` |
| `odysseus` | unsupported | `<project>/data/skills/omf/omf/SKILL.md` | `<out>/odysseus/data/skills/omf/omf/SKILL.md` |
| `generic` | unsupported | unsupported | `<out>/generic/skill.md` |

OMF's internal state still lives under `.omf` (`.omf/config.yaml`,
`.omf/evidence`, `.omf/sessions`, `.omf/exports`, ...). Agent activation assets
are separate and are installed where the selected runtime discovers skills. The
installed skills tell agents to inspect `omf --help` and the relevant subcommand
help before using remembered CLI syntax.

If a target already exists and you did not pass `--overwrite`, OMF skips that
target and reports `skip_existing` in the JSON `actions`. `--dry-run` reports the
same plan without writing files. Codex skill installs also include
`agents/openai.yaml` metadata next to `SKILL.md`; MCP configuration is handled by
`omf install mcp`.

### Skill Install Options

| Option | Default | Purpose |
| --- | --- | --- |
| `--runtime` | (required) | `codex`, `claude_code`, `hermes`, `pi`, `odysseus`, or `generic` |
| `--project` | `.` | Project root used to resolve the target file and relative `--out` |
| `--profile` | none | Runtime profile name (reserved for profile-aware runtimes) |
| `--out` | `.omf/agent/omf-skill` | Output directory for `export` scope resources |
| `--scope` | `auto` | `auto`, `user`, `project`, or `export` |
| `--home` | current home | Home directory used for `user` scope installs |
| `--dry-run` | off | Plan the writes without touching the filesystem |
| `--overwrite` | off | Replace an existing target file instead of skipping it |

Preview an install without writing anything:

```bash
omf install skill --runtime claude_code --dry-run
```

### Install An MCP Config

For clients that can call OMF as a structured tool surface, patch the runtime's
MCP config and run the stdio server:

```bash
omf install mcp --client codex
omf install mcp --client claude_code
omf install mcp --client hermes
omf install mcp --client pi
omf install mcp --client odysseus --project /path/to/odysseus
omf install mcp --client generic --scope export --out .omf/mcp.json
omf mcp serve
```

`--scope auto` resolves to `user` for Codex, Claude Code, Hermes, and Pi; it
resolves to `project` for Odysseus and to `export` for `generic`.

| Client | `user` config | `project` config | `export` |
| --- | --- | --- | --- |
| `codex` | `~/.codex/config.toml` | `<project>/.codex/config.toml` | unsupported |
| `claude_code` | `~/.claude.json` | `<project>/.mcp.json` | unsupported |
| `hermes` | `~/.hermes/config.yaml` | unsupported | unsupported |
| `pi` | `~/.pi/agent/mcp.json` | `<project>/.mcp.json` | unsupported |
| `odysseus` | unsupported | `<project>/.omf/agent/odysseus/oh-my-field.add-server.json` API payload | unsupported |
| `generic` | unsupported | unsupported | JSON snippet at `--out` |

The installed server entry points the client at the OMF stdio server:

```json
{
  "mcpServers": {
    "oh-my-field": { "command": "omf", "args": ["mcp", "serve"] }
  }
}
```

For Codex the same server is written as TOML; for Hermes it is written as YAML.
For Pi it is written as JSON and requires the `pi-mcp-adapter` package. For
Odysseus, OMF writes a reviewable `/api/mcp/servers` form payload because
Odysseus persists MCP servers through its admin API/database rather than a
shared MCP config file.
If an `oh-my-field` server already exists, OMF skips it unless `--overwrite` is
set. When a config file already exists and OMF writes a change, it creates a
timestamped backup next to the original file. `--server-command` overrides the
server executable path; otherwise OMF uses `shutil.which("omf")` and falls back
to `"omf"` with a `next_action` reminder to check PATH.

Add or verify this config in your agent client's MCP settings, then the agent
can use the OMF tool surface (`omf_start_session`, `omf_record_input`,
`omf_record_artifact`, `omf_record_validation`, `omf_record_decision`,
`omf_record_event`, `omf_materialize_session`, `omf_promote_capability`,
`omf_export_capability`, `omf_health`). The JSON summary includes the resolved
`scope`, `config_path`,
optional `backup_path`, `server_name`, `next_action`, and idempotent `actions`.
See [mcp.md](mcp.md) and [agent-ux.md](agent-ux.md).

After activation, a human can drive OMF with short prompts:

```text
/omf
track this task with OMF
```

## Verify The Install

```bash
omf --help
omf --version --json
omf doctor --json
omf import-run --help
omf capability export --help
omf install skill --runtime codex --home /tmp/omf-home
omf install skill --runtime pi --home /tmp/omf-home
omf install skill --runtime odysseus --project /tmp/odysseus
omf install skill --runtime generic --scope export --out /tmp/omf-skill
omf install mcp --client codex --home /tmp/omf-home
omf install mcp --client pi --home /tmp/omf-home
omf install mcp --client odysseus --project /tmp/odysseus
omf install mcp --client generic --scope export --out /tmp/omf-mcp.json
```

From a source checkout, use `uv run omf ...`.

## Source Notes For Pi And Odysseus

Pi support follows the official Pi docs: Pi loads user skills from
`~/.pi/agent/skills/`, project skills from `.pi/skills/`, and package resources
from `package.json` `pi.skills` entries. Pi MCP support requires installing
`pi-mcp-adapter`, which reads `.mcp.json` and `~/.pi/agent/mcp.json`.

Odysseus support follows the upstream repository: skills are disk-backed under
`data/skills/<category>/<name>/SKILL.md`, while MCP servers are registered by the
admin-only `/api/mcp/servers` route and persisted by Odysseus. OMF therefore
installs Odysseus skills directly and writes a reviewable MCP registration
payload for the Odysseus API/settings flow.

Sources: <https://pi.dev/docs/latest/skills>, <https://pi.dev/docs/latest/packages>,
<https://pi.dev/packages/pi-mcp-adapter>,
<https://github.com/pewdiepie-archdaemon/odysseus>,
<https://raw.githubusercontent.com/pewdiepie-archdaemon/odysseus/main/services/memory/skill_format.py>,
<https://raw.githubusercontent.com/pewdiepie-archdaemon/odysseus/main/routes/mcp_routes.py>.
