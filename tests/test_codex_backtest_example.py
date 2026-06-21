"""Regression checks for the Codex portfolio backtest example."""

from __future__ import annotations

import importlib.util
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
