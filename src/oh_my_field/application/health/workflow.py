from pathlib import Path

from pydantic import Field

from oh_my_field.integrity import model_sha256
from oh_my_field.models import (
    CAPABILITY_NAME_PATTERN,
    CapabilityManifest,
    EvalResult,
    ExportStatus,
    ImportStatus,
    IntegrityVerificationStatus,
    PortabilityHealth,
    StrictModel,
    TargetStatusEntry,
    TargetValidationStatus,
)
from oh_my_field.storage import (
    capability_package_paths,
    list_eval_results,
    list_manifests,
    load_manifest,
    read_portability_health,
    render_capability_card,
    update_manifest,
)


class HealthError(Exception):
    pass


class CapabilityHealthRequest(StrictModel):
    capability_name: str | None = Field(default=None, pattern=CAPABILITY_NAME_PATTERN)
    capabilities_dir: Path
    eval_dir: Path


class CapabilityHealthEntry(StrictModel):
    name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    status: str
    evidence_count: int = Field(ge=0)
    successful_evidence_count: int = Field(ge=0)
    eval_count: int = Field(ge=0)
    failed_eval_count: int = Field(ge=0)
    pass_rate: float = Field(ge=0.0, le=1.0)
    integrity_status: str
    runtime_coverage: tuple[str, ...] = ()
    export_status: ExportStatus
    import_status: ImportStatus
    validation_status: TargetValidationStatus
    export_count: int = Field(ge=0)
    import_count: int = Field(ge=0)
    target_validation_count: int = Field(ge=0)
    target_statuses: tuple[TargetStatusEntry, ...] = ()
    next_action: str = Field(min_length=1)


class CapabilityHealthSummary(StrictModel):
    capability_name: str | None = None
    count: int
    entries: tuple[CapabilityHealthEntry, ...]


class CapabilityHardenSummary(StrictModel):
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    recommended_actions: tuple[str, ...]


class CapabilityCardSummary(StrictModel):
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    card_path: str
    written: bool = False
    content: str


def run_health_workflow(request: CapabilityHealthRequest) -> CapabilityHealthSummary:
    eval_results = list_eval_results(request.eval_dir)
    entries = tuple(
        health_entry_from_manifest(
            manifest=manifest,
            package_dir=path.parent,
            eval_results=eval_results,
        )
        for path, manifest in list_manifests(request.capabilities_dir)
    )
    if request.capability_name is not None:
        entries = tuple(
            entry for entry in entries if entry.name == request.capability_name
        )
    return CapabilityHealthSummary(
        capability_name=request.capability_name,
        count=len(entries),
        entries=entries,
    )


def run_harden_workflow(request: CapabilityHealthRequest) -> CapabilityHardenSummary:
    if request.capability_name is None:
        msg = "harden requires a capability name"
        raise HealthError(msg)
    summary = run_health_workflow(request)
    if not summary.entries:
        msg = f"capability {request.capability_name!r} not found"
        raise HealthError(msg)
    entry = summary.entries[0]
    actions = _harden_actions(entry)
    return CapabilityHardenSummary(
        capability_name=entry.name,
        recommended_actions=actions,
    )


def run_card_workflow(
    *,
    capability_name: str,
    capabilities_dir: Path,
    write: bool,
) -> CapabilityCardSummary:
    manifest = load_manifest(capability_name, capabilities_dir)
    paths = capability_package_paths(capability_name, capabilities_dir)
    if write:
        update_manifest(manifest, capabilities_dir)
    content = (
        paths.card_path.read_text(encoding="utf-8")
        if paths.card_path.exists()
        else render_capability_card(
            manifest,
            read_portability_health(paths.package_dir),
        )
    )
    return CapabilityCardSummary(
        capability_name=manifest.name,
        card_path=str(paths.card_path),
        written=write,
        content=content,
    )


