import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import Field

from oh_my_field.integrity import append_integrity_link, integrity_link
from oh_my_field.models import (
    CAPABILITY_NAME_PATTERN,
    ArtifactIntegrityLink,
    CapabilityManifest,
    CapturedTextFile,
    EvidenceRecord,
    LearningExport,
    StrictModel,
)
from oh_my_field.storage import load_evidence, load_manifest, write_learning_export

LEARN_NODES: Final = (
    "load_manifest",
    "load_source_evidence",
    "build_learning_export",
    "validate_learning_export",
    "write_learning_export",
    "summarize",
)

type Clock = Callable[[], datetime]
type TokenFactory = Callable[[], str]


class LearnError(Exception):
    pass


@dataclass
class LearnStateError(LearnError):
    key: str

    def __str__(self) -> str:
        return f"learn workflow state missing {self.key!r}"


@dataclass(frozen=True, slots=True)
class LearnDependencies:
    clock: Clock
    token_factory: TokenFactory


class LearnRequest(StrictModel):
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    capabilities_dir: Path
    evidence_dir: Path
    learning_dir: Path


class LearnSummary(StrictModel):
    learning_id: str
    learning_path: str
    capability_name: str


class LearnState(TypedDict, total=False):
    request: LearnRequest
    dependencies: LearnDependencies
    manifest: CapabilityManifest
    source_evidence: EvidenceRecord
    export: LearningExport
    export_path: Path
    summary: LearnSummary


def run_learn_workflow(
    request: LearnRequest,
    dependencies: LearnDependencies | None = None,
) -> LearnSummary:
    graph = _build_learn_graph()
    initial_state = LearnState(
        request=request,
        dependencies=dependencies or _default_dependencies(),
    )
    final_state = graph.invoke(initial_state)
    return _state_summary(final_state)


def _build_learn_graph() -> CompiledStateGraph[
    LearnState,
    None,
    LearnState,
    LearnState,
]:
    builder: StateGraph[LearnState, None, LearnState, LearnState] = StateGraph(
        LearnState,
    )
    builder.add_node("load_manifest", _load_manifest)
    builder.add_node("load_source_evidence", _load_source_evidence)
    builder.add_node("build_learning_export", _build_learning_export)
    builder.add_node("validate_learning_export", _validate_learning_export)
    builder.add_node("write_learning_export", _write_learning_export)
    builder.add_node("summarize", _summarize)
    builder.add_edge(START, "load_manifest")
    builder.add_edge("load_manifest", "load_source_evidence")
    builder.add_edge("load_source_evidence", "build_learning_export")
    builder.add_edge("build_learning_export", "validate_learning_export")
    builder.add_edge("validate_learning_export", "write_learning_export")
    builder.add_edge("write_learning_export", "summarize")
    builder.add_edge("summarize", END)
    return builder.compile()


def _default_dependencies() -> LearnDependencies:
    return LearnDependencies(clock=_now_utc, token_factory=_token_suffix)


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _token_suffix() -> str:
    return secrets.token_hex(4)


def _load_manifest(state: LearnState) -> LearnState:
    request = _state_request(state)
    manifest = load_manifest(request.capability_name, request.capabilities_dir)
    return LearnState(manifest=manifest)


def _load_source_evidence(state: LearnState) -> LearnState:
    request = _state_request(state)
    manifest = _state_manifest(state)
    evidence = load_evidence(manifest.source_evidence_id, request.evidence_dir)
    return LearnState(source_evidence=evidence)


