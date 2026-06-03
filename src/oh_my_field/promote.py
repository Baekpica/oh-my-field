from dataclasses import dataclass
from pathlib import Path
from typing import Final, TypedDict, cast

import yaml
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import Field

from oh_my_field.integrity import append_integrity_link, integrity_link
from oh_my_field.models import (
    COMMAND_RISK_CATEGORIES,
    ArtifactIntegrityLink,
    CapabilityManifest,
    CapabilityStatus,
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


@dataclass
class PromoteEvidenceSourceError(PromoteError):
    def __str__(self) -> str:
        return "promote requires an evidence id or --from-evidence-set"


@dataclass
class EvidenceSetParseError(PromoteError):
    path: Path
    reason: str

    def __str__(self) -> str:
        return f"could not parse evidence set {self.path}: {self.reason}"


class PromoteRequest(StrictModel):
    evidence_id: str | None = Field(default=None, min_length=1)
    from_evidence_set: Path | None = None
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
    evidence_records: tuple[EvidenceRecord, ...]
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
    evidence_ids = _evidence_ids(request)
    evidence_records = tuple(
        load_evidence(evidence_id, request.evidence_dir)
        for evidence_id in evidence_ids
    )
    return PromoteState(evidence_records=evidence_records)


def _build_manifest(state: PromoteState) -> PromoteState:
    request = _state_request(state)
    evidence_records = _state_evidence_records(state)
    evidence = evidence_records[0]
    runtime_tools = _runtime_tools(evidence_records)
    source_evidence_ids = tuple(record.id for record in evidence_records)
    promotion_criteria = PromotionCriteria(
        min_success_runs=3,
        max_human_intervention_rate=0.3,
        required_harness_pass_rate=0.9,
        min_runtime_profiles=_min_runtime_profiles(evidence_records),
    )
    manifest = CapabilityManifest(
        name=request.name,
        version=request.version,
        description=request.description,
        status=_capability_status(evidence_records, promotion_criteria),
        runtime_compatibility=_runtime_compatibility(evidence_records, runtime_tools),
        source_evidence_id=evidence.id,
        source_evidence_ids=source_evidence_ids,
        field=_field_manifest(evidence_records),
        normalized_goal=evidence.normalized_goal or evidence.goal,
        inputs=("goal", *_input_context(evidence_records)),
        context=ContextPolicy(
            required=_input_context(evidence_records),
            optional=_optional_context(evidence_records),
            forbidden=(".env", "secrets/", "production-kubeconfig"),
            sources=_context_sources(evidence_records),
            source_priority=("evidence", "repository", "user_feedback"),
            evidence_recall_strategy="prefer prior successful evidence, then failures",
        ),
        workflow=WorkflowManifest(graph="langgraph", nodes=CAPABILITY_WORKFLOW_NODES),
        harness=_harness_result(evidence_records),
        runtime=RuntimeInfo(
            name=evidence.runtime.name,
            model=evidence.runtime.model,
            preferred_models=_preferred_models(evidence_records),
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
        promotion_criteria=promotion_criteria,
    )
    evidence_links = tuple(
        _evidence_integrity_link(record) for record in evidence_records
    )
    manifest = manifest.model_copy(
        update={"integrity_chain": evidence_links},
    )
    manifest = append_integrity_link(
        manifest,
        artifact_type="capability",
        artifact_id=manifest.name,
        previous_sha256=manifest.integrity_chain[-1].sha256,
    )
    return PromoteState(manifest=manifest)


def _evidence_ids(request: PromoteRequest) -> tuple[str, ...]:
    evidence_ids: list[str] = []
    if request.evidence_id is not None:
        evidence_ids.append(request.evidence_id)
    if request.from_evidence_set is not None:
        evidence_ids.extend(_read_evidence_set(request.from_evidence_set))
    if not evidence_ids:
        raise PromoteEvidenceSourceError
    return tuple(dict.fromkeys(evidence_ids))


def _read_evidence_set(path: Path) -> tuple[str, ...]:
    try:
        parsed = cast("object", yaml.safe_load(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise EvidenceSetParseError(path=path, reason=str(exc)) from exc
    list_ids = _string_list(parsed)
    if list_ids is not None:
        return list_ids
    if isinstance(parsed, dict):
        parsed_mapping = cast("dict[object, object]", parsed)
        raw_ids = parsed_mapping.get("evidence_ids")
        mapping_ids = _string_list(raw_ids)
        if mapping_ids is not None:
            return mapping_ids
    raise EvidenceSetParseError(
        path=path,
        reason="expected a list of ids or mapping with evidence_ids",
    )


def _string_list(value: object) -> tuple[str, ...] | None:
    if not isinstance(value, list):
        return None
    raw_items = cast("list[object]", value)
    items: list[str] = []
    for item in raw_items:
        if not isinstance(item, str):
            return None
        items.append(item)
    return tuple(items)


def _field_manifest(evidence_records: tuple[EvidenceRecord, ...]) -> FieldManifest:
    primary = evidence_records[0]
    return FieldManifest(
        name=_field_name(primary.field),
        description=f"Field policy inferred from evidence field {primary.field!r}.",
        sources=_context_sources(evidence_records),
        policies=FieldPolicy(
            network="disabled",
            require_approval=COMMAND_RISK_CATEGORIES,
            forbidden_context=(".env", "secrets/", "production-kubeconfig"),
        ),
        quality_bar=FieldQualityBar(
            required_checks=_required_checks(evidence_records),
            human_review_required=True,
        ),
        failure_history=FieldFailureHistory(
            recall_strategy="prefer_recent_regressions",
            cases=tuple(
                error for record in evidence_records for error in record.errors
            ),
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


def _context_sources(
    evidence_records: tuple[EvidenceRecord, ...],
) -> tuple[ContextSource, ...]:
    sources = [
        ContextSource(
            name=f"source_evidence_{index}",
            type="evidence",
            location=evidence.id,
            freshness="captured",
            priority=index,
        )
        for index, evidence in enumerate(evidence_records, start=1)
    ]
    input_context = _input_context(evidence_records)
    if input_context:
        sources.append(
            ContextSource(
                name="input_context",
                type="docs",
                location=",".join(input_context),
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


def _runtime_tools(evidence_records: tuple[EvidenceRecord, ...]) -> tuple[str, ...]:
    tools = [
        tool
        for evidence in evidence_records
        for tool in evidence.runtime.tools
    ]
    if any(evidence.generated_commands for evidence in evidence_records):
        tools.append("shell")
    if any(evidence.files for evidence in evidence_records):
        tools.append("file_system")
    return tuple(dict.fromkeys(tools))


def _preferred_models(evidence_records: tuple[EvidenceRecord, ...]) -> tuple[str, ...]:
    models: list[str] = []
    for evidence in evidence_records:
        if evidence.runtime.model is not None:
            models.append(evidence.runtime.model)
        models.extend(evidence.runtime.preferred_models)
    return tuple(dict.fromkeys(models))


def _runtime_compatibility(
    evidence_records: tuple[EvidenceRecord, ...],
    runtime_tools: tuple[str, ...],
) -> tuple[str, ...]:
    values = [
        f"runtime:{evidence.runtime.name}"
        for evidence in evidence_records
    ]
    values.extend(
        f"model:{evidence.runtime.model}"
        for evidence in evidence_records
        if evidence.runtime.model is not None
    )
    values.extend(
        f"model:{model}"
        for evidence in evidence_records
        for model in evidence.runtime.preferred_models
    )
    values.extend(f"tool:{tool}" for tool in runtime_tools)
    return tuple(dict.fromkeys(values))


def _input_context(evidence_records: tuple[EvidenceRecord, ...]) -> tuple[str, ...]:
    values = [
        item
        for evidence in evidence_records
        for item in evidence.input_context
    ]
    return tuple(dict.fromkeys(values))


def _optional_context(evidence_records: tuple[EvidenceRecord, ...]) -> tuple[str, ...]:
    values = [
        file.path
        for evidence in evidence_records
        for file in evidence.files
        if file.role != "context"
    ]
    return tuple(dict.fromkeys(values))


def _required_checks(evidence_records: tuple[EvidenceRecord, ...]) -> tuple[str, ...]:
    values = [
        check
        for evidence in evidence_records
        for check in evidence.harness.required_checks
    ]
    return tuple(dict.fromkeys((*values, "schema_valid")))


def _harness_result(evidence_records: tuple[EvidenceRecord, ...]) -> HarnessResult:
    failures = tuple(
        failure
        for evidence in evidence_records
        for failure in evidence.harness.failures
    )
    checks = tuple(
        dict.fromkeys(
            check
            for evidence in evidence_records
            for check in evidence.harness.checks
        ),
    )
    return HarnessResult(
        status="fail" if failures else "pass",
        checks=checks,
        failures=failures,
        required_checks=_required_checks(evidence_records),
        human_review_required=True,
    )


def _min_runtime_profiles(
    evidence_records: tuple[EvidenceRecord, ...],
) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            f"runtime:{evidence.runtime.name}" for evidence in evidence_records
        ),
    )


def _capability_status(
    evidence_records: tuple[EvidenceRecord, ...],
    criteria: PromotionCriteria,
) -> CapabilityStatus:
    success_count = sum(
        1
        for evidence in evidence_records
        if evidence.success_or_failure_label == "success"
        or evidence.harness.status == "pass"
    )
    pass_rate = success_count / len(evidence_records)
    intervention_rate = (
        sum(1 for evidence in evidence_records if evidence.user_interventions)
        / len(evidence_records)
    )
    runtime_profiles = _min_runtime_profiles(evidence_records)
    if (
        success_count >= criteria.min_success_runs
        and pass_rate >= criteria.required_harness_pass_rate
        and intervention_rate <= criteria.max_human_intervention_rate
        and all(
            profile in runtime_profiles for profile in criteria.min_runtime_profiles
        )
    ):
        return "validated"
    return "candidate"


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


def _state_evidence_records(state: PromoteState) -> tuple[EvidenceRecord, ...]:
    evidence_records = state.get("evidence_records")
    if evidence_records is None:
        raise PromoteStateError(key="evidence_records")
    return evidence_records


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
