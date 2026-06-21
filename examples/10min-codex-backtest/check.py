#!/usr/bin/env python3
"""Objective pass/fail for the Codex portfolio backtest happy path."""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOLDEN = HERE / "expected" / "backtest_report.md"

REQUIRED_LINES = (
    "# Portfolio Backtest Report",
    "- Period: 2026-01 through 2026-06",
    "- Strategy: 60.00% US Equity / 30.00% Core Bonds / 10.00% Gold",
    "- Starting value: $1,000,000.00",
    "- Ending value: $1,018,749.79",
    "- Total return: 1.87%",
    "- Annualized return: 3.79%",
    "- Annualized volatility: 7.58%",
    "- Sharpe ratio: 0.52",
    "- Max drawdown: -3.14%",
    "- Total transaction costs: $5.78",
    "- Best month: 2026-05 (2.24%)",
    "- Worst month: 2026-04 (-3.14%)",
    "| 2026-01 | -1.66% | $983,400.00 | -1.66% | $0.00 |",
    "| 2026-02 | 1.56% | $998,770.20 | -0.12% | $0.00 |",
    "| 2026-03 | 1.68% | $1,015,557.88 | 0.00% | $0.00 |",
    "| 2026-04 | -3.14% | $983,663.77 | -3.14% | $5.78 |",
    "| 2026-05 | 2.24% | $1,005,704.91 | -0.97% | $0.00 |",
    "| 2026-06 | 1.30% | $1,018,749.79 | 0.00% | $0.00 |",
)


def _normalize(text: str) -> str:
    text = text.strip()
    fence = re.search(r"```(?:markdown|md)?\s*\n(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    lines = [" ".join(line.strip().split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _missing_lines(produced: str) -> list[str]:
    normalized = _normalize(produced)
    return [line for line in REQUIRED_LINES if line not in normalized]


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python check.py <produced-report.md>", file=sys.stderr)
        return 1
    produced_path = Path(argv[1])
    try:
        produced = produced_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"FAIL: produced file not found: {produced_path}", file=sys.stderr)
        return 1
    missing = _missing_lines(produced)
    if missing:
        print(
            "FAIL: report is missing required backtest result line(s):", file=sys.stderr
        )
        for line in missing:
            print(f"  - {line}", file=sys.stderr)
        return 1
    try:
        golden_missing = _missing_lines(GOLDEN.read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"FAIL: cannot read golden {GOLDEN}: {exc}", file=sys.stderr)
        return 1
    if golden_missing:
        print(f"FAIL: golden report is incomplete: {golden_missing}", file=sys.stderr)
        return 1
    print("PASS: report contains the required portfolio backtest results")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
