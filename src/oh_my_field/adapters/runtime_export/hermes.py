from oh_my_field.adapters.runtime_export.base import (
    RuntimeExportRequest,
    RuntimeExportSummary,
)
from oh_my_field.application.portability.rendering import (
    agent_skill_markdown,
    harness_markdown,
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
        skill_dir = runtime_path / "skills" / request.manifest.name
        write_text_exclusive(
            skill_dir / "SKILL.md",
            agent_skill_markdown(request.manifest),
        )
        write_text_exclusive(
            skill_dir / "references" / "harness.md",
            harness_markdown(request.manifest),
        )
        return RuntimeExportSummary(
            runtime_path=str(runtime_path),
            target_runtime=self.target,
        )
