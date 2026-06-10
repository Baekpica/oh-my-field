from pathlib import Path
from typing import Protocol

from oh_my_field.contract_rendering import (
    artifact_contracts_yaml,
    replay_plan_yaml,
    task_contract_yaml,
    validation_markdown,
    validator_script,
)
from oh_my_field.domain.models import CapabilityManifest, StrictModel
from oh_my_field.domain.portability.models import ExportTarget, PortabilityManifest
from oh_my_field.infrastructure.portability.bundle_store import write_text_exclusive


class RuntimeExportRequest(StrictModel):
    bundle_path: Path
    manifest: CapabilityManifest
    portability: PortabilityManifest


class RuntimeExportSummary(StrictModel):
    runtime_path: str
    target_runtime: ExportTarget


class RuntimeExportAdapter(Protocol):
    target: ExportTarget

    def export_capability(
        self,
        request: RuntimeExportRequest,
    ) -> RuntimeExportSummary: ...


def write_contract_reference_files(
    reference_path: Path,
    manifest: CapabilityManifest,
) -> None:
    write_text_exclusive(
        reference_path / "task_contract.yaml",
        task_contract_yaml(manifest),
    )
    write_text_exclusive(
        reference_path / "artifacts.yaml",
        artifact_contracts_yaml(manifest),
    )
    write_text_exclusive(
        reference_path / "validation.md",
        validation_markdown(manifest),
    )
    write_text_exclusive(
        reference_path / "replay_plan.yaml",
        replay_plan_yaml(manifest),
    )


def write_contract_bundle_files(
    runtime_path: Path,
    manifest: CapabilityManifest,
) -> None:
    write_text_exclusive(
        runtime_path / "contracts" / "task_contract.yaml",
        task_contract_yaml(manifest),
    )
    write_text_exclusive(
        runtime_path / "contracts" / "artifacts.yaml",
        artifact_contracts_yaml(manifest),
    )
    write_text_exclusive(
        runtime_path / "contracts" / "validation.md",
        validation_markdown(manifest),
    )
    write_text_exclusive(
        runtime_path / "contracts" / "replay_plan.yaml",
        replay_plan_yaml(manifest),
    )
    write_text_exclusive(
        runtime_path / "validators" / "validate_contract.py",
        validator_script(manifest),
    )
