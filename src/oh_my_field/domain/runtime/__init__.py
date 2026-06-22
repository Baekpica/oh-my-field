"""Domain view: Runtime identity and adapter spec models.

Re-exported from oh_my_field.domain.models so callers can import by
concept (the models share frozen base primitives, so they live in one
definition module to avoid cross-concept import cycles).
"""

from oh_my_field.domain.models import (
    AgentImporterName,
    AgentImporterSpec,
    AgentRunSource,
    RuntimeAdapterName,
    RuntimeInfo,
    RuntimeRunSource,
)

__all__ = [
    "AgentImporterName",
    "AgentImporterSpec",
    "AgentRunSource",
    "RuntimeAdapterName",
    "RuntimeInfo",
    "RuntimeRunSource",
]
