from dataclasses import dataclass
from pathlib import Path
from typing import Final, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import Field

from oh_my_field.integrity import append_integrity_link, integrity_link
from oh_my_field.models import (
    COMMAND_RISK_CATEGORIES,
    ArtifactIntegrityLink,
    CapabilityManifest,
    ContextPolicy,
    ContextSource,
    EvidencePolicy,
    EvidenceRecord,
    FieldFailureHistory,
    FieldManifest,
    FieldPolicy,
    FieldQualityBar,
    HarnessResult,
    PromotionCriteria,
    RuntimeInfo,
    StrictModel,
    WorkflowControl,
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
CAPABILITY_WORKFLOW_NODES: Final = (
    "parse_goal",
    "collect_context",
    "plan_execution",
    "execute_tools",
    "run_harness",
    "collect_evidence",
    "human_review",
    "package_learning",
)
EVIDENCE_STORE_FIELDS: Final = (
    "prompts",
    "tool_calls",
    "generated_commands",
    "generated_scripts",
    "execution_outputs",
    "errors",
    "retries",
    "user_interventions",
    "final_artifacts",
    "harness_results",
    "cost_metrics",
    "latency_metrics",
    "success_or_failure_label",
    "improvement_notes",
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
    runtime_tools = _runtime_tools(evidence)
    manifest = CapabilityManifest(
        name=request.name,
        version=request.version,
        description=request.description,
        status="candidate",
        runtime_compatibility=_runtime_compatibility(evidence, runtime_tools),
        source_evidence_id=evidence.id,
        source_evidence_ids=(evidence.id,),
        field=_field_manifest(evidence),
        normalized_goal=evidence.normalized_goal or evidence.goal,
        inputs=("goal", *evidence.input_context),
        context=ContextPolicy(
            required=evidence.input_context,
            optional=tuple(
                file.path for file in evidence.files if file.role != "context"
            ),
            forbidden=(".env", "secrets/", "production-kubeconfig"),
            sources=_context_sources(evidence),
            source_priority=("evidence", "repository", "user_feedback"),
            evidence_recall_strategy="prefer prior successful evidence, then failures",
        ),
        workflow=WorkflowManifest(graph="langgraph", nodes=CAPABILITY_WORKFLOW_NODES),
        harness=HarnessResult(
            status=evidence.harness.status,
            checks=evidence.harness.checks,
            failures=evidence.harness.failures,
            required_checks=tuple(
                dict.fromkeys((*evidence.harness.required_checks, "schema_valid")),
            ),
            human_review_required=True,
        ),
        runtime=RuntimeInfo(
            name=evidence.runtime.name,
            model=evidence.runtime.model,
            preferred_models=_preferred_models(evidence),
            tools=runtime_tools,
        ),
        evidence=EvidencePolicy(store=EVIDENCE_STORE_FIELDS),
        workflow_control=WorkflowControl(
            allowed_tools=runtime_tools,
            require_approval_before_write=True,
            require_approval_before_external_call=True,
            require_approval_before_destructive_action=True,
            approval_required_actions=COMMAND_RISK_CATEGORIES,
            safe_execution_mode=True,
            network_policy="disabled",
            rollback_policy="manual checkpoint restore",
            checkpoint_interval=1,
        ),
        promotion_criteria=PromotionCriteria(
            min_success_runs=3,
            max_human_intervention_rate=0.3,
            required_harness_pass_rate=0.9,
            min_runtime_profiles=(f"runtime:{evidence.runtime.name}",),
        ),
    )
    manifest = manifest.model_copy(
        update={"integrity_chain": (_evidence_integrity_link(evidence),)},
    )
    manifest = append_integrity_link(
        manifest,
        artifact_type="capability",
        artifact_id=manifest.name,
        previous_sha256=manifest.integrity_chain[-1].sha256,
    )
    return PromoteState(manifest=manifest)


def _field_manifest(evidence: EvidenceRecord) -> FieldManifest:
    return FieldManifest(
        name=_field_name(evidence.field),
        description=f"Field policy inferred from evidence field {evidence.field!r}.",
        sources=_context_sources(evidence),
        policies=FieldPolicy(
            network="disabled",
            require_approval=COMMAND_RISK_CATEGORIES,
            forbidden_context=(".env", "secrets/", "production-kubeconfig"),
        ),
        quality_bar=FieldQualityBar(
            required_checks=evidence.harness.required_checks,
            human_review_required=True,
        ),
        failure_history=FieldFailureHistory(
            recall_strategy="prefer_recent_regressions",
            cases=evidence.errors,
        ),
    )


def _field_name(value: str) -> str:
    normalized = "".join(
        character if character.isalnum() else "_"
        for character in value.casefold()
    ).strip("_")
    if not normalized:
        return "field_local"
    if normalized[0].isalpha():
        return normalized
    return f"field_{normalized}"


def _context_sources(evidence: EvidenceRecord) -> tuple[ContextSource, ...]:
    sources = [
        ContextSource(
            name="source_evidence",
            type="evidence",
            location=evidence.id,
            freshness="captured",
            priority=0,
        ),
    ]
    if evidence.input_context:
        sources.append(
            ContextSource(
                name="input_context",
                type="docs",
                location=",".join(evidence.input_context),
                freshness="captured",
                priority=10,
            ),
        )
    return tuple(sources)


def _evidence_integrity_link(evidence: EvidenceRecord) -> ArtifactIntegrityLink:
    if evidence.integrity_chain:
        return evidence.integrity_chain[-1]
    return integrity_link(
        artifact_type="evidence",
        artifact_id=evidence.id,
        model=evidence,
    )


def _runtime_tools(evidence: EvidenceRecord) -> tuple[str, ...]:
    tools = [*evidence.runtime.tools]
    if evidence.generated_commands:
        tools.append("shell")
    if evidence.files:
        tools.append("file_system")
    return tuple(dict.fromkeys(tools))


def _preferred_models(evidence: EvidenceRecord) -> tuple[str, ...]:
    models: list[str] = []
    if evidence.runtime.model is not None:
        models.append(evidence.runtime.model)
    models.extend(evidence.runtime.preferred_models)
    return tuple(dict.fromkeys(models))


def _runtime_compatibility(
    evidence: EvidenceRecord,
    runtime_tools: tuple[str, ...],
) -> tuple[str, ...]:
    values = [f"runtime:{evidence.runtime.name}"]
    if evidence.runtime.model is not None:
        values.append(f"model:{evidence.runtime.model}")
    values.extend(f"model:{model}" for model in evidence.runtime.preferred_models)
    values.extend(f"tool:{tool}" for tool in runtime_tools)
    return tuple(dict.fromkeys(values))


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
