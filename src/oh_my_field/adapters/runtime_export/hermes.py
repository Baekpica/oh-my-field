import yaml

from oh_my_field.adapters.runtime_export.base import (
    RuntimeExportRequest,
    RuntimeExportSummary,
)
from oh_my_field.application.portability.rendering import (
    harness_markdown,
    runtime_memory,
    skill_markdown,
)
from oh_my_field.domain.portability.models import ExportTarget
from oh_my_field.infrastructure.portability.bundle_store import write_text_exclusive


class HermesRuntimeExportAdapter:
    target: ExportTarget = "hermes"

    def export_capability(
        self,
        request: RuntimeExportRequest,
    ) -> RuntimeExportSummary:
        runtime_path = request.bundle_path / "runtime" / self.target
        write_text_exclusive(runtime_path / "SOUL.md", runtime_memory(request.manifest))
        write_text_exclusive(
            runtime_path / "skills" / f"{request.manifest.name}.md",
            skill_markdown(request.manifest),
        )
        write_text_exclusive(
            runtime_path / "harness.md",
            harness_markdown(request.manifest),
        )
        write_text_exclusive(
            runtime_path / "profile.patch.yaml",
            yaml.safe_dump(
                {
                    "skills": [f"skills/{request.manifest.name}.md"],
                    "harness": "harness.md",
                },
                sort_keys=False,
            ),
        )
        return RuntimeExportSummary(
            runtime_path=str(runtime_path),
            target_runtime=self.target,
        )
