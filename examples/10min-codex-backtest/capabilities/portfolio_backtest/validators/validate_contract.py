#!/usr/bin/env python3
"""Contract validator for the portfolio_backtest capability."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ARTIFACT = Path("output/backtest_report.md")

REQUIRED_LINES = (
    "# Portfolio Backtest Report",
    "- Ending value: $1,018,749.79",
    "- Total return: 1.87%",
    "- Annualized return: 3.79%",
    "- Annualized volatility: 7.58%",
    "- Sharpe ratio: 0.52",
    "- Max drawdown: -3.14%",
    "- Total transaction costs: $5.78",
    "- Best month: 2026-05 (2.24%)",
    "- Worst month: 2026-04 (-3.14%)",
    "| 2026-04 | -3.14% | $983,663.77 | -3.14% | $5.78 |",
    "| 2026-06 | 1.30% | $1,018,749.79 | 0.00% | $0.00 |",
)


def _normalize(text: str) -> str:
    text = text.strip()
    fence = re.search(r"```(?:markdown|md)?\s*\n(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    lines = [" ".join(line.strip().split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def main() -> int:
    if not ARTIFACT.exists():
        print(f"missing artifact: {ARTIFACT}", file=sys.stderr)
        return 1
    normalized = _normalize(ARTIFACT.read_text(encoding="utf-8"))
    missing = [line for line in REQUIRED_LINES if line not in normalized]
    if missing:
        for line in missing:
            print(f"contract violation: missing line: {line}", file=sys.stderr)
        return 1
    print("contract validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

