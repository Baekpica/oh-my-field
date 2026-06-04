from oh_my_field.adapters.runtime_export.base import (
    RuntimeExportRequest,
    RuntimeExportSummary,
)
from oh_my_field.application.portability.rendering import (
    base_instructions,
    claude_memory,
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
        write_text_exclusive(
            runtime_path / "CLAUDE.md", claude_memory(request.manifest)
        )
        write_text_exclusive(
            runtime_path / "capability.md",
            base_instructions(request.manifest),
        )
        write_text_exclusive(
            runtime_path / "examples.md",
            examples_markdown(request.manifest),
        )
        write_text_exclusive(
            runtime_path / "checks.md",
            harness_markdown(request.manifest),
        )
        return RuntimeExportSummary(
            runtime_path=str(runtime_path),
            target_runtime=self.target,
        )
