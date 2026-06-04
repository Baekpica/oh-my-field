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

## Agent Activation

Install the CLI first, then install the agent-facing surfaces:

```bash
omf install skill --runtime codex
omf install mcp --client generic --out .omf/mcp.json
```

In an agent session, activate OMF with:

```text
/omf
track this task with OMF
```

## Development Install

```bash
git clone https://github.com/Baekpica/oh-my-field.git
cd oh-my-field
uv sync --all-extras --dev
uv run omf --help
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
