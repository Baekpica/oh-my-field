import yaml

from oh_my_field.adapters.runtime_export.base import (
    RuntimeExportRequest,
    RuntimeExportSummary,
)
from oh_my_field.application.portability.rendering import skill_markdown, yaml_dump
from oh_my_field.domain.portability.models import ExportTarget
from oh_my_field.infrastructure.portability.bundle_store import write_text_exclusive


class GenericRuntimeExportAdapter:
    target: ExportTarget = "generic"

    def export_capability(
        self,
        request: RuntimeExportRequest,
    ) -> RuntimeExportSummary:
        runtime_path = request.bundle_path / "runtime" / self.target
        write_text_exclusive(
            runtime_path / "skill.md",
            skill_markdown(request.manifest),
        )
        write_text_exclusive(
            runtime_path / "context.policy.yaml",
            yaml_dump(request.manifest.context),
        )
        write_text_exclusive(
            runtime_path / "harness.yaml",
            yaml_dump(request.manifest.harness),
        )
        write_text_exclusive(
            runtime_path / "eval_set.yaml",
            yaml.safe_dump(
                {
                    "name": f"{request.manifest.name}_regression",
                    "capability_name": request.manifest.name,
                    "cases": [],
                },
                sort_keys=False,
            ),
        )
        return RuntimeExportSummary(
            runtime_path=str(runtime_path),
            target_runtime=self.target,
        )
