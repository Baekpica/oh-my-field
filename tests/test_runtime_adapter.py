from dataclasses import dataclass
from pathlib import Path

import pytest

from oh_my_field.adapters import (
    BUILTIN_ADAPTERS,
    AgentImportDependencies,
    AgentImportRequest,
    AgentImportSummary,
    ImporterAdapter,
    RuntimeAdapterPluginError,
    build_adapter_registry,
    builtin_adapter_registry,
    register_runtime_adapter,
)
from oh_my_field.domain.runtime.adapter import UnknownRuntimeError
from oh_my_field.domain.runtime.registry import AdapterRegistry
from oh_my_field.models import AgentImporterSpec


def test_builtin_registry_exposes_known_runtimes() -> None:
    assert BUILTIN_ADAPTERS.available() == ("claude_code", "codex", "hermes")
    assert BUILTIN_ADAPTERS.get("codex").spec.name == "codex"


def test_registry_raises_unknown_runtime_error() -> None:
    registry = AdapterRegistry()
    with pytest.raises(UnknownRuntimeError) as excinfo:
        registry.get("bogus")
    assert excinfo.value.name == "bogus"
    assert "available: none" in str(excinfo.value)


def test_registry_lists_available_runtimes_in_error() -> None:
    with pytest.raises(UnknownRuntimeError) as excinfo:
        BUILTIN_ADAPTERS.get("gpt5")
    message = str(excinfo.value)
    assert "claude_code" in message
    assert "codex" in message
    assert "hermes" in message


def test_importer_adapter_satisfies_protocol() -> None:
    adapter = BUILTIN_ADAPTERS.get("hermes")
    assert isinstance(adapter, ImporterAdapter)
    assert hasattr(adapter, "import_run")
    assert adapter.spec.display_name == "Hermes"


def test_import_request_accepts_external_runtime_adapter_names() -> None:
    request = AgentImportRequest(
        adapter="acme",
        log_path=Path("run.log"),
        goal="import external run",
        field="local",
        evidence_dir=Path("evidence"),
    )

    assert request.adapter == "acme"


def test_register_runtime_adapter_allows_external_names() -> None:
    registry = builtin_adapter_registry()

    register_runtime_adapter(registry, AcmeAdapter())

    assert registry.get("acme").spec.display_name == "Acme Runtime"


def test_build_registry_loads_runtime_adapter_entry_points() -> None:
    registry = build_adapter_registry(
        entry_points=(FakeEntryPoint(name="acme", adapter=AcmeAdapter()),),
    )

    assert registry.available() == ("acme", "claude_code", "codex", "hermes")
    assert registry.get("acme").spec.name == "acme"


def test_build_registry_accepts_runtime_adapter_factories() -> None:
    registry = build_adapter_registry(entry_points=(FactoryEntryPoint(name="acme"),))

    assert registry.get("acme").spec.display_name == "Acme Runtime"


def test_runtime_adapter_plugin_errors_identify_entry_point() -> None:
    with pytest.raises(RuntimeAdapterPluginError) as excinfo:
        build_adapter_registry(entry_points=(BrokenEntryPoint(name="broken"),))

    assert excinfo.value.source == "broken"
    assert "boom" in str(excinfo.value)


class AcmeAdapter:
    spec = AgentImporterSpec(name="acme", display_name="Acme Runtime")

    def import_run(
        self,
        request: AgentImportRequest,
        dependencies: AgentImportDependencies | None = None,
    ) -> AgentImportSummary:
        del request, dependencies
        message = "test adapter should not import a run"
        raise AssertionError(message)


@dataclass(frozen=True, slots=True)
class FakeEntryPoint:
    name: str
    adapter: AcmeAdapter

    def load(self) -> AcmeAdapter:
        return self.adapter


@dataclass(frozen=True, slots=True)
class FactoryEntryPoint:
    name: str

    def load(self) -> type[AcmeAdapter]:
        return AcmeAdapter


@dataclass(frozen=True, slots=True)
class BrokenEntryPoint:
    name: str

    def load(self) -> AcmeAdapter:
        message = "boom"
        raise RuntimeError(message)