def _build_learning_export(state: LearnState) -> LearnState:
    dependencies = _state_dependencies(state)
    request = _state_request(state)
    evidence = _state_source_evidence(state)
    created_at = dependencies.clock().astimezone(UTC)
    prompt_improvement_candidates = (
        *evidence.improvement_notes,
        *_feedback_candidates(evidence),
    )
    regression_eval_candidates = (
        *evidence.errors,
        *evidence.harness.failures,
    )
    few_shot_examples = _few_shot_examples(evidence.files)
    preference_signals = (
        *evidence.feedback,
        *evidence.user_interventions,
        *evidence.human_review.notes,
    )
    export = LearningExport(
        id=f"{created_at:%Y%m%dT%H%M%SZ}-{dependencies.token_factory()}",
        created_at=created_at,
        capability_name=request.capability_name,
        source_evidence_id=evidence.id,
        prompt_improvement_candidates=prompt_improvement_candidates,
        regression_eval_candidates=regression_eval_candidates,
        few_shot_examples=few_shot_examples,
        preference_signals=preference_signals,
        prompt_patches=_prompt_patches(prompt_improvement_candidates),
        eval_set_candidates=_eval_set_candidates(
            goal=evidence.normalized_goal or evidence.goal,
            regression_eval_candidates=regression_eval_candidates,
        ),
        fine_tuning_candidates=few_shot_examples,
        preference_dataset_candidates=preference_signals,
    )
    export = export.model_copy(
        update={"integrity_chain": (_evidence_integrity_link(evidence),)},
    )
    export = append_integrity_link(
        export,
        artifact_type="learning",
        artifact_id=export.id,
        previous_sha256=export.integrity_chain[-1].sha256,
    )
    return LearnState(export=export)


def _validate_learning_export(state: LearnState) -> LearnState:
    export = _state_export(state)
    checked = LearningExport.model_validate(export)
    return LearnState(export=checked)


def _write_learning_export(state: LearnState) -> LearnState:
    request = _state_request(state)
    export = _state_export(state)
    export_path = write_learning_export(export, request.learning_dir)
    return LearnState(export_path=export_path)


def _summarize(state: LearnState) -> LearnState:
    export = _state_export(state)
    export_path = _state_export_path(state)
    summary = LearnSummary(
        learning_id=export.id,
        learning_path=str(export_path),
        capability_name=export.capability_name,
    )
    return LearnState(summary=summary)


def _feedback_candidates(evidence: EvidenceRecord) -> tuple[str, ...]:
    if evidence.success_or_failure_label != "failure":
        return ()
    return evidence.feedback


def _few_shot_examples(files: tuple[CapturedTextFile, ...]) -> tuple[str, ...]:
    prompts = [file.content for file in files if file.role == "prompt"]
    outputs = [
        file.content
        for file in files
        if file.role in {"command_output", "test_result", "artifact"}
    ]
    if not prompts or not outputs:
        return ()
    return tuple(
        f"input:\n{prompt}\n\noutput:\n{output}"
        for prompt in prompts
        for output in outputs
    )


def _prompt_patches(candidates: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(f"Add instruction: {candidate}" for candidate in candidates)


def _eval_set_candidates(
    *,
    goal: str,
    regression_eval_candidates: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(
        f"goal: {goal}\nregression: {candidate}"
        for candidate in regression_eval_candidates
    )


def _evidence_integrity_link(evidence: EvidenceRecord) -> ArtifactIntegrityLink:
    if evidence.integrity_chain:
        return evidence.integrity_chain[-1]
    return integrity_link(
        artifact_type="evidence",
        artifact_id=evidence.id,
        model=evidence,
    )


def _state_request(state: LearnState) -> LearnRequest:
    request = state.get("request")
    if request is None:
        raise LearnStateError(key="request")
    return request


def _state_dependencies(state: LearnState) -> LearnDependencies:
    dependencies = state.get("dependencies")
    if dependencies is None:
        raise LearnStateError(key="dependencies")
    return dependencies


def _state_manifest(state: LearnState) -> CapabilityManifest:
    manifest = state.get("manifest")
    if manifest is None:
        raise LearnStateError(key="manifest")
    return manifest


def _state_source_evidence(state: LearnState) -> EvidenceRecord:
    evidence = state.get("source_evidence")
    if evidence is None:
        raise LearnStateError(key="source_evidence")
    return evidence


def _state_export(state: LearnState) -> LearningExport:
    export = state.get("export")
    if export is None:
        raise LearnStateError(key="export")
    return export


def _state_export_path(state: LearnState) -> Path:
    export_path = state.get("export_path")
    if export_path is None:
        raise LearnStateError(key="export_path")
    return export_path


def _state_summary(state: LearnState) -> LearnSummary:
    summary = state.get("summary")
    if summary is None:
        raise LearnStateError(key="summary")
    return summary
