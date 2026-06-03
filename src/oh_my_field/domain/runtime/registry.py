"""Runtime adapter registry.

A pure container that maps a runtime name to its ``RuntimeAdapter``. The
domain owns the registry type and the unknown-runtime failure; the adapters
layer constructs and populates the concrete instances.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from oh_my_field.domain.runtime.adapter import UnknownRuntimeError

if TYPE_CHECKING:
    from oh_my_field.domain.runtime.adapter import RuntimeAdapter


class AdapterRegistry:
    def __init__(self) -> None:
        """Create an empty runtime adapter registry."""
        self._adapters: dict[str, RuntimeAdapter] = {}

    def register(self, name: str, adapter: RuntimeAdapter) -> None:
        self._adapters[name] = adapter

    def get(self, name: str) -> RuntimeAdapter:
        try:
            return self._adapters[name]
        except KeyError:
            raise UnknownRuntimeError(name, self.available()) from None

    def available(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))
