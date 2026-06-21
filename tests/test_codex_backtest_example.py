"""Regression checks for the Codex portfolio backtest example."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "10min-codex-backtest"


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_portfolio_backtest_validator_covers_checker_required_lines() -> None:
    checker = _load_module("codex_backtest_check", EXAMPLE / "check.py")
    validator = _load_module(
        "portfolio_backtest_validator",
        EXAMPLE
        / "capabilities"
        / "portfolio_backtest"
        / "validators"
        / "validate_contract.py",
    )

    missing = sorted(set(checker.REQUIRED_LINES) - set(validator.REQUIRED_LINES))

    assert missing == []


def test_portfolio_backtest_checker_rejects_conflicting_summary_value() -> None:
    checker = _load_module("codex_backtest_check", EXAMPLE / "check.py")
    produced = (
        checker.GOLDEN.read_text(encoding="utf-8") + "\n- Ending value: $999,999.99\n"
    )

    assert (
        "conflicting summary line for Ending value: - Ending value: $999,999.99"
        in checker._contract_violations(produced)
    )


def test_portfolio_backtest_checker_rejects_duplicate_monthly_row() -> None:
    checker = _load_module("codex_backtest_check", EXAMPLE / "check.py")
    produced = (
        checker.GOLDEN.read_text(encoding="utf-8")
        + "\n| 2026-04 | -3.14% | $983,663.77 | -3.14% | $5.78 |\n"
    )

    assert "duplicate monthly row for 2026-04" in checker._contract_violations(produced)


def test_portfolio_backtest_validator_rejects_conflicting_rows(tmp_path: Path) -> None:
    checker = _load_module("codex_backtest_check", EXAMPLE / "check.py")
    validator = _load_module(
        "portfolio_backtest_validator",
        EXAMPLE
        / "capabilities"
        / "portfolio_backtest"
        / "validators"
        / "validate_contract.py",
    )
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "backtest_report.md").write_text(
        checker.GOLDEN.read_text(encoding="utf-8")
        + "\n| 2026-04 | 0.00% | $1.00 | 0.00% | $0.00 |\n",
        encoding="utf-8",
    )
    cwd = Path.cwd()
    try:
        os.chdir(tmp_path)
        assert validator.main() == 1
    finally:
        os.chdir(cwd)
