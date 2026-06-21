# portfolio_backtest

## Purpose

Produce a portfolio backtest report from a small investment-committee case. These
instructions were distilled from a successful Codex `gpt-5.5` run so a smaller
Codex model can reproduce the same calculation.

## Goal

Read the user's backtest case from `input.md` and write the completed report to
`output/backtest_report.md`.

## Output format

- Write Markdown only.
- Write the report file at `output/backtest_report.md`.
- Use this exact section structure:
  - `# Portfolio Backtest Report`
  - `## Summary`
  - `## Monthly Results`
  - `## Notes`

## Backtest rules

- Starting value is USD 1,000,000.00.
- Target allocation is 60.00% US Equity, 30.00% Core Bonds, 10.00% Gold.
- Rebalance only on 2026-01-01 and 2026-04-01.
- Do not charge transaction cost on the initial 2026-01-01 allocation.
- On 2026-04-01, rebalance the drifted March-end positions back to 60/30/10.
- Trading cost is 10 bps of traded notional, where traded notional is the sum of
  absolute dollar trades across the three assets.
- Deduct the 2026-04 rebalance cost before applying April returns.
- After deducting the cost, positions should be at target weights before April
  returns are applied.
- Do not rebalance in February, March, May, or June.

## Metric rules

- Monthly net return is `(ending_value / prior_month_ending_value) - 1`, including
  any rebalance cost in that month's change.
- Drawdown uses month-end values versus the month-end high-water mark, with the
  starting USD 1,000,000.00 value as the initial high-water mark.
- Total return is ending value divided by starting value minus one.
- Annualized return for this six-month test is `(1 + total_return) ** 2 - 1`.
- Annualized volatility is sample standard deviation of monthly net returns times
  `sqrt(12)`.
- Sharpe ratio uses zero risk-free rate: annualized arithmetic mean monthly
  return divided by annualized volatility.
- Round dollars to 2 decimals, percentages to 2 decimals, and Sharpe to 2
  decimals.

## Expected calculation anchors

Use these anchors to catch mistakes:

- 2026-04 traded notional before cost is USD 5,775.42.
- 2026-04 rebalance cost is USD 5.78.
- Ending value is USD 1,018,749.79.
- Total return is 1.87%.
- Annualized return is 3.79%.
- Annualized volatility is 7.58%.
- Sharpe ratio is 0.52.
- Max drawdown is -3.14%.

## Completion gate

Run the harness checks (`harness.yaml`) and the contract (`contracts/`) before
declaring done. Do not emit mock, placeholder, or canned data; derive the report
from `input.md` and the rules above.
