# OMF MCP

OMF exposes a minimal stdio MCP surface for agents that support structured tool
calls. The MCP server is not a shell wrapper around the CLI. Each tool calls the
same application workflows used by the CLI and returns JSON-serializable
summary models.

Install a runtime MCP config:

```bash
omf install mcp --client codex
omf install mcp --client claude_code
omf install mcp --client hermes
omf install mcp --client generic --scope export --out .omf/mcp.json
```

`--scope auto` is the default. It resolves to user config patching for Codex,
Claude Code, and Hermes, and to export-only JSON generation for `generic`.

| Client | User config | Project config |
| --- | --- | --- |
| `codex` | `~/.codex/config.toml` | `<project>/.codex/config.toml` |
| `claude_code` | `~/.claude.json` | `<project>/.mcp.json` |
| `hermes` | `~/.hermes/config.yaml` | unsupported |
| `generic` | unsupported | unsupported; writes JSON to `--out` |

The installed config starts the server with:

```bash
omf mcp serve
```

If an `oh-my-field` server already exists, install skips it unless
`--overwrite` is set. Existing config files are backed up before modification.
Use `--dry-run` to inspect the same action plan without writing files or
backups. Use `--server-command` when the agent runtime needs an absolute path to
the `omf` executable.

Initial tool surface:

| Tool | Purpose |
| --- | --- |
| `omf_start_session` | Start tracking the current agent task. |
| `omf_record_event` | Append context, command, diff, test, artifact, or feedback. |
| `omf_finish_session` | Mark the session outcome. |
| `omf_materialize_session` | Convert a session into immutable evidence. |
| `omf_promote_capability` | Promote evidence into a capability package. |
| `omf_export_capability` | Export a capability to Codex, Claude Code, Hermes, or generic assets. |
| `omf_health` | Read capability health and next action. |

OMF keeps its safety boundary explicit: the MCP server records and packages
agent work, but it does not sniff terminal output or run arbitrary risky
commands on behalf of an agent.
