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
    capability_evals = tuple(
        result for result in eval_results if result.capability_name == manifest.name
    )
    evaluation_results = tuple(result.id for result in capability_evals)
    pass_count = sum(result.status == "pass" for result in capability_evals)
    latest_eval = max(
        capability_evals,
        key=lambda result: result.created_at,
        default=None,
    )
    runtime_profiles = _runtime_profiles(manifest, capability_evals)
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
        source_evidence_count=len(manifest.source_evidence_ids)
        if manifest.source_evidence_ids
        else 1,
        eval_count=len(capability_evals),
        latest_eval_status=None if latest_eval is None else latest_eval.status,
        pass_rate=pass_count / len(capability_evals) if capability_evals else 0.0,
        runtime_profiles=runtime_profiles,
        patch_count=(
            len(manifest.patches.prompt)
            + len(manifest.patches.context)
            + len(manifest.patches.harness)
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


def _runtime_profiles(
    manifest: CapabilityManifest,
    eval_results: tuple[EvalResult, ...],
) -> tuple[str, ...]:
    values = [_runtime_profile(manifest.runtime.name, manifest.runtime.model)]
    values.extend(
        profile for result in eval_results if (profile := result.runtime_profile)
    )
    return tuple(dict.fromkeys(values))


def _runtime_profile(runtime: str, model: str | None) -> str:
    if model is None:
        return runtime
    return f"{runtime}:{model}"
