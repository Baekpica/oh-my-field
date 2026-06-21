# Validation Contract

## Completion Gate

- Do not mark the capability complete until every required check passes.
- Do not create mock, sample, placeholder, or canned output artifacts.
- Generated artifacts must come from `input.md` and the task contract.
- Treat any contract mismatch as a failed runtime import.

## Required Checks

- artifact_exists:output/backtest_report.md
- markdown_contains:portfolio_backtest_results
- values_match:expected_backtest_report

## Expected Artifacts

- output/backtest_report.md

A fresh target run reads `input.md` and produces only
`output/backtest_report.md`. The seed run log and validation transcript are
provenance recorded in `capability.yaml`; they are not target inputs or target
artifacts.

## Validator

- Run `python /path/to/package/validators/validate_contract.py` from the target
  artifact root when available.
- It enforces the required Markdown result lines and the exact calculated
  metrics, including the reporting period, strategy line, and 2026-04
  transaction cost.
- If the target runtime cannot run Python, manually apply the same checks.
