"""Import-run use case: turn an external agent run into evidence.

The import use case is generic across runtimes; it dispatches through the
runtime adapter registry in oh_my_field.adapters.
"""

from oh_my_field.adapters import (
    AdapterError,
    AgentArtifactInput,
    AgentImportRequest,
    AgentImportSummary,
    RuntimeAdapterPluginError,
    build_adapter_registry,
    builtin_adapter_registry,
    import_agent_run,
    load_runtime_adapter_plugins,
    register_runtime_adapter,
)

__all__ = [
    "AdapterError",
    "AgentArtifactInput",
    "AgentImportRequest",
    "AgentImportSummary",
    "RuntimeAdapterPluginError",
    "build_adapter_registry",
    "builtin_adapter_registry",
    "import_agent_run",
    "load_runtime_adapter_plugins",
    "register_runtime_adapter",
]
