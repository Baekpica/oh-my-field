# Validation Contract

## Completion Gate
- Do not mark the capability complete until every required check passes.
- Do not create mock, sample, placeholder, or canned output artifacts.
- Generated artifacts must come from the recorded inputs and task contract.
- Treat any contract mismatch as a failed runtime import.

## Required Checks
- agent_log_imported
- artifacts_readable
- artifact_exists:opus_run.log
- artifact_exists:validation.txt
- artifact_exists:output/normalized.json
- json_parses:output/normalized.json
- schema_valid

## Expected Artifacts
- opus_run.log
- validation.txt
- output/normalized.json

## Validator
- Run `python /path/to/package/validators/validate_contract.py` from the target artifact root when available.
- If the target runtime cannot run Python, manually apply the same contract checks.
