"""Runtime adapters: import external agent runs into OMF evidence.

This package is also the compatibility surface for the old
oh_my_field.adapters module path.
"""

from oh_my_field.adapters.agent_import import (
    ADAPTER_SPECS,
    BUILTIN_ADAPTERS,
    DEFAULT_EXCLUDE_PATTERNS,
    IMPORTER_SPECS,
    OMFIGNORE_FILE_NAME,
    RUNTIME_ADAPTER_ENTRY_POINT_GROUP,
    AdapterError,
    AgentArtifactInput,
    AgentArtifactLimitError,
    AgentArtifactReadError,
    AgentImportDependencies,
    AgentImportRequest,
    AgentImportSummary,
    Clock,
    ImporterAdapter,
    ImporterError,
    RuntimeAdapterPluginError,
    TokenFactory,
    build_adapter_registry,
    builtin_adapter_registry,
    import_agent_run,
    load_runtime_adapter_plugins,
    register_runtime_adapter,
)
from oh_my_field.domain.runtime.adapter import RuntimeAdapter

__all__ = [
    "ADAPTER_SPECS",
    "BUILTIN_ADAPTERS",
    "DEFAULT_EXCLUDE_PATTERNS",
    "IMPORTER_SPECS",
    "OMFIGNORE_FILE_NAME",
    "RUNTIME_ADAPTER_ENTRY_POINT_GROUP",
    "AdapterError",
    "AgentArtifactInput",
    "AgentArtifactLimitError",
    "AgentArtifactReadError",
    "AgentImportDependencies",
    "AgentImportRequest",
    "AgentImportSummary",
    "Clock",
    "ImporterAdapter",
    "ImporterError",
    "RuntimeAdapter",
    "RuntimeAdapterPluginError",
    "TokenFactory",
    "build_adapter_registry",
    "builtin_adapter_registry",
    "import_agent_run",
    "load_runtime_adapter_plugins",
    "register_runtime_adapter",
]
