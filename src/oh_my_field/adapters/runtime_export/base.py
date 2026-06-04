from pathlib import Path
from typing import Protocol

from oh_my_field.domain.models import CapabilityManifest, StrictModel
from oh_my_field.domain.portability.models import ExportTarget, PortabilityManifest


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
