from oh_my_field.adapters.runtime_export.base import (
    RuntimeExportRequest,
    RuntimeExportSummary,
)
from oh_my_field.application.portability.rendering import (
    base_instructions,
    context_markdown,
    harness_markdown,
    odysseus_skill_markdown,
)
from oh_my_field.domain.portability.models import ExportTarget
from oh_my_field.infrastructure.portability.bundle_store import write_text_exclusive


class OdysseusRuntimeExportAdapter:
    target: ExportTarget = "odysseus"

    def export_capability(
        self,
        request: RuntimeExportRequest,
    ) -> RuntimeExportSummary:
        runtime_path = request.bundle_path / "runtime" / self.target
        skill_dir = runtime_path / "data" / "skills" / "omf" / request.manifest.name
        reference_path = skill_dir / "references"
        write_text_exclusive(
            skill_dir / "SKILL.md",
            odysseus_skill_markdown(request.manifest),
        )
        write_text_exclusive(
            reference_path / "capability.md",
            base_instructions(request.manifest),
        )
        write_text_exclusive(
            reference_path / "context.policy.md",
            context_markdown(request.manifest),
        )
        write_text_exclusive(
            reference_path / "harness.md",
            harness_markdown(request.manifest),
        )
        return RuntimeExportSummary(
            runtime_path=str(runtime_path),
            target_runtime=self.target,
        )
