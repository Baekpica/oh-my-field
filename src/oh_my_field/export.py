import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import Field

from oh_my_field.models import (
    CAPABILITY_NAME_PATTERN,
    CapabilityExportBundle,
    CapabilityManifest,
    ContextBundle,
    EvalResult,
    EvidenceRecord,
    LearningExport,
    ReflectionReport,
    StrictModel,
)
from oh_my_field.storage import (
    list_context_bundles,
    list_eval_results,
    list_learning_exports,
    list_reflection_reports,
    load_evidence,
    load_manifest,
    write_export_bundle,
)

EXPORT_NODES: Final = (
    "check_approval",
    "load_manifest",
    "load_source_evidence",
    "collect_related_artifacts",
    "build_bundle",
    "write_bundle",
    "summarize",
)

type Clock = Callable[[], datetime]
type TokenFactory = Callable[[], str]


class ExportError(Exception):
    pass


@dataclass
class ExportApprovalRequiredError(ExportError):
    capability_name: str

    def __str__(self) -> str:
        return (
            f"export for capability {self.capability_name!r} requires --approve-export"
        )


@dataclass
class ExportStateError(ExportError):
    key: str

    def __str__(self) -> str:
        return f"export workflow state missing {self.key!r}"


@dataclass(frozen=True, slots=True)
class ExportDependencies:
    clock: Clock
    token_factory: TokenFactory


class ExportRequest(StrictModel):
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    approve_export: bool = False
    capabilities_dir: Path
    evidence_dir: Path
    eval_dir: Path
    context_dir: Path
    learning_dir: Path
    reflection_dir: Path
    export_dir: Path


class ExportSummary(StrictModel):
    export_id: str
    export_path: str
    capability_name: str
    eval_count: int
    context_count: int
    learning_count: int
    reflection_count: int


class ExportState(TypedDict, total=False):
    request: ExportRequest
    dependencies: ExportDependencies
    manifest: CapabilityManifest
    source_evidence: EvidenceRecord
    eval_results: tuple[EvalResult, ...]
    context_bundles: tuple[ContextBundle, ...]
    learning_exports: tuple[LearningExport, ...]
    reflection_reports: tuple[ReflectionReport, ...]
    bundle: CapabilityExportBundle
    bundle_path: Path
    summary: ExportSummary


def run_export_workflow(
    request: ExportRequest,
    dependencies: ExportDependencies | None = None,
) -> ExportSummary:
    graph = _build_export_graph()
    initial_state = ExportState(
        request=request,
        dependencies=dependencies or _default_dependencies(),
    )
    final_state = graph.invoke(initial_state)
    return _state_summary(final_state)


def _default_dependencies() -> ExportDependencies:
    return ExportDependencies(clock=_now_utc, token_factory=_token_suffix)


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _token_suffix() -> str:
    return secrets.token_hex(4)


def _build_export_graph() -> CompiledStateGraph[
    ExportState,
    None,
    ExportState,
    ExportState,
]:
    builder: StateGraph[ExportState, None, ExportState, ExportState] = StateGraph(
        ExportState,
    )
    builder.add_node("check_approval", _check_approval)
    builder.add_node("load_manifest", _load_manifest)
    builder.add_node("load_source_evidence", _load_source_evidence)
    builder.add_node("collect_related_artifacts", _collect_related_artifacts)
    builder.add_node("build_bundle", _build_bundle)
    builder.add_node("write_bundle", _write_bundle)
    builder.add_node("summarize", _summarize)
    builder.add_edge(START, "check_approval")
    builder.add_edge("check_approval", "load_manifest")
    builder.add_edge("load_manifest", "load_source_evidence")
    builder.add_edge("load_source_evidence", "collect_related_artifacts")
    builder.add_edge("collect_related_artifacts", "build_bundle")
    builder.add_edge("build_bundle", "write_bundle")
    builder.add_edge("write_bundle", "summarize")
    builder.add_edge("summarize", END)
    return builder.compile()


def _check_approval(state: ExportState) -> ExportState:
    request = _state_request(state)
    if not request.approve_export:
        raise ExportApprovalRequiredError(capability_name=request.capability_name)
    return ExportState()


