# Portfolio Backtest Case

You are reviewing a six-month model portfolio backtest for an investment
committee packet.

## Mandate

- Starting value: USD 1,000,000.00 on 2026-01-01.
- Target allocation: 60.00% US Equity, 30.00% Core Bonds, 10.00% Gold.
- Rebalance on 2026-01-01 and 2026-04-01 only.
- Initial allocation on 2026-01-01 has no transaction cost.
- Later rebalances charge 10 bps of traded notional.
- Deduct transaction cost before applying that month's returns.
- After deducting rebalance cost, set positions back to target weights.
- Use zero risk-free rate for Sharpe.

## Monthly Total Returns

| Month | US Equity | Core Bonds | Gold |
|-------|-----------|------------|------|
| 2026-01 | -4.00% | 0.80% | 5.00% |
| 2026-02 | 2.50% | -0.20% | 1.50% |
| 2026-03 | 3.00% | 0.40% | -2.00% |
| 2026-04 | -6.50% | 1.20% | 4.00% |
| 2026-05 | 4.00% | 0.10% | -1.00% |
| 2026-06 | 1.50% | 0.50% | 2.50% |

## Required Output

Write a Markdown report to `output/backtest_report.md`.

The report must include:

- starting value,
- ending value,
- total return,
- annualized return,
- annualized volatility,
- Sharpe ratio,
- max drawdown,
- total transaction costs,
- best and worst month,
- a monthly table with month, net return, ending value, drawdown, and rebalance
  cost.
