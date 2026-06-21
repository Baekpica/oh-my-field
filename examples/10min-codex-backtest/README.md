# 10-Minute Codex Happy Path: Portfolio Backtest

This demo uses a practical finance task instead of another data-formatting
exercise. A smaller Codex model is asked to prepare a six-month portfolio
backtest report. The bare prompt is easy to get almost right, but the contract
depends on details that are common sources of backtesting errors: rebalance
timing, transaction costs, drawdown high-water marks, annualized volatility, and
Sharpe ratio.

> Same target model. Same input. The only difference is the OMF capability
> distilled from a stronger Codex run.

## The task

Turn [`task/backtest_case.md`](task/backtest_case.md) into a Markdown investment
committee report at `output/backtest_report.md`.

The report must include summary metrics and a month-by-month table for a 60/30/10
portfolio. The key trap is the 2026-04 rebalance: charge 10 bps on traded
notional, deduct the cost before April returns, then calculate the net return and
drawdown from the resulting value path.

## Run it

```bash
# from the repo root; requires uv, python3, and the `codex` CLI (logged in)
bash examples/10min-codex-backtest/run.sh
```

Defaults:

- source model recorded in the seed import: `gpt-5.5`
- target model used for the live runs: `gpt-5.4-mini`

Override them if your Codex installation uses different model ids:

```bash
SOURCE_MODEL=gpt-5.5 TARGET_MODEL=gpt-5.4-mini \
  bash examples/10min-codex-backtest/run.sh
```

You will see three steps:

1. **OMF pipeline** - `omf import-run` the recorded Codex `gpt-5.5` run, then
   `omf promote` it into a capability, then `omf health`.
2. **Bare Codex target model** - runs as an agent with only the task statement.
3. **Codex target model + OMF capability** - same agent setup, but handed the
   distilled backtesting instructions.

The verdict is objective: [`check.py`](check.py) checks the produced Markdown
against the committed golden report
[`expected/backtest_report.md`](expected/backtest_report.md).

## What's in here

| Path | Role |
|------|------|
| `task/backtest_case.md` | the backtest case a user has |
| `seed/` | the recorded Codex `gpt-5.5` run fed to `import-run` |
| `capabilities/portfolio_backtest/` | the promoted + curated capability package |
| `expected/backtest_report.md` | the golden report |
| `check.py` | the objective pass/fail check |
| `run.sh` | the one-command demo |

## Do it yourself

```bash
FIELD="$(pwd)/examples/10min-codex-backtest/.omf-quickstart"

EVIDENCE_ID="$(cd examples/10min-codex-backtest/seed && uv run omf import-run codex \
  --log gpt55_run.txt \
  --goal "produce a portfolio backtest report for the six-month model portfolio case" \
  --model gpt-5.5 \
  --artifact output/backtest_report.md \
  --test-result validation.txt \
  --outcome success \
  --evidence-dir "$FIELD/evidence" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["evidence_id"])')"

uv run omf promote "$EVIDENCE_ID" \
  --name portfolio_backtest \
  --description "Produce a deterministic portfolio backtest report with rebalance costs and risk metrics" \
  --evidence-dir "$FIELD/evidence" \
  --capabilities-dir "$FIELD/capabilities"

DIY_CAP="$FIELD/capabilities/portfolio_backtest"
uv run python examples/10min-codex-backtest/curate_package.py \
  --source examples/10min-codex-backtest/capabilities/portfolio_backtest \
  --target "$DIY_CAP" \
  --evidence "$FIELD/evidence/$EVIDENCE_ID.json"

uv run omf capability export portfolio_backtest \
  --target codex --target-model gpt-5.4-mini \
  --capabilities-dir "$FIELD/capabilities" \
  --evidence-dir "$FIELD/evidence" \
  --out "$FIELD/exports/portfolio_backtest-codex"
```

The curated manifest keeps the fresh target surface narrow: `input.md` is the
only required input and `output/backtest_report.md` is the only expected target
artifact. Seed logs and validation transcripts remain provenance only.