def health_entry_from_manifest(
    *,
    manifest: CapabilityManifest,
    package_dir: Path,
    eval_results: tuple[EvalResult, ...],
) -> CapabilityHealthEntry:
    capability_evals = tuple(
        result for result in eval_results if result.capability_name == manifest.name
    )
    pass_count = sum(result.status == "pass" for result in capability_evals)
    failed_count = sum(result.status == "fail" for result in capability_evals)
    integrity_status = manifest_integrity_status(manifest)
    portability = read_portability_health(package_dir)
    return CapabilityHealthEntry(
        name=manifest.name,
        status=manifest.status,
        evidence_count=_evidence_count(manifest),
        successful_evidence_count=_successful_evidence_count(manifest),
        eval_count=len(capability_evals),
        failed_eval_count=failed_count,
        pass_rate=pass_count / len(capability_evals) if capability_evals else 0.0,
        integrity_status=integrity_status,
        runtime_coverage=_runtime_coverage(manifest),
        export_status=portability.export_status,
        import_status=portability.import_status,
        validation_status=portability.validation_status,
        export_count=portability.export_count,
        import_count=portability.import_count,
        target_validation_count=portability.target_validation_count,
        target_statuses=portability.target_statuses,
        next_action=next_action_for_capability(
            manifest=manifest,
            eval_results=capability_evals,
            integrity_status=integrity_status,
            portability=portability,
        ),
    )


def manifest_integrity_status(
    manifest: CapabilityManifest,
) -> IntegrityVerificationStatus:
    if not manifest.integrity_chain:
        return "fail"
    if model_sha256(manifest) == manifest.integrity_chain[-1].sha256:
        return "pass"
    return "fail"


def next_action_for_capability(
    *,
    manifest: CapabilityManifest,
    eval_results: tuple[EvalResult, ...],
    integrity_status: str,
    portability: PortabilityHealth,
) -> str:
    action: str
    validation = portability.validation_status
    if integrity_status == "fail":
        action = f"run `omf verify capability {manifest.name}`"
    elif not eval_results:
        action = f"run eval set `{manifest.name}_regression`"
    elif any(result.status == "fail" for result in eval_results):
        action = "add regression cases for failed evals, then rerun eval"
    elif portability.import_count and validation == "needs_adaptation":
        action = "adapt target import before marking portable"
    elif portability.import_count and validation == "needs_validation":
        action = (
            f"run `omf capability validate {manifest.name} --run-command ...` "
            "to observe a target run (pending, not a failure)"
        )
    elif portability.export_status == "not_exported" and portability.import_count == 0:
        action = "export to a target runtime and validate portability"
    elif manifest.status == "candidate":
        action = "collect more passing evidence or promote from an evidence set"
    else:
        action = "monitor capability health"
    return action


def _harden_actions(entry: CapabilityHealthEntry) -> tuple[str, ...]:
    actions = [entry.next_action]
    if entry.failed_eval_count:
        actions.append("create or update regression cases for failed eval output")
    if entry.eval_count == 0:
        actions.append(
            f"run `omf eval {entry.name} --eval-set {entry.name}_regression`",
        )
    if entry.export_status == "not_exported" and entry.import_count == 0:
        actions.append(
            "export to Codex, Claude Code, Hermes, Pi, Odysseus, or generic target"
        )
    if entry.validation_status == "needs_adaptation":
        actions.append(
            "adapt the failing target import (tools/context), then re-run "
            f"`omf capability validate {entry.name}`",
        )
        actions.append("triage the target failure evidence via `omf learn`")
    elif entry.import_count and entry.validation_status == "needs_validation":
        actions.append(
            f"run `omf capability validate {entry.name} --run-command ...` "
            "on the imported target",
        )
    actions.append("review learning patch candidates after `omf learn`")
    return tuple(dict.fromkeys(actions))


def _evidence_count(manifest: CapabilityManifest) -> int:
    if manifest.promotion_metrics is not None:
        return manifest.promotion_metrics.evidence_count
    if manifest.source_evidence_ids:
        return len(manifest.source_evidence_ids)
    return 1


def _successful_evidence_count(manifest: CapabilityManifest) -> int:
    if manifest.promotion_metrics is not None:
        return manifest.promotion_metrics.successful_evidence_count
    return 0


def _runtime_coverage(manifest: CapabilityManifest) -> tuple[str, ...]:
    values = [f"{manifest.runtime.name}:{manifest.runtime.model or 'model_unknown'}"]
    values.extend(f"tool:{tool}" for tool in manifest.runtime.tools)
    return tuple(values)
