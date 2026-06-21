#!/usr/bin/env python3
"""Contract validator for the portfolio_backtest capability."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ARTIFACT = Path("output/backtest_report.md")

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
SUMMARY_LINES = {
    line[2:].split(":", 1)[0]: line
    for line in REQUIRED_LINES
    if line.startswith("- ") and ": " in line
}
MONTHLY_ROWS = {
    line.strip("|").split("|", 1)[0].strip(): line
    for line in REQUIRED_LINES
    if line.startswith("| 2026-")
}


def _normalize(text: str) -> str:
    text = text.strip()
    fence = re.search(r"```(?:markdown|md)?\s*\n(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    lines = [" ".join(line.strip().split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _summary_violations(normalized_lines: list[str]) -> list[str]:
    summary_lines: dict[str, list[str]] = {}
    for line in normalized_lines:
        if not line.startswith("- ") or ": " not in line:
            continue
        key = line[2:].split(":", 1)[0]
        if key in SUMMARY_LINES:
            summary_lines.setdefault(key, []).append(line)

    violations: list[str] = []
    for key, expected in SUMMARY_LINES.items():
        lines = summary_lines.get(key, [])
        if len(lines) > 1:
            violations.append(f"duplicate summary line for {key}")
        violations.extend(
            f"conflicting summary line for {key}: {line}"
            for line in lines
            if line != expected
        )
    return violations


def _monthly_violations(normalized_lines: list[str]) -> list[str]:
    monthly_rows: dict[str, list[str]] = {}
    for line in normalized_lines:
        if not line.startswith("| 2026-"):
            continue
        month = line.strip("|").split("|", 1)[0].strip()
        monthly_rows.setdefault(month, []).append(line)

    violations: list[str] = []
    for month, expected in MONTHLY_ROWS.items():
        rows = monthly_rows.get(month, [])
        if len(rows) > 1:
            violations.append(f"duplicate monthly row for {month}")
        violations.extend(
            f"conflicting monthly row for {month}: {row}"
            for row in rows
            if row != expected
        )
    for month, rows in monthly_rows.items():
        if month not in MONTHLY_ROWS:
            violations.extend(
                f"unexpected monthly row for {month}: {row}" for row in rows
            )

    return violations


def _contract_violations(produced: str) -> list[str]:
    normalized_lines = _normalize(produced).splitlines()
    normalized = "\n".join(normalized_lines)
    violations = [
        f"missing line: {line}" for line in REQUIRED_LINES if line not in normalized
    ]
    violations.extend(_summary_violations(normalized_lines))
    violations.extend(_monthly_violations(normalized_lines))
    return violations


def main() -> int:
    if not ARTIFACT.exists():
        print(f"missing artifact: {ARTIFACT}", file=sys.stderr)
        return 1
    violations = _contract_violations(ARTIFACT.read_text(encoding="utf-8"))
    if violations:
        for violation in violations:
            print(f"contract violation: {violation}", file=sys.stderr)
        return 1
    print("contract validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
