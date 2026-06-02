from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import Field

from oh_my_field.models import (
    CAPABILITY_NAME_PATTERN,
    CapabilityManifest,
    CapabilityRegistry,
    CapabilityRegistryEntry,
    EvalResult,
    StrictModel,
)
from oh_my_field.storage import list_eval_results, list_manifests

type Clock = Callable[[], datetime]


class RegistryError(Exception):
    pass


@dataclass
class CapabilityRegistryNotFoundError(RegistryError):
    capability_name: str

    def __str__(self) -> str:
        return f"capability {self.capability_name!r} not found in registry"


class RegistryRequest(StrictModel):
    capability_name: str | None = Field(default=None, pattern=CAPABILITY_NAME_PATTERN)
    capabilities_dir: Path
    eval_dir: Path


class RegistrySummary(StrictModel):
    capability_name: str | None = None
    count: int
    registry: CapabilityRegistry


def run_registry_workflow(
    request: RegistryRequest,
    clock: Clock | None = None,
) -> RegistrySummary:
    clock = clock or _now_utc
    eval_results = list_eval_results(request.eval_dir)
    entries = tuple(
        _entry_from_manifest(
            manifest=manifest,
            manifest_path=manifest_path,
            eval_results=eval_results,
        )
        for manifest_path, manifest in list_manifests(request.capabilities_dir)
    )
    if request.capability_name is not None:
        entries = tuple(
            entry for entry in entries if entry.name == request.capability_name
        )
        if not entries:
            raise CapabilityRegistryNotFoundError(
                capability_name=request.capability_name,
            )
    registry = CapabilityRegistry(
        generated_at=clock().astimezone(UTC),
        entries=entries,
    )
    return RegistrySummary(
        capability_name=request.capability_name,
        count=len(entries),
        registry=registry,
    )


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _entry_from_manifest(
    *,
    manifest: CapabilityManifest,
    manifest_path: Path,
    eval_results: tuple[EvalResult, ...],
) -> CapabilityRegistryEntry:
    evaluation_results = tuple(
        result.id
        for result in eval_results
        if result.capability_name == manifest.name
    )
    return CapabilityRegistryEntry(
        name=manifest.name,
        version=manifest.version,
        description=manifest.description,
        status=manifest.status,
        owner=manifest.owner,
        dependencies=manifest.dependencies,
        runtime_compatibility=(
            *manifest.runtime_compatibility,
            *_runtime_compatibility(manifest),
        ),
        evaluation_results=tuple(
            dict.fromkeys((*manifest.evaluation_results, *evaluation_results)),
        ),
        manifest_path=str(manifest_path),
    )


def _runtime_compatibility(manifest: CapabilityManifest) -> tuple[str, ...]:
    values = [f"runtime:{manifest.runtime.name}"]
    if manifest.runtime.model is not None:
        values.append(f"model:{manifest.runtime.model}")
    values.extend(f"model:{model}" for model in manifest.runtime.preferred_models)
    values.extend(f"tool:{tool}" for tool in manifest.runtime.tools)
    return tuple(dict.fromkeys(values))
