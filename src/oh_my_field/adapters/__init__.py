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
    TokenFactory,
    import_agent_run,
)

__all__ = [
    "ADAPTER_SPECS",
    "BUILTIN_ADAPTERS",
    "DEFAULT_EXCLUDE_PATTERNS",
    "IMPORTER_SPECS",
    "OMFIGNORE_FILE_NAME",
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
    "TokenFactory",
    "import_agent_run",
]
