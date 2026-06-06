from pathlib import Path

from oh_my_field.adapters.runtime_export.base import (
    RuntimeExportAdapter,
    RuntimeExportRequest,
)
from oh_my_field.adapters.runtime_export.claude_code import (
    ClaudeCodeRuntimeExportAdapter,
)
from oh_my_field.adapters.runtime_export.codex import CodexRuntimeExportAdapter
from oh_my_field.adapters.runtime_export.generic import GenericRuntimeExportAdapter
from oh_my_field.adapters.runtime_export.hermes import HermesRuntimeExportAdapter
from oh_my_field.adapters.runtime_export.odysseus import (
    OdysseusRuntimeExportAdapter,
)
from oh_my_field.adapters.runtime_export.pi import PiRuntimeExportAdapter
from oh_my_field.domain.models import CapabilityManifest
from oh_my_field.domain.portability.models import ExportTarget, PortabilityManifest

_ADAPTERS: dict[ExportTarget, RuntimeExportAdapter] = {
    "claude_code": ClaudeCodeRuntimeExportAdapter(),
    "codex": CodexRuntimeExportAdapter(),
    "generic": GenericRuntimeExportAdapter(),
    "hermes": HermesRuntimeExportAdapter(),
    "odysseus": OdysseusRuntimeExportAdapter(),
    "pi": PiRuntimeExportAdapter(),
}


def get_runtime_export_adapter(target: ExportTarget) -> RuntimeExportAdapter:
    return _ADAPTERS[target]


def write_runtime_target(
    bundle_path: Path,
    manifest: CapabilityManifest,
    portability: PortabilityManifest,
) -> Path:
    adapter = get_runtime_export_adapter(portability.target.runtime)
    summary = adapter.export_capability(
        RuntimeExportRequest(
            bundle_path=bundle_path,
            manifest=manifest,
            portability=portability,
        ),
    )
    return Path(summary.runtime_path)


__all__ = [
    "RuntimeExportAdapter",
    "RuntimeExportRequest",
    "get_runtime_export_adapter",
    "write_runtime_target",
]
