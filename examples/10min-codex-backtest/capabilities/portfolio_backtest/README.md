# portfolio_backtest

## Purpose

Produce a deterministic portfolio backtest report from a small investment
committee case. The capability captures the calculation details that smaller
models often miss: rebalance timing, transaction-cost treatment, drawdown
calculation, and annualized risk metrics.

## Source Evidence

- Runtime: Codex
- Source model: `gpt-5.5`
- Target model for the demo: `gpt-5.4-mini`
- Source evidence id: see `capability.yaml`

## Harness

- Required input: `input.md`
- Expected artifact: `output/backtest_report.md`
- Required checks:
  - `artifact_exists:output/backtest_report.md`
  - `markdown_contains:portfolio_backtest_results`
  - `values_match:expected_backtest_report`