def _load_manifest(state: ExportState) -> ExportState:
    request = _state_request(state)
    manifest = load_manifest(request.capability_name, request.capabilities_dir)
    return ExportState(manifest=manifest)


def _load_source_evidence(state: ExportState) -> ExportState:
    request = _state_request(state)
    manifest = _state_manifest(state)
    evidence = load_evidence(manifest.source_evidence_id, request.evidence_dir)
    return ExportState(source_evidence=evidence)


def _collect_related_artifacts(state: ExportState) -> ExportState:
    request = _state_request(state)
    capability_name = request.capability_name
    return ExportState(
        eval_results=tuple(
            result
            for result in list_eval_results(request.eval_dir)
            if result.capability_name == capability_name
        ),
        context_bundles=tuple(
            bundle
            for bundle in list_context_bundles(request.context_dir)
            if bundle.capability_name == capability_name
        ),
        learning_exports=tuple(
            export
            for export in list_learning_exports(request.learning_dir)
            if export.capability_name == capability_name
        ),
        reflection_reports=tuple(
            report
            for report in list_reflection_reports(request.reflection_dir)
            if report.capability_name == capability_name
        ),
    )


def _build_bundle(state: ExportState) -> ExportState:
    request = _state_request(state)
    dependencies = _state_dependencies(state)
    created_at = dependencies.clock().astimezone(UTC)
    bundle = CapabilityExportBundle(
        id=f"{created_at:%Y%m%dT%H%M%SZ}-{dependencies.token_factory()}",
        created_at=created_at,
        capability_name=request.capability_name,
        manifest=_state_manifest(state),
        source_evidence=_state_source_evidence(state),
        eval_results=state.get("eval_results", ()),
        context_bundles=state.get("context_bundles", ()),
        learning_exports=state.get("learning_exports", ()),
        reflection_reports=state.get("reflection_reports", ()),
    )
    return ExportState(bundle=CapabilityExportBundle.model_validate(bundle))


def _write_bundle(state: ExportState) -> ExportState:
    request = _state_request(state)
    bundle = _state_bundle(state)
    bundle_path = write_export_bundle(bundle, request.export_dir)
    return ExportState(bundle_path=bundle_path)


def _summarize(state: ExportState) -> ExportState:
    bundle = _state_bundle(state)
    bundle_path = _state_bundle_path(state)
    summary = ExportSummary(
        export_id=bundle.id,
        export_path=str(bundle_path),
        capability_name=bundle.capability_name,
        eval_count=len(bundle.eval_results),
        context_count=len(bundle.context_bundles),
        learning_count=len(bundle.learning_exports),
        reflection_count=len(bundle.reflection_reports),
    )
    return ExportState(summary=summary)


def _state_request(state: ExportState) -> ExportRequest:
    request = state.get("request")
    if request is None:
        raise ExportStateError(key="request")
    return request


def _state_dependencies(state: ExportState) -> ExportDependencies:
    dependencies = state.get("dependencies")
    if dependencies is None:
        raise ExportStateError(key="dependencies")
    return dependencies


def _state_manifest(state: ExportState) -> CapabilityManifest:
    manifest = state.get("manifest")
    if manifest is None:
        raise ExportStateError(key="manifest")
    return manifest


def _state_source_evidence(state: ExportState) -> EvidenceRecord:
    evidence = state.get("source_evidence")
    if evidence is None:
        raise ExportStateError(key="source_evidence")
    return evidence


def _state_bundle(state: ExportState) -> CapabilityExportBundle:
    bundle = state.get("bundle")
    if bundle is None:
        raise ExportStateError(key="bundle")
    return bundle


def _state_bundle_path(state: ExportState) -> Path:
    bundle_path = state.get("bundle_path")
    if bundle_path is None:
        raise ExportStateError(key="bundle_path")
    return bundle_path


def _state_summary(state: ExportState) -> ExportSummary:
    summary = state.get("summary")
    if summary is None:
        raise ExportStateError(key="summary")
    return summary
