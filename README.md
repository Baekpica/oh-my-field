# oh-my-field
Field-fit agents to real work. Turn tacit know-how into reusable capabilities.

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
uv run pyright
```

## CLI

```bash
omf capture --goal "triage repo issue" --prompt prompt.md
omf promote <evidence_id> --name repo_issue_triage --description "GitHub issue triage capability"
```
