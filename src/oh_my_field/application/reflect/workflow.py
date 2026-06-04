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
    EVIDENCE_ID_PATTERN,
    CapabilityManifest,
    EvalResult,
    EvidenceRecord,
    ReflectionReport,
    StrictModel,
)
from oh_my_field.storage import (
    list_eval_results,
    load_eval_result,
    load_evidence,
    load_manifest,
    write_reflection_report,
)

REFLECT_NODES: Final = (
    "load_manifest",
    "load_source_evidence",
    "load_eval",
    "build_reflection",
    "validate_reflection",
    "write_reflection",
    "summarize",
)

type Clock = Callable[[], datetime]
type TokenFactory = Callable[[], str]


class ReflectError(Exception):
    pass


@dataclass
class ReflectStateError(ReflectError):
    key: str

    def __str__(self) -> str:
        return f"reflect workflow state missing {self.key!r}"


@dataclass
class CapabilityNameMismatchError(ReflectError):
    requested_name: str
    manifest_name: str

    def __str__(self) -> str:
        return (
            f"manifest name {self.manifest_name!r} does not match requested "
            f"capability {self.requested_name!r}"
        )


@dataclass(frozen=True, slots=True)
class ReflectDependencies:
    clock: Clock
    token_factory: TokenFactory


class ReflectRequest(StrictModel):
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    eval_id: str | None = Field(default=None, pattern=EVIDENCE_ID_PATTERN)
    capabilities_dir: Path
    evidence_dir: Path
    eval_dir: Path
    reflection_dir: Path
    notes: tuple[str, ...] = ()


class ReflectSummary(StrictModel):
    reflection_id: str
    reflection_path: str
    capability_name: str
    eval_id: str | None = None


class ReflectState(TypedDict, total=False):
    request: ReflectRequest
    dependencies: ReflectDependencies
    manifest: CapabilityManifest
    source_evidence: EvidenceRecord
    eval_result: EvalResult | None
    report: ReflectionReport
    report_path: Path
    summary: ReflectSummary


def run_reflect_workflow(
    request: ReflectRequest,
    dependencies: ReflectDependencies | None = None,
) -> ReflectSummary:
    graph = _build_reflect_graph()
    initial_state = ReflectState(
        request=request,
        dependencies=dependencies or _default_dependencies(),
    )
    final_state = graph.invoke(initial_state)
    return _state_summary(final_state)


def _build_reflect_graph() -> CompiledStateGraph[
    ReflectState,
    None,
    ReflectState,
    ReflectState,
]:
    builder: StateGraph[ReflectState, None, ReflectState, ReflectState] = StateGraph(
        ReflectState,
    )
    builder.add_node("load_manifest", _load_manifest)
    builder.add_node("load_source_evidence", _load_source_evidence)
    builder.add_node("load_eval", _load_eval)
    builder.add_node("build_reflection", _build_reflection)
    builder.add_node("validate_reflection", _validate_reflection)
    builder.add_node("write_reflection", _write_reflection)
    builder.add_node("summarize", _summarize)
    builder.add_edge(START, "load_manifest")
    builder.add_edge("load_manifest", "load_source_evidence")
    builder.add_edge("load_source_evidence", "load_eval")
    builder.add_edge("load_eval", "build_reflection")
    builder.add_edge("build_reflection", "validate_reflection")
    builder.add_edge("validate_reflection", "write_reflection")
    builder.add_edge("write_reflection", "summarize")
    builder.add_edge("summarize", END)
    return builder.compile()


def _default_dependencies() -> ReflectDependencies:
    return ReflectDependencies(clock=_now_utc, token_factory=_token_suffix)


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _token_suffix() -> str:
    return secrets.token_hex(4)


def _load_manifest(state: ReflectState) -> ReflectState:
    request = _state_request(state)
    manifest = load_manifest(request.capability_name, request.capabilities_dir)
    if manifest.name != request.capability_name:
        raise CapabilityNameMismatchError(
            requested_name=request.capability_name,
            manifest_name=manifest.name,
        )
    return ReflectState(manifest=manifest)


def _load_source_evidence(state: ReflectState) -> ReflectState:
    request = _state_request(state)
    manifest = _state_manifest(state)
    evidence = load_evidence(manifest.source_evidence_id, request.evidence_dir)
    return ReflectState(source_evidence=evidence)


def _load_eval(state: ReflectState) -> ReflectState:
    request = _state_request(state)
    if request.eval_id is not None:
        eval_result = load_eval_result(request.eval_id, request.eval_dir)
        return ReflectState(eval_result=eval_result)
    matching = tuple(
        result
        for result in list_eval_results(request.eval_dir)
        if result.capability_name == request.capability_name
    )
    if not matching:
        return ReflectState(eval_result=None)
    latest = max(matching, key=lambda result: result.created_at)
    return ReflectState(eval_result=latest)


