# Validation Contract

## Completion Gate
- Do not mark the capability complete until every required check passes.
- Do not create mock, sample, placeholder, or canned output artifacts.
- Generated artifacts must come from the recorded inputs and task contract.
- Treat any contract mismatch as a failed runtime import.

## Required Checks (fresh target run)
- artifact_exists:output/normalized.json
- json_parses:output/normalized.json
- schema_valid:output/normalized.json

## Expected Artifacts
- output/normalized.json

A fresh run of this capability reads `input.csv` and produces only
`output/normalized.json`. The Opus source-evidence files (`opus_run.log`,
`validation.txt`) are provenance recorded in `capability.yaml`; they are **not**
artifacts a target run is expected to reproduce.

## Validator
- Run `python /path/to/package/validators/validate_contract.py` from the target artifact root when available. It enforces existence, valid JSON, and the record schema/types — not just file presence.
- If the target runtime cannot run Python, manually apply the same contract checks.
