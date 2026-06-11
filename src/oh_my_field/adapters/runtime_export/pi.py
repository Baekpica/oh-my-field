import json

from oh_my_field.adapters.runtime_export.base import (
    RuntimeExportRequest,
    RuntimeExportSummary,
    write_contract_reference_files,
)
from oh_my_field.application.portability.rendering import (
    agent_skill_markdown,
    base_instructions,
    context_markdown,
    harness_markdown,
    launcher_skill_markdown,
)
from oh_my_field.domain.portability.models import ExportTarget
from oh_my_field.infrastructure.portability.bundle_store import write_text_exclusive


class PiRuntimeExportAdapter:
    target: ExportTarget = "pi"

    def export_capability(
        self,
        request: RuntimeExportRequest,
    ) -> RuntimeExportSummary:
        runtime_path = request.bundle_path / "runtime" / self.target
        skill_dir = runtime_path / ".pi" / "skills" / request.manifest.name
        reference_path = skill_dir / "references"
        launcher = request.portability.agent_view.skill_style == "launcher"
        write_text_exclusive(
            skill_dir / "SKILL.md",
            launcher_skill_markdown(request.manifest, target_runtime=self.target)
            if launcher
            else agent_skill_markdown(request.manifest),
        )
        if not launcher:
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
        write_text_exclusive(
            runtime_path / "package.json",
            _package_json(request.manifest.name),
        )
        write_contract_reference_files(reference_path, request.manifest)
        return RuntimeExportSummary(
            runtime_path=str(runtime_path),
            target_runtime=self.target,
        )


def _package_json(capability_name: str) -> str:
    package_name = "omf-" + capability_name.replace("_", "-") + "-pi"
    return (
        json.dumps(
            {
                "name": package_name,
                "private": True,
                "keywords": ["pi-package"],
                "pi": {"skills": ["./.pi/skills"]},
            },
            indent=2,
        )
        + "\n"
    )
