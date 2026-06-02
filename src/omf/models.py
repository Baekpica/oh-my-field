from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict

type ArtifactKind = Literal[
    "evidence",
    "capability",
    "replay",
    "eval",
    "review",
    "regression",
    "learning",
]
type ReviewDecision = Literal[
    "approve",
    "reject",
    "revise",
    "add_context",
    "change_goal",
    "change_constraint",
    "mark_reusable",
    "mark_unsafe",
    "create_regression_case",
]
type LearningPurpose = Literal[
    "prompt_improvement",
    "eval_set",
    "fine_tuning_candidate",
]


class RuntimeInfo(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    platform: str
    python_version: str


class CommandResult(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    command: str
    args: tuple[str, ...]
    cwd: str
    exit_code: int
    duration_ms: int
    stdout: str
    stderr: str


class ArtifactEvidence(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    path: str
    exists: bool
    sha256: str | None
    size_bytes: int | None


class HarnessCheckResult(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    name: str
    command_result: CommandResult
    status: Literal["pass", "fail"]


class GitInfo(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    is_repository: bool
    repository_root: str | None
    head_sha: str | None
    branch: str | None
    dirty: bool
    changed_files: tuple[str, ...]
    diff_sha256: str | None


class EvidenceRecord(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["omf.evidence.v1"] = "omf.evidence.v1"
    run_id: str
    goal: str
    status: Literal["pass", "fail"]
    created_at: str
    runtime: RuntimeInfo
    command_result: CommandResult
    artifacts: tuple[ArtifactEvidence, ...]
    harness_results: tuple[HarnessCheckResult, ...] = ()
    git: GitInfo | None = None


class CapabilityManifest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["omf.capability.v1"] = "omf.capability.v1"
    name: str
    version: str
    created_at: str
    source_evidence_path: str
    source_evidence_sha256: str
    goal: str
    command: str
    cwd: str
    success_exit_code: int
    required_artifacts: tuple[ArtifactEvidence, ...]
    required_checks: tuple[str, ...] = ()


class ReplayCheck(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    name: str
    status: Literal["pass", "fail"]
    detail: str


class ReplayTiming(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    command_duration_ms: int
    harness_duration_ms: int
    total_command_and_harness_duration_ms: int


class ReplayResult(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["omf.replay.v1"] = "omf.replay.v1"
    replay_id: str
    capability_name: str
    status: Literal["pass", "fail"]
    created_at: str
    manifest_path: str
    manifest_sha256: str
    evidence_path: str
    evidence_sha256: str
    checks: tuple[ReplayCheck, ...]
    timing: ReplayTiming


class EvalTimingSummary(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    command_duration_ms_min: int
    command_duration_ms_max: int
    command_duration_ms_mean: float
    harness_duration_ms_total: int
    total_command_and_harness_duration_ms: int


class EvalResult(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["omf.eval.v1"] = "omf.eval.v1"
    eval_id: str
    capability_name: str
    status: Literal["pass", "fail"]
    created_at: str
    runs: int
    pass_count: int
    pass_rate: float
    timing: EvalTimingSummary
    replay_results: tuple[ReplayResult, ...]


class StoreIndexEntry(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    kind: ArtifactKind
    path: str
    name: str
    status: str
    validated: bool


class StoreIndex(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["omf.store_index.v1"] = "omf.store_index.v1"
    store_dir: str
    entries: tuple[StoreIndexEntry, ...]


class SearchMatch(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    kind: ArtifactKind
    path: str
    name: str
    status: str
    validated: bool
    score: int
    snippets: tuple[str, ...]


class StoreSearchResult(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["omf.store_search.v1"] = "omf.store_search.v1"
    store_dir: str
    query: str
    matches: tuple[SearchMatch, ...]


class ReviewRecord(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["omf.review.v1"] = "omf.review.v1"
    review_id: str
    created_at: str
    reviewer: str
    decision: ReviewDecision
    note: str
    reviewed_artifact_path: str
    reviewed_artifact_sha256: str
    reviewed_artifact_type: ArtifactKind
    reviewed_artifact_status: str


class RegressionCaseRecord(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["omf.regression_case.v1"] = "omf.regression_case.v1"
    case_id: str
    name: str
    reason: str
    created_at: str
    source_artifact_path: str
    source_artifact_sha256: str
    source_artifact_type: ArtifactKind
    source_artifact_status: str
    manifest_path: str
    manifest_sha256: str
    capability_name: str
    status: Literal["pass", "fail"]
    replay_result: ReplayResult


class LearningExportItem(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    source_artifact_path: str
    source_artifact_sha256: str
    source_artifact_type: ArtifactKind
    source_artifact_status: str
    label: str
    note: str


class LearningExportManifest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["omf.learning_export.v1"] = "omf.learning_export.v1"
    export_id: str
    created_at: str
    name: str
    purpose: LearningPurpose
    output_jsonl_path: str
    output_jsonl_sha256: str
    item_count: int
    items: tuple[LearningExportItem, ...]


class InspectResult(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["omf.inspect.v1"] = "omf.inspect.v1"
    path: str
    artifact_type: ArtifactKind
    status: str
    summary: dict[str, str | int | float | bool]