def _build_reflection(state: ReflectState) -> ReflectState:
    dependencies = _state_dependencies(state)
    request = _state_request(state)
    evidence = _state_source_evidence(state)
    eval_result = state.get("eval_result")
    created_at = dependencies.clock().astimezone(UTC)
    categories = _failure_categories(evidence, eval_result)
    report = ReflectionReport(
        id=f"{created_at:%Y%m%dT%H%M%SZ}-{dependencies.token_factory()}",
        created_at=created_at,
        capability_name=request.capability_name,
        source_evidence_id=evidence.id,
        eval_id=None if eval_result is None else eval_result.id,
        failure_categories=categories,
        retry_strategy=_retry_strategy(categories),
        context_additions=_context_additions(evidence, eval_result),
        prompt_patches=_prompt_patches(eval_result),
        tool_call_revisions=_tool_call_revisions(evidence, eval_result),
        notes=request.notes,
    )
    return ReflectState(report=report)


def _validate_reflection(state: ReflectState) -> ReflectState:
    report = _state_report(state)
    checked = ReflectionReport.model_validate(report)
    return ReflectState(report=checked)


def _write_reflection(state: ReflectState) -> ReflectState:
    request = _state_request(state)
    report = _state_report(state)
    report_path = write_reflection_report(report, request.reflection_dir)
    return ReflectState(report_path=report_path)


def _summarize(state: ReflectState) -> ReflectState:
    report = _state_report(state)
    report_path = _state_report_path(state)
    summary = ReflectSummary(
        reflection_id=report.id,
        reflection_path=str(report_path),
        capability_name=report.capability_name,
        eval_id=report.eval_id,
    )
    return ReflectState(summary=summary)


def _failure_categories(
    evidence: EvidenceRecord,
    eval_result: EvalResult | None,
) -> tuple[str, ...]:
    categories: list[str] = []
    if evidence.harness.status == "fail":
        categories.append("source_harness")
    if evidence.errors:
        categories.append("source_error")
    if any(execution.exit_code != 0 for execution in evidence.command_executions):
        categories.append("source_command")
    if eval_result is not None:
        if eval_result.status == "fail":
            categories.append("eval_harness")
        if any(
            execution.exit_code != 0 for execution in eval_result.command_executions
        ):
            categories.append("eval_command")
        if any(item.status == "fail" for item in eval_result.checklist_items):
            categories.append("checklist")
        if any(score.status == "fail" for score in eval_result.rubric_scores):
            categories.append("rubric")
    return tuple(dict.fromkeys(categories))


def _retry_strategy(categories: tuple[str, ...]) -> str:
    if not categories:
        return "No retry needed; preserve the successful evidence as a baseline."
    return (
        "Retry after addressing "
        f"{', '.join(categories)} and rerun the capability harness."
    )


def _context_additions(
    evidence: EvidenceRecord,
    eval_result: EvalResult | None,
) -> tuple[str, ...]:
    additions = [f"Investigate source error: {error}" for error in evidence.errors]
    if eval_result is not None:
        additions.extend(
            f"Investigate eval failure: {failure}" for failure in eval_result.failures
        )
    return tuple(additions)


def _prompt_patches(eval_result: EvalResult | None) -> tuple[str, ...]:
    if eval_result is None:
        return ()
    patches = [
        f"Add checklist requirement: {item.name}"
        for item in eval_result.checklist_items
        if item.status == "fail"
    ]
    patches.extend(
        f"Improve rubric dimension {score.name} to at least {score.pass_threshold:g}"
        for score in eval_result.rubric_scores
        if score.status == "fail"
    )
    return tuple(patches)


def _tool_call_revisions(
    evidence: EvidenceRecord,
    eval_result: EvalResult | None,
) -> tuple[str, ...]:
    revisions = [
        f"Revise source command: {execution.command}"
        for execution in evidence.command_executions
        if execution.exit_code != 0
    ]
    if eval_result is not None:
        revisions.extend(
            f"Revise harness command: {execution.command}"
            for execution in eval_result.command_executions
            if execution.exit_code != 0
        )
    return tuple(revisions)


def _state_request(state: ReflectState) -> ReflectRequest:
    request = state.get("request")
    if request is None:
        raise ReflectStateError(key="request")
    return request


def _state_dependencies(state: ReflectState) -> ReflectDependencies:
    dependencies = state.get("dependencies")
    if dependencies is None:
        raise ReflectStateError(key="dependencies")
    return dependencies


def _state_manifest(state: ReflectState) -> CapabilityManifest:
    manifest = state.get("manifest")
    if manifest is None:
        raise ReflectStateError(key="manifest")
    return manifest


def _state_source_evidence(state: ReflectState) -> EvidenceRecord:
    evidence = state.get("source_evidence")
    if evidence is None:
        raise ReflectStateError(key="source_evidence")
    return evidence


def _state_report(state: ReflectState) -> ReflectionReport:
    report = state.get("report")
    if report is None:
        raise ReflectStateError(key="report")
    return report


def _state_report_path(state: ReflectState) -> Path:
    report_path = state.get("report_path")
    if report_path is None:
        raise ReflectStateError(key="report_path")
    return report_path


def _state_summary(state: ReflectState) -> ReflectSummary:
    summary = state.get("summary")
    if summary is None:
        raise ReflectStateError(key="summary")
    return summary
