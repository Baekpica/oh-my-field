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
uv run omf capture \
  --goal "triage repo issue" \
  --prompt tests/fixtures/prompt.md \
  --command-output tests/fixtures/output.txt \
  --test-result tests/fixtures/pytest.txt \
  --evidence-dir /private/tmp/omf-evidence-smoke

uv run omf promote <evidence_id> \
  --name repo_issue_triage \
  --description "GitHub issue triage capability" \
  --evidence-dir /private/tmp/omf-evidence-smoke \
  --capabilities-dir /private/tmp/omf-capabilities-smoke

uv run omf replay repo_issue_triage \
  --evidence-dir /private/tmp/omf-evidence-smoke \
  --capabilities-dir /private/tmp/omf-capabilities-smoke \
  --replay-dir /private/tmp/omf-replays-smoke

uv run omf eval repo_issue_triage \
  --replay-id <replay_id> \
  --evidence-dir /private/tmp/omf-evidence-smoke \
  --capabilities-dir /private/tmp/omf-capabilities-smoke \
  --replay-dir /private/tmp/omf-replays-smoke \
  --eval-dir /private/tmp/omf-evals-smoke
```
