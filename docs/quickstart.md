# Quickstart

## 10-Minute Examples

First time here? Run the thinnest successful OMF loop first:

```bash
bash examples/10min-happy-path/run.sh
```

The Claude example shows a task a bare Haiku gets wrong becoming reproducible
once Haiku is handed an OMF capability distilled from an Opus run. See
[examples/10min-happy-path/](../examples/10min-happy-path/README.md).

For a finance-focused Codex variant, run:

```bash
bash examples/10min-codex-backtest/run.sh
```

The Codex example carries a `gpt-5.5` portfolio backtest capability to
`gpt-5.4-mini` and validates rebalance-cost, drawdown, volatility, and Sharpe
metrics with a Markdown contract checker. See
[examples/10min-codex-backtest/](../examples/10min-codex-backtest/README.md).

OMF has three entry paths. Path A is the intended agent-assisted loop; Path B is
the fallback when you only have run artifacts after the fact; Path C moves a
capability to another runtime.

From a source checkout, prefix each command with `uv run`.

Set up the repo-local field once:

```bash
omf init
```

This writes `.omf/config.yaml`, `.omfignore`, the top-level `capabilities/`
library, and the artifact directories (`.omf/evidence`, `.omf/sessions`,
`.omf/exports`, …). Capability packages under `capabilities/<name>/` are the
reviewable source of truth; `.omf/registry.yaml` is local registry metadata.

## Path A: Agent-Assisted Session Tracking

Use this when an agent can call OMF *during* the work. Optionally install the
meta-skill first so the agent knows when and how to call OMF:

```bash
omf install skill --runtime codex
```

Start a session, record meaningful events, then finish it:

```bash
omf session start \
  --runtime codex \
  --model gpt-5.5 \
  --goal "triage repository issue" \
  --activation-source skill
```

Create a tiny input, output artifact, and validation result for the example:

```bash
mkdir -p output
printf "issue: repository bug report\n" > issue.md
printf '{"status":"triaged"}\n' > output/report.json
printf "pytest passed\n" > output/pytest.txt
```

Copy the `session_id` from the JSON output and record the task context,
commands, produced artifact, and validation result:

```bash
omf session event <session_id> \
  --type context \
  --summary "Captured issue report" \
  --path issue.md

omf session event <session_id> \
  --type command \
  --summary "Ran the test suite" \
  --command "uv run pytest" \
  --exit-code 0

omf session event <session_id> \
  --type artifact \
  --summary "Produced triage report" \
  --path output/report.json

omf session event <session_id> \
  --type test_result \
  --summary "pytest passed" \
  --path output/pytest.txt \
  --command "uv run pytest" \
  --exit-code 0

omf session finish <session_id> --outcome success
```

Event `--type` accepts `goal`, `assumption`, `context`, `command`, `diff`,
`test_result`, `artifact`, `user_feedback`, `decision`, and `completion`.
`promote` is strict by default, so reusable successful runs should include at
least one required context path, produced artifact path, and validation result.

Materialize the session into immutable evidence and (optionally) ask OMF to
suggest a capability name:

```bash
omf session materialize <session_id>
omf session suggest-capability <session_id>
```

Promote the resulting evidence into a capability and check its health. Use
`--no-strict` only for intentional legacy or incomplete evidence promotion:

```bash
omf promote <evidence_id> \
  --name repo_issue_triage \
  --description "Repository issue triage capability"

omf health repo_issue_triage
```

## Path B: Import An Existing Run

Use this when the agent already produced logs, diffs, test outputs, or artifacts.

```bash
mkdir -p /tmp/omf-smoke
printf "agent run log\n" > /tmp/omf-smoke/codex.log
printf "pytest passed\n" > /tmp/omf-smoke/pytest.txt

omf import-run codex \
  --log /tmp/omf-smoke/codex.log \
  --goal "triage repo issue" \
  --test-result /tmp/omf-smoke/pytest.txt \
  --evidence-dir /tmp/omf-smoke/evidence \
  --outcome success
```

Copy the `evidence_id` from the JSON output. Imported runs are hardened into
the same canonical record shape before promotion:

```bash
omf promote <evidence_id> \
  --name repo_issue_triage \
  --description "Repository issue triage capability" \
  --evidence-dir /tmp/omf-smoke/evidence \
  --capabilities-dir /tmp/omf-smoke/capabilities

omf health repo_issue_triage \
  --capabilities-dir /tmp/omf-smoke/capabilities
```

## Path C: Export, Import, And Validate A Capability

Use this to move a capability to another runtime or project. The three states
are distinct: exported ≠ imported ≠ validated (see
[portability.md](portability.md)).

```bash
# Export the canonical capability package and target runtime projection.
omf capability export repo_issue_triage \
  --target hermes \
  --out .omf/exports/repo_issue_triage-hermes

# Verify the archive manifest before handing it to another runtime.
omf verify package .omf/exports/repo_issue_triage-hermes.omfcap.tar.gz

# Import the package into a target project (static --validate check).
omf capability import .omf/exports/repo_issue_triage-hermes.omfcap.tar.gz \
  --runtime hermes \
  --validate

# Validate with a real target run; OMF gates the command behind
# --approve-command-risk and folds hard blockers into the target eval.
omf capability validate repo_issue_triage \
  --target hermes \
  --run-command "hermes-code --profile target --skill repo_issue_triage" \
  --approve-command-risk
```

Without `--run-command`, `validate` records a manual-run plan and the expected
artifacts to bring back via `import-run`; the import stays at
`needs_validation` until a real target run passes. With a target run, missing
expected artifacts or failed opt-in `--run-contract-validator` checks are hard
blockers; runtime/model/project transfer risk is advisory.
