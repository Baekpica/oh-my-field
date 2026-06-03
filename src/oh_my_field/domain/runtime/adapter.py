"""Runtime adapter contract.

A ``RuntimeAdapter`` knows how to turn one external agent runtime's run into
OMF evidence. The protocol is the extension seam for per-runtime behavior:
today every runtime shares the generic importer, but a runtime that needs its
own log parsing implements this same interface and registers itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from oh_my_field.adapters.agent_import import (
        AgentImportDependencies,
        AgentImportRequest,
        AgentImportSummary,
    )
    from oh_my_field.domain.models import AgentImporterSpec


class UnknownRuntimeError(Exception):
    def __init__(self, name: str, available: tuple[str, ...]) -> None:
        """Record the unknown runtime name and the registered alternatives."""
        self.name = name
        self.available = available
        listed = ", ".join(available) or "none"
        super().__init__(f"unknown runtime adapter {name!r}; available: {listed}")


class RuntimeAdapter(Protocol):
    spec: AgentImporterSpec

    def import_run(
        self,
        request: AgentImportRequest,
        dependencies: AgentImportDependencies | None = None,
    ) -> AgentImportSummary: ...
