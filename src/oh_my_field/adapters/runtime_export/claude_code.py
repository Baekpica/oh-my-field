from oh_my_field.adapters.runtime_export.base import (
    RuntimeExportRequest,
    RuntimeExportSummary,
    write_contract_reference_files,
)
from oh_my_field.application.portability.rendering import (
    agent_skill_markdown,
    base_instructions,
    examples_markdown,
    harness_markdown,
)
from oh_my_field.domain.portability.models import ExportTarget
from oh_my_field.infrastructure.portability.bundle_store import write_text_exclusive


class ClaudeCodeRuntimeExportAdapter:
    target: ExportTarget = "claude_code"

    def export_capability(
        self,
        request: RuntimeExportRequest,
    ) -> RuntimeExportSummary:
        runtime_path = request.bundle_path / "runtime" / self.target
        skill_path = (
            runtime_path / ".claude" / "skills" / request.manifest.name / "SKILL.md"
        )
        reference_path = skill_path.parent / "references"
        write_text_exclusive(
            skill_path,
            agent_skill_markdown(request.manifest),
        )
        write_text_exclusive(
            reference_path / "capability.md",
            base_instructions(request.manifest),
        )
        write_text_exclusive(
            reference_path / "examples.md",
            examples_markdown(request.manifest),
        )
        write_text_exclusive(
            reference_path / "checks.md",
            harness_markdown(request.manifest),
        )
        write_contract_reference_files(reference_path, request.manifest)
        return RuntimeExportSummary(
            runtime_path=str(runtime_path),
            target_runtime=self.target,
        )
