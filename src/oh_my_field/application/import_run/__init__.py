"""Import-run use case: turn an external agent run into evidence.

The import use case is generic across runtimes; it dispatches through the
runtime adapter registry in oh_my_field.adapters.
"""

from oh_my_field.adapters import (
    AdapterError,
    AgentArtifactInput,
    AgentImportRequest,
    AgentImportSummary,
    import_agent_run,
)

__all__ = [
    "AdapterError",
    "AgentArtifactInput",
    "AgentImportRequest",
    "AgentImportSummary",
    "import_agent_run",
]
