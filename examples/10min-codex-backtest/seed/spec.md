# Seed Run Spec

Use Codex with `gpt-5.5` to solve the portfolio backtest case in
`task/backtest_case.md`.

The reusable capability should teach a smaller Codex model to:

- apply rebalance timing exactly,
- charge transaction costs only on traded notional,
- deduct the cost before applying returns,
- calculate monthly net returns from portfolio value changes,
- calculate max drawdown from month-end high-water marks,
- annualize return and sample volatility consistently,
- write the final answer as a Markdown investment committee report.
