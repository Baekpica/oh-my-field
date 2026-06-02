from dataclasses import dataclass
from pathlib import Path
from typing import Final, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import Field

from oh_my_field.models import (
    CapabilityManifest,
    EvidenceRecord,
    PromotionCriteria,
    StrictModel,
    WorkflowManifest,
)
from oh_my_field.storage import load_evidence, write_manifest

PROMOTE_NODES: Final = (
    "load_evidence",
    "build_manifest",
    "validate_manifest",
    "write_capability",
    "summarize",
)


class PromoteError(Exception):
    pass


@dataclass
class PromoteStateError(PromoteError):
    key: str

    def __str__(self) -> str:
        return f"promote workflow state missing {self.key!r}"


class PromoteRequest(StrictModel):
    evidence_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    version: str = Field(min_length=1)
    evidence_dir: Path
    capabilities_dir: Path


class PromoteSummary(StrictModel):
    capability_name: str
    manifest_path: str
    status: str


class PromoteState(TypedDict, total=False):
    request: PromoteRequest
    evidence: EvidenceRecord
    manifest: CapabilityManifest
    manifest_path: Path
    summary: PromoteSummary


def run_promote_workflow(request: PromoteRequest) -> PromoteSummary:
    graph = _build_promote_graph()
    final_state = graph.invoke(PromoteState(request=request))
    return _state_summary(final_state)


def _build_promote_graph() -> CompiledStateGraph[
    PromoteState,
    None,
    PromoteState,
    PromoteState,
]:
    builder: StateGraph[PromoteState, None, PromoteState, PromoteState] = StateGraph(
        PromoteState,
    )
    builder.add_node("load_evidence", _load_evidence)
    builder.add_node("build_manifest", _build_manifest)
    builder.add_node("validate_manifest", _validate_manifest)
    builder.add_node("write_capability", _write_capability)
    builder.add_node("summarize", _summarize)
    builder.add_edge(START, "load_evidence")
    builder.add_edge("load_evidence", "build_manifest")
    builder.add_edge("build_manifest", "validate_manifest")
    builder.add_edge("validate_manifest", "write_capability")
    builder.add_edge("write_capability", "summarize")
    builder.add_edge("summarize", END)
    return builder.compile()


def _load_evidence(state: PromoteState) -> PromoteState:
    request = _state_request(state)
    evidence = load_evidence(request.evidence_id, request.evidence_dir)
    return PromoteState(evidence=evidence)


def _build_manifest(state: PromoteState) -> PromoteState:
    request = _state_request(state)
    evidence = _state_evidence(state)
    manifest = CapabilityManifest(
        name=request.name,
        version=request.version,
        description=request.description,
        status="candidate",
        source_evidence_id=evidence.id,
        normalized_goal=evidence.goal,
        inputs=("goal",),
        workflow=WorkflowManifest(graph="langgraph", nodes=PROMOTE_NODES),
        harness=evidence.harness,
        runtime=evidence.runtime,
        promotion_criteria=PromotionCriteria(
            min_success_runs=3,
            max_human_intervention_rate=0.3,
            required_harness_pass_rate=0.9,
        ),
    )
    return PromoteState(manifest=manifest)


def _validate_manifest(state: PromoteState) -> PromoteState:
    manifest = _state_manifest(state)
    checked = CapabilityManifest.model_validate(manifest)
    return PromoteState(manifest=checked)


def _write_capability(state: PromoteState) -> PromoteState:
    request = _state_request(state)
    manifest = _state_manifest(state)
    manifest_path = write_manifest(manifest, request.capabilities_dir)
    return PromoteState(manifest_path=manifest_path)


def _summarize(state: PromoteState) -> PromoteState:
    manifest = _state_manifest(state)
    manifest_path = _state_manifest_path(state)
    summary = PromoteSummary(
        capability_name=manifest.name,
        manifest_path=str(manifest_path),
        status=manifest.status,
    )
    return PromoteState(summary=summary)


def _state_request(state: PromoteState) -> PromoteRequest:
    request = state.get("request")
    if request is None:
        raise PromoteStateError(key="request")
    return request


def _state_evidence(state: PromoteState) -> EvidenceRecord:
    evidence = state.get("evidence")
    if evidence is None:
        raise PromoteStateError(key="evidence")
    return evidence


def _state_manifest(state: PromoteState) -> CapabilityManifest:
    manifest = state.get("manifest")
    if manifest is None:
        raise PromoteStateError(key="manifest")
    return manifest


def _state_manifest_path(state: PromoteState) -> Path:
    manifest_path = state.get("manifest_path")
    if manifest_path is None:
        raise PromoteStateError(key="manifest_path")
    return manifest_path


def _state_summary(state: PromoteState) -> PromoteSummary:
    summary = state.get("summary")
    if summary is None:
        raise PromoteStateError(key="summary")
    return summary
