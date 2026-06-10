import yaml

from oh_my_field.domain.models import CapabilityManifest

TASK_CONTRACT_SCHEMA_VERSION = "omf.task_contract.v0.1"
ARTIFACT_CONTRACT_SCHEMA_VERSION = "omf.artifact_contracts.v0.1"
REPLAY_PLAN_SCHEMA_VERSION = "omf.replay_plan.v0.1"


def task_contract_yaml(manifest: CapabilityManifest) -> str:
    contract = manifest.task_contract
    data: dict[str, object]
    if contract is None:
        data = {
            "goal": manifest.normalized_goal,
            "required_inputs": list(manifest.context.required),
            "expected_artifacts": [
                artifact.artifact_path for artifact in manifest.artifact_contracts
            ],
            "validation_checks": list(manifest.harness.required_checks),
            "mock_outputs_allowed": False,
        }
    else:
        data = contract.model_dump(mode="json")
    payload = {"schema_version": TASK_CONTRACT_SCHEMA_VERSION, **data}
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)


def artifact_contracts_yaml(manifest: CapabilityManifest) -> str:
    payload = {
        "schema_version": ARTIFACT_CONTRACT_SCHEMA_VERSION,
        "capability": manifest.name,
        "artifacts": [
            contract.model_dump(mode="json") for contract in manifest.artifact_contracts
        ],
    }
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)


def validation_markdown(manifest: CapabilityManifest) -> str:
    checks = manifest.harness.required_checks
    artifact_paths = tuple(
        contract.artifact_path for contract in manifest.artifact_contracts
    )
    lines = [
        "# Validation Contract",
        "",
        "## Completion Gate",
        "- Do not mark the capability complete until every required check passes.",
        "- Do not create mock, sample, placeholder, or canned output artifacts.",
        "- Generated artifacts must come from the recorded inputs and task contract.",
        "- Treat any contract mismatch as a failed runtime import.",
        "",
        "## Required Checks",
        _bullets(checks, "No required checks recorded."),
        "",
        "## Expected Artifacts",
        _bullets(artifact_paths, "No expected artifacts recorded."),
        "",
        "## Validator",
        "- Run `python validators/validate_contract.py` from the package root "
        "when available.",
        "- If the target runtime cannot run Python, manually apply the same "
        "contract checks.",
        "",
    ]
    return "\n".join(lines)


def replay_plan_yaml(manifest: CapabilityManifest) -> str:
    payload = {
        "schema_version": REPLAY_PLAN_SCHEMA_VERSION,
        "capability": manifest.name,
        "goal": manifest.normalized_goal,
        "steps": [
            "load_required_context",
            "apply_task_contract",
            "produce_expected_artifacts",
            "run_validation_contract",
            "record_target_failures_as_evidence",
        ],
        "required_inputs": list(manifest.context.required),
        "expected_artifacts": [
            contract.artifact_path for contract in manifest.artifact_contracts
        ],
        "validation_checks": list(manifest.harness.required_checks),
    }
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)


def validator_script(manifest: CapabilityManifest) -> str:
    artifact_paths = [
        contract.artifact_path for contract in manifest.artifact_contracts
    ]
    return f"""#!/usr/bin/env python3
import sys
from pathlib import Path

EXPECTED_ARTIFACTS = {artifact_paths!r}


def main() -> int:
    missing = [path for path in EXPECTED_ARTIFACTS if not Path(path).exists()]
    if missing:
        for path in missing:
            print(f"missing artifact: {{path}}", file=sys.stderr)
        return 1
    print("contract validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


def _bullets(values: tuple[str, ...], empty: str) -> str:
    if not values:
        return f"- {empty}"
    return "\n".join(f"- {value}" for value in values)
