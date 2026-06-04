# OMF MCP

OMF exposes a minimal stdio MCP surface for agents that support structured tool
calls. The MCP server is not a shell wrapper around the CLI. Each tool calls the
same application workflows used by the CLI and returns JSON-serializable
summary models.

Install a generic client config:

```bash
omf install mcp --client generic --out .omf/mcp.json
```

The generated config starts the server with:

```bash
omf mcp serve
```

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
