import pytest

from oh_my_field.adapters import BUILTIN_ADAPTERS, ImporterAdapter
from oh_my_field.domain.runtime.adapter import UnknownRuntimeError
from oh_my_field.domain.runtime.registry import AdapterRegistry


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
