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
  --command "printf 'smoke ok\n'" \
  --command-output tests/fixtures/output.txt \
  --test-result tests/fixtures/pytest.txt \
  --runtime-tool shell \
  --outcome success \
  --evidence-dir /private/tmp/omf-evidence-smoke

uv run omf promote <evidence_id> \
  --name repo_issue_triage \
  --description "GitHub issue triage capability" \
  --evidence-dir /private/tmp/omf-evidence-smoke \
  --capabilities-dir /private/tmp/omf-capabilities-smoke

uv run omf replay repo_issue_triage \
  --execute \
  --evidence-dir /private/tmp/omf-evidence-smoke \
  --capabilities-dir /private/tmp/omf-capabilities-smoke \
  --replay-dir /private/tmp/omf-replays-smoke

uv run omf context repo_issue_triage \
  --include-optional \
  --query "triage" \
  --max-chars 4000 \
  --evidence-dir /private/tmp/omf-evidence-smoke \
  --capabilities-dir /private/tmp/omf-capabilities-smoke \
  --context-dir /private/tmp/omf-context-smoke

uv run omf eval repo_issue_triage \
  --replay-id <replay_id> \
  --harness-command "printf 'harness ok\n'" \
  --checklist-pass "schema includes reviewer" \
  --rubric-score "clarity:4:5:3:clear enough" \
  --evidence-dir /private/tmp/omf-evidence-smoke \
  --capabilities-dir /private/tmp/omf-capabilities-smoke \
  --replay-dir /private/tmp/omf-replays-smoke \
  --eval-dir /private/tmp/omf-evals-smoke

uv run omf approve capability repo_issue_triage \
  --reviewer operator \
  --note "meets field criteria" \
  --review-dir /private/tmp/omf-reviews-smoke

uv run omf revise evidence <evidence_id> \
  --revision "add a regression harness for the observed failure" \
  --review-dir /private/tmp/omf-reviews-smoke

uv run omf reject replay <replay_id> \
  --note "runtime behavior diverged" \
  --review-dir /private/tmp/omf-reviews-smoke

uv run omf review evidence <evidence_id> add_context \
  --added-context "prefer small diffs" \
  --review-dir /private/tmp/omf-reviews-smoke

uv run omf review replay <replay_id> mark_unsafe \
  --note "destructive command attempted" \
  --review-dir /private/tmp/omf-reviews-smoke

uv run omf review evidence <evidence_id> create_regression_case \
  --regression-case "parser should reject empty branch" \
  --review-dir /private/tmp/omf-reviews-smoke

uv run omf learn repo_issue_triage \
  --evidence-dir /private/tmp/omf-evidence-smoke \
  --capabilities-dir /private/tmp/omf-capabilities-smoke \
  --learning-dir /private/tmp/omf-learning-smoke

uv run omf registry repo_issue_triage \
  --capabilities-dir /private/tmp/omf-capabilities-smoke \
  --eval-dir /private/tmp/omf-evals-smoke

uv run omf reflect repo_issue_triage \
  --eval-id <eval_id> \
  --note "operator saw repeated issue" \
  --evidence-dir /private/tmp/omf-evidence-smoke \
  --capabilities-dir /private/tmp/omf-capabilities-smoke \
  --eval-dir /private/tmp/omf-evals-smoke \
  --reflection-dir /private/tmp/omf-reflections-smoke

uv run omf run \
  --goal "triage repo issue" \
  --name repo_issue_triage_v2 \
  --description "GitHub issue triage capability" \
  --prompt tests/fixtures/prompt.md \
  --command "printf 'orchestrated smoke ok\n'" \
  --harness-command "printf 'harness ok\n'" \
  --checklist-pass "operator rubric attached" \
  --rubric-score "quality:4:5:3:usable" \
  --runtime-tool shell \
  --evidence-dir /private/tmp/omf-run-evidence-smoke \
  --capabilities-dir /private/tmp/omf-run-capabilities-smoke \
  --replay-dir /private/tmp/omf-run-replays-smoke \
  --eval-dir /private/tmp/omf-run-evals-smoke \
  --context-dir /private/tmp/omf-run-context-smoke \
  --learning-dir /private/tmp/omf-run-learning-smoke \
  --workflow-dir /private/tmp/omf-run-workflows-smoke

uv run omf status <run_id> \
  --workflow-dir /private/tmp/omf-run-workflows-smoke

uv run omf resume <run_id> \
  --workflow-dir /private/tmp/omf-run-workflows-smoke
```
