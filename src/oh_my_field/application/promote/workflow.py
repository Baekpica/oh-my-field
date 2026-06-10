from dataclasses import dataclass
from pathlib import Path
from typing import Final, TypedDict, cast

import yaml
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import Field

from oh_my_field.domain.layout import DEFAULT_EVAL_DIR
from oh_my_field.integrity import append_integrity_link, integrity_link
from oh_my_field.models import (
    COMMAND_RISK_CATEGORIES,
    ArtifactContract,
    ArtifactIntegrityLink,
    CapabilityManifest,
    CapabilityStatus,
    ContextPolicy,
    ContextSource,
    EvalResult,
    EvidencePolicy,
    EvidenceRecord,
    FieldFailureHistory,
    FieldManifest,
    FieldPolicy,
    FieldQualityBar,
    HarnessResult,
    PromotionCriteria,
    PromotionMetrics,
    RecordQuality,
    RuntimeInfo,
    StrictModel,
    TaskContract,
    WorkflowControl,
    WorkflowManifest,
)
from oh_my_field.storage import (
    list_eval_results,
    load_evidence,
    write_capability_package,
)

PROMOTE_NODES: Final = (
    "load_evidence",
    "build_manifest",
    "validate_manifest",
    "write_capability",
    "summarize",
)
CAPABILITY_WORKFLOW_NODES: Final = (
    "import_evidence",
    "pack_context",
    "run_verification",
    "record_review",
    "export_runtime_assets",
    "apply_learning_patch",
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


@dataclass
class PromoteQualityGateError(PromoteError):
    issues: tuple[str, ...]

    def __str__(self) -> str:
        details = "; ".join(self.issues)
        return (
            f"strict quality gate failed: {details}. "
            "Capture or materialize richer evidence, or pass --no-strict "
            "to promote legacy evidence intentionally."
        )


class PromoteRequest(StrictModel):
    evidence_id: str | None = Field(default=None, min_length=1)
    from_evidence_set: Path | None = None
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    version: str = Field(min_length=1)
    evidence_dir: Path
    eval_dir: Path = DEFAULT_EVAL_DIR
    capabilities_dir: Path
    strict: bool = True


class PromoteSummary(StrictModel):
    capability_name: str
    manifest_path: str
    package_path: str
    capability_path: str
    instructions_path: str
    harness_path: str
    card_path: str
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
        load_evidence(evidence_id, request.evidence_dir) for evidence_id in evidence_ids
    )
    if request.strict:
        _enforce_quality_gate(evidence_records)
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
    relevant_evals = tuple(
        result
        for result in list_eval_results(request.eval_dir)
        if result.source_evidence_id in source_evidence_ids
        or result.capability_name == request.name
    )
    promotion_metrics = _promotion_metrics(
        evidence_records,
        relevant_evals,
        promotion_criteria,
    )
    manifest = CapabilityManifest(
        name=request.name,
        version=request.version,
        description=request.description,
        status=_capability_status(promotion_metrics),
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
        promotion_metrics=promotion_metrics,
        artifact_contracts=_artifact_contracts(evidence_records),
        task_contract=_task_contract(evidence_records),
        record_quality=_record_quality(evidence_records),
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


def _enforce_quality_gate(evidence_records: tuple[EvidenceRecord, ...]) -> None:
    issues = tuple(
        issue
        for evidence in evidence_records
        for issue in _quality_gate_issues(evidence)
    )
    if issues:
        raise PromoteQualityGateError(issues=issues)


def _quality_gate_issues(evidence: EvidenceRecord) -> tuple[str, ...]:
    issues: list[str] = []
    prefix = f"evidence {evidence.id}"
    if evidence.record_quality is None:
        issues.append(f"{prefix} is missing record_quality")
    elif not evidence.record_quality.strict_ready:
        missing = ", ".join(evidence.record_quality.missing_sections)
        issues.append(f"{prefix} is not strict-ready: {missing or 'quality warnings'}")
    if evidence.task_contract is None:
        issues.append(f"{prefix} is missing task_contract")
    if not evidence.artifact_contracts:
        issues.append(f"{prefix} is missing artifact_contracts")
    if not evidence.validation_results:
        issues.append(f"{prefix} is missing validation_results")
    failed_validations = tuple(
        result.name for result in evidence.validation_results if result.status == "fail"
    )
    if failed_validations:
        issues.append(
            f"{prefix} has failing validation: {', '.join(failed_validations)}",
        )
    if evidence.harness.status != "pass":
        issues.append(f"{prefix} harness status is {evidence.harness.status}")
    return tuple(issues)


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
        character if character.isalnum() else "_" for character in value.casefold()
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


def _artifact_contracts(
    evidence_records: tuple[EvidenceRecord, ...],
) -> tuple[ArtifactContract, ...]:
    contracts = [
        contract
        for evidence in evidence_records
        for contract in evidence.artifact_contracts
    ]
    by_key = {
        f"{contract.name}:{contract.artifact_path}": contract for contract in contracts
    }
    return tuple(by_key.values())


def _task_contract(
    evidence_records: tuple[EvidenceRecord, ...],
) -> TaskContract | None:
    for evidence in evidence_records:
        if evidence.task_contract is not None:
            return evidence.task_contract
    return None


def _record_quality(
    evidence_records: tuple[EvidenceRecord, ...],
) -> RecordQuality | None:
    qualities = tuple(
        evidence.record_quality
        for evidence in evidence_records
        if evidence.record_quality is not None
    )
    if not qualities:
        return None
    warnings = tuple(
        dict.fromkeys(warning for quality in qualities for warning in quality.warnings)
    )
    missing = tuple(
        dict.fromkeys(
            section for quality in qualities for section in quality.missing_sections
        ),
    )
    return RecordQuality(
        score=min(quality.score for quality in qualities),
        warnings=warnings,
        missing_sections=missing,
        strict_ready=all(quality.strict_ready for quality in qualities),
    )


def _runtime_tools(evidence_records: tuple[EvidenceRecord, ...]) -> tuple[str, ...]:
    tools = [tool for evidence in evidence_records for tool in evidence.runtime.tools]
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
    values = [f"runtime:{evidence.runtime.name}" for evidence in evidence_records]
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
    values = [item for evidence in evidence_records for item in evidence.input_context]
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
            check for evidence in evidence_records for check in evidence.harness.checks
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


def _promotion_metrics(
    evidence_records: tuple[EvidenceRecord, ...],
    eval_results: tuple[EvalResult, ...],
    criteria: PromotionCriteria,
) -> PromotionMetrics:
    evidence_count = len(evidence_records)
    success_count = sum(
        1 for evidence in evidence_records if _evidence_successful(evidence)
    )
    failure_count = sum(
        1 for evidence in evidence_records if _evidence_failed(evidence)
    )
    harness_pass_count = sum(
        1 for evidence in evidence_records if evidence.harness.status == "pass"
    )
    harness_pass_rate = harness_pass_count / evidence_count
    intervention_rate = (
        sum(1 for evidence in evidence_records if evidence.user_interventions)
        / evidence_count
    )
    retry_rate = sum(evidence.retries for evidence in evidence_records) / evidence_count
    eval_count = len(eval_results)
    eval_pass_rate = (
        sum(1 for result in eval_results if result.status == "pass") / eval_count
        if eval_count
        else 0.0
    )
    runtime_profiles = _promotion_runtime_profiles(evidence_records, eval_results)
    criteria_met = (
        success_count >= criteria.min_success_runs
        and harness_pass_rate >= criteria.required_harness_pass_rate
        and intervention_rate <= criteria.max_human_intervention_rate
        and all(
            profile in runtime_profiles for profile in criteria.min_runtime_profiles
        )
    )
    eval_gate_met = (
        True
        if eval_count == 0
        else eval_pass_rate >= criteria.required_harness_pass_rate
    )
    return PromotionMetrics(
        evidence_count=evidence_count,
        successful_evidence_count=success_count,
        failed_evidence_count=failure_count,
        harness_pass_rate=harness_pass_rate,
        human_intervention_rate=intervention_rate,
        retry_rate=retry_rate,
        eval_count=eval_count,
        eval_pass_rate=eval_pass_rate,
        runtime_profiles=runtime_profiles,
        criteria_met=criteria_met,
        eval_gate_met=eval_gate_met,
        recommended_version_bump="minor" if criteria_met else "patch",
    )


def _capability_status(metrics: PromotionMetrics) -> CapabilityStatus:
    if metrics.criteria_met and metrics.eval_gate_met and metrics.eval_count > 0:
        return "stable"
    if metrics.criteria_met and metrics.eval_gate_met:
        return "validated"
    return "candidate"


def _evidence_successful(evidence: EvidenceRecord) -> bool:
    return evidence.task_outcome == "success" or (
        evidence.task_outcome == "unknown"
        and evidence.success_or_failure_label == "success"
    )


def _evidence_failed(evidence: EvidenceRecord) -> bool:
    return evidence.task_outcome == "failure" or (
        evidence.task_outcome == "unknown"
        and evidence.success_or_failure_label == "failure"
    )


def _promotion_runtime_profiles(
    evidence_records: tuple[EvidenceRecord, ...],
    eval_results: tuple[EvalResult, ...],
) -> tuple[str, ...]:
    profiles: list[str] = []
    for evidence in evidence_records:
        profiles.append(f"runtime:{evidence.runtime.name}")
        if evidence.runtime.model is not None:
            profiles.append(f"model:{evidence.runtime.model}")
    profiles.extend(
        f"eval:{result.runtime_profile}"
        for result in eval_results
        if result.runtime_profile is not None
    )
    return tuple(dict.fromkeys(profiles))


def _validate_manifest(state: PromoteState) -> PromoteState:
    manifest = _state_manifest(state)
    checked = CapabilityManifest.model_validate(manifest)
    return PromoteState(manifest=checked)


def _write_capability(state: PromoteState) -> PromoteState:
    request = _state_request(state)
    manifest = _state_manifest(state)
    paths = write_capability_package(manifest, request.capabilities_dir)
    manifest_path = paths.capability_path
    return PromoteState(manifest_path=manifest_path)


def _summarize(state: PromoteState) -> PromoteState:
    manifest = _state_manifest(state)
    manifest_path = _state_manifest_path(state)
    summary = PromoteSummary(
        capability_name=manifest.name,
        manifest_path=str(manifest_path),
        package_path=str(manifest_path.parent),
        capability_path=str(manifest_path),
        instructions_path=str(manifest_path.parent / "instructions.md"),
        harness_path=str(manifest_path.parent / "harness.yaml"),
        card_path=str(manifest_path.parent / "README.md"),
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
