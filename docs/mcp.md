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
omf install mcp --client pi
omf install mcp --client odysseus --project /path/to/odysseus
omf install mcp --client generic --scope export --out .omf/mcp.json
```

`--scope auto` is the default. It resolves to user config patching for Codex,
Claude Code, Hermes, and Pi; to a project-scoped Odysseus API payload; and to
export-only JSON generation for `generic`.

| Client | User config | Project config |
| --- | --- | --- |
| `codex` | `~/.codex/config.toml` | `<project>/.codex/config.toml` |
| `claude_code` | `~/.claude.json` | `<project>/.mcp.json` |
| `hermes` | `~/.hermes/config.yaml` | unsupported |
| `pi` | `~/.pi/agent/mcp.json` | `<project>/.mcp.json` |
| `odysseus` | unsupported | `<project>/.omf/agent/odysseus/oh-my-field.add-server.json` API payload |
| `generic` | unsupported | unsupported; writes JSON to `--out` |

The installed config starts the server with:

```bash
omf mcp serve
```

If an `oh-my-field` server already exists, install skips it unless
`--overwrite` is set. Existing config files are backed up before modification.
Use `--dry-run` to inspect the same action plan without writing files or
backups. Use `--server-command` when the agent runtime needs an absolute path to
the `omf` executable. Pi users must install `pi-mcp-adapter` first with
`pi install npm:pi-mcp-adapter`. Odysseus users should post the generated
payload to `/api/mcp/servers` as an admin or add the same stdio server in
Settings > MCP.

Initial tool surface:

| Tool | Purpose |
| --- | --- |
| `omf_start_session` | Start tracking the current agent task. |
| `omf_record_input` | Record required input context for strict portable evidence. |
| `omf_record_artifact` | Record a produced artifact path for contract snapshotting. |
| `omf_record_validation` | Record a validation result, command, and optional artifact path. |
| `omf_record_decision` | Record a reusable-workflow or portability decision. |
| `omf_record_event` | Append a generic context, command, diff, test, artifact, or feedback event. |
| `omf_finish_session` | Mark the session outcome. |
| `omf_materialize_session` | Convert a session into immutable evidence. |
| `omf_promote_capability` | Promote evidence into a capability package; strict is true by default. |
| `omf_export_capability` | Export a capability to Codex, Claude Code, Hermes, Pi, Odysseus, or generic assets. |
| `omf_health` | Read capability health and next action. |

Prefer `omf_record_input`, `omf_record_artifact`, `omf_record_validation`, and
`omf_record_decision` over the generic event tool whenever the agent knows the
role of the data. Those structured calls give `session materialize`, `promote`,
and `export` enough information to infer task, artifact, validation, and replay
contracts.

OMF keeps its safety boundary explicit: the MCP server records and packages
agent work, but it does not sniff terminal output or run arbitrary risky
commands on behalf of an agent.
