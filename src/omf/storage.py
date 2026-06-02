from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast
from uuid import uuid4

from pydantic import ValidationError

from omf.models import (
    ArtifactEvidence,
    ArtifactKind,
    CapabilityManifest,
    CommandResult,
    EvalResult,
    EvalTimingSummary,
    EvidenceRecord,
    GitInfo,
    HarnessCheckResult,
    InspectResult,
    LearningExportItem,
    LearningExportManifest,
    LearningPurpose,
    RegressionCaseRecord,
    ReplayCheck,
    ReplayResult,
    ReplayTiming,
    ReviewDecision,
    ReviewRecord,
    RuntimeInfo,
    SearchMatch,
    StoreIndex,
    StoreIndexEntry,
    StoreSearchResult,
)

ARTIFACT_KINDS: tuple[ArtifactKind, ...] = (
    "evidence",
    "capability",
    "replay",
    "eval",
    "review",
    "regression",
    "learning",
)
LEARNING_PURPOSES = (
    "prompt_improvement",
    "eval_set",
    "fine_tuning_candidate",
)
REVIEW_DECISIONS: tuple[ReviewDecision, ...] = (
    "approve",
    "reject",
    "revise",
    "add_context",
    "change_goal",
    "change_constraint",
    "mark_reusable",
    "mark_unsafe",
    "create_regression_case",
)


class OmfError(Exception):
    @classmethod
    def expected_json_object(cls, path: Path) -> OmfError:
        return cls(f"Expected JSON object: {path}")

    @classmethod
    def invalid_capability_name(cls) -> OmfError:
        return cls("Capability name must contain at least one alphanumeric character")

    @classmethod
    def empty_command(cls) -> OmfError:
        return cls("Command must not be empty")

    @classmethod
    def invalid_evidence(cls, path: Path, error: ValidationError) -> OmfError:
        return cls(f"Invalid evidence record: {path}: {error}")

    @classmethod
    def evidence_record_mismatch(cls, path: Path) -> OmfError:
        return cls(f"Evidence record does not match command, harness, or artifact results: {path}")

    @classmethod
    def evidence_artifact_missing(cls, path: Path) -> OmfError:
        return cls(f"Evidence artifact does not exist: {path}")

    @classmethod
    def evidence_artifact_hash_mismatch(cls, path: Path) -> OmfError:
        return cls(f"Evidence artifact hash does not match evidence record: {path}")

    @classmethod
    def invalid_manifest(cls, path: Path, error: ValidationError) -> OmfError:
        return cls(f"Invalid capability manifest: {path}: {error}")

    @classmethod
    def expected_capability_manifest(cls, path: Path, actual: ArtifactKind) -> OmfError:
        return cls(f"Expected capability manifest, got {actual}: {path}")

    @classmethod
    def missing_source_evidence(cls, path: Path) -> OmfError:
        return cls(f"Capability source evidence does not exist: {path}")

    @classmethod
    def source_evidence_hash_mismatch(cls, path: Path) -> OmfError:
        return cls(f"Capability source evidence hash does not match manifest: {path}")

    @classmethod
    def source_evidence_not_passing(cls, path: Path) -> OmfError:
        return cls(f"Capability source evidence is not passing: {path}")

    @classmethod
    def source_evidence_manifest_mismatch(cls, path: Path) -> OmfError:
        return cls(f"Capability manifest does not match source evidence: {path}")

    @classmethod
    def missing_replay_manifest(cls, path: Path) -> OmfError:
        return cls(f"Replay capability manifest does not exist: {path}")

    @classmethod
    def replay_manifest_hash_mismatch(cls, path: Path) -> OmfError:
        return cls(f"Replay capability manifest hash does not match replay record: {path}")

    @classmethod
    def missing_replay_evidence(cls, path: Path) -> OmfError:
        return cls(f"Replay evidence does not exist: {path}")

    @classmethod
    def replay_evidence_hash_mismatch(cls, path: Path) -> OmfError:
        return cls(f"Replay evidence hash does not match replay record: {path}")

    @classmethod
    def replay_record_mismatch(cls, path: Path) -> OmfError:
        return cls(f"Replay record does not match manifest and evidence: {path}")

    @classmethod
    def eval_record_mismatch(cls, path: Path) -> OmfError:
        return cls(f"Eval record does not match replay results: {path}")

    @classmethod
    def cannot_promote_failed_evidence(cls) -> OmfError:
        return cls("Only passing evidence can be promoted to a capability")

    @classmethod
    def cannot_promote_missing_artifacts(cls, missing_artifacts: list[str]) -> OmfError:
        joined = ", ".join(missing_artifacts)
        return cls(f"Cannot promote evidence with missing artifacts: {joined}")

    @classmethod
    def invalid_eval_runs(cls) -> OmfError:
        return cls("Eval runs must be greater than 0")

    @classmethod
    def empty_search_query(cls) -> OmfError:
        return cls("Search query must not be empty")

    @classmethod
    def unsupported_artifact_kind(cls, kind: str) -> OmfError:
        return cls(f"Unsupported artifact kind: {kind}")

    @classmethod
    def search_artifact_kind_mismatch(
        cls,
        *,
        expected: ArtifactKind,
        actual: ArtifactKind,
        path: Path,
    ) -> OmfError:
        message = (
            "Search artifact kind does not match store location: "
            f"expected {expected}, got {actual}: {path}"
        )
        return cls(
            message
        )

    @classmethod
    def list_artifact_kind_mismatch(
        cls,
        *,
        expected: ArtifactKind,
        actual: ArtifactKind,
        path: Path,
    ) -> OmfError:
        message = (
            "List artifact kind does not match store location: "
            f"expected {expected}, got {actual}: {path}"
        )
        return cls(message)

    @classmethod
    def empty_reviewer(cls) -> OmfError:
        return cls("Reviewer must not be empty")

    @classmethod
    def empty_review_note(cls) -> OmfError:
        return cls("Review note must not be empty")

    @classmethod
    def unsupported_review_decision(cls, decision: str) -> OmfError:
        return cls(f"Unsupported review decision: {decision}")

    @classmethod
    def missing_reviewed_artifact(cls, path: Path) -> OmfError:
        return cls(f"Reviewed artifact does not exist: {path}")

    @classmethod
    def reviewed_artifact_hash_mismatch(cls, path: Path) -> OmfError:
        return cls(f"Reviewed artifact hash does not match review record: {path}")

    @classmethod
    def reviewed_artifact_record_mismatch(cls, path: Path) -> OmfError:
        return cls(f"Reviewed artifact type or status does not match review record: {path}")

    @classmethod
    def empty_regression_reason(cls) -> OmfError:
        return cls("Regression case reason must not be empty")

    @classmethod
    def missing_regression_source_artifact(cls, path: Path) -> OmfError:
        return cls(f"Regression source artifact does not exist: {path}")

    @classmethod
    def regression_source_artifact_hash_mismatch(cls, path: Path) -> OmfError:
        return cls(f"Regression source artifact hash does not match case record: {path}")

    @classmethod
    def missing_regression_manifest(cls, path: Path) -> OmfError:
        return cls(f"Regression capability manifest does not exist: {path}")

    @classmethod
    def regression_manifest_hash_mismatch(cls, path: Path) -> OmfError:
        return cls(f"Regression capability manifest hash does not match case record: {path}")

    @classmethod
    def regression_record_mismatch(cls, path: Path) -> OmfError:
        return cls(f"Regression case links do not match inspected artifacts: {path}")

    @classmethod
    def empty_learning_sources(cls) -> OmfError:
        return cls("Learning export requires at least one source artifact")

    @classmethod
    def unsupported_learning_purpose(cls, purpose: str) -> OmfError:
        return cls(f"Unsupported learning export purpose: {purpose}")

    @classmethod
    def empty_learning_note(cls) -> OmfError:
        return cls("Learning export note must not be empty")

    @classmethod
    def missing_learning_jsonl(cls, path: Path) -> OmfError:
        return cls(f"Learning export JSONL does not exist: {path}")

    @classmethod
    def invalid_learning_jsonl(cls, path: Path, error: ValidationError) -> OmfError:
        return cls(f"Invalid learning export JSONL: {path}: {error}")

    @classmethod
    def learning_jsonl_hash_mismatch(cls, path: Path) -> OmfError:
        return cls(f"Learning export JSONL hash does not match manifest: {path}")

    @classmethod
    def learning_jsonl_item_mismatch(cls, path: Path) -> OmfError:
        return cls(f"Learning export JSONL items do not match manifest: {path}")

    @classmethod
    def learning_item_count_mismatch(cls, path: Path) -> OmfError:
        return cls(f"Learning export item count does not match JSONL rows: {path}")


@dataclass(frozen=True, slots=True)
class CaptureRequest:
    goal: str
    command: str
    artifacts: tuple[str, ...]
    store_dir: Path
    cwd: Path
    checks: tuple[str, ...] = ()
    run_id_prefix: str = "run"


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def new_id(prefix: str) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}-{timestamp}-{uuid4().hex[:8]}"


def ensure_store(store_dir: Path) -> None:
    for child in (
        "evidence",
        "capabilities",
        "replays",
        "evals",
        "reviews",
        "regressions",
        "learning",
    ):
        (store_dir / child).mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(payload + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, object]:
    loaded = cast("object", json.loads(path.read_text(encoding="utf-8")))
    if not isinstance(loaded, dict):
        raise OmfError.expected_json_object(path)
    return cast("dict[str, object]", loaded)


def resolve_manifest_reference(manifest_path: Path, reference: str) -> Path:
    referenced_path = Path(reference)
    if referenced_path.is_absolute():
        return referenced_path
    return manifest_path.parent / referenced_path


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    chars: list[str] = []
    previous_dash = False
    for char in lowered:
        if char.isalnum():
            chars.append(char)
            previous_dash = False
        elif not previous_dash:
            chars.append("-")
            previous_dash = True
    slug = "".join(chars).strip("-")
    if not slug:
        raise OmfError.invalid_capability_name()
    return slug


def resolve_artifact(cwd: Path, artifact: str) -> Path:
    path = Path(artifact)
    if path.is_absolute():
        return path
    return cwd / path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_artifact(cwd: Path, artifact: str) -> ArtifactEvidence:
    path = resolve_artifact(cwd, artifact)
    if not path.is_file():
        return ArtifactEvidence(path=artifact, exists=False, sha256=None, size_bytes=None)
    return ArtifactEvidence(
        path=artifact,
        exists=True,
        sha256=sha256_file(path),
        size_bytes=path.stat().st_size,
    )


def runtime_info() -> RuntimeInfo:
    label = f"{platform.system()} {platform.release()} {platform.machine()}"
    return RuntimeInfo(platform=label, python_version=sys.version.split()[0])


def run_git(args: tuple[str, ...], cwd: Path) -> subprocess.CompletedProcess[str]:
    git_executable = shutil.which("git")
    if git_executable is None:
        missing_executable = "git"
        raise FileNotFoundError(missing_executable)
    return subprocess.run(  # noqa: S603 - fixed git introspection command.
        (git_executable, *args),
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )


def git_stdout(args: tuple[str, ...], cwd: Path) -> str | None:
    try:
        result = run_git(args, cwd)
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def git_diff_sha256(cwd: Path) -> str | None:
    try:
        unstaged = run_git(("diff", "--binary"), cwd)
        staged = run_git(("diff", "--cached", "--binary"), cwd)
    except FileNotFoundError:
        return None
    if unstaged.returncode != 0 or staged.returncode != 0:
        return None
    payload = f"{unstaged.stdout}\n{staged.stdout}"
    if not payload:
        return None
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def git_changed_files(cwd: Path) -> tuple[str, ...]:
    status_output = git_stdout(("status", "--porcelain"), cwd)
    if status_output is None:
        return ()
    changed_files: list[str] = []
    for line in status_output.splitlines():
        if not line:
            continue
        path = line[2:].strip()
        if " -> " in path:
            path = path.split(" -> ", maxsplit=1)[1]
        changed_files.append(path)
    return tuple(changed_files)


def collect_git_info(cwd: Path) -> GitInfo:
    root = git_stdout(("rev-parse", "--show-toplevel"), cwd)
    if root is None:
        return GitInfo(
            is_repository=False,
            repository_root=None,
            head_sha=None,
            branch=None,
            dirty=False,
            changed_files=(),
            diff_sha256=None,
        )
    changed_files = git_changed_files(cwd)
    return GitInfo(
        is_repository=True,
        repository_root=root,
        head_sha=git_stdout(("rev-parse", "--verify", "HEAD"), cwd),
        branch=git_stdout(("branch", "--show-current"), cwd),
        dirty=bool(changed_files),
        changed_files=changed_files,
        diff_sha256=git_diff_sha256(cwd),
    )


def run_command(command: str, cwd: Path) -> CommandResult:
    if not command.strip():
        raise OmfError.empty_command()
    shell_path = os.environ.get("SHELL") or shutil.which("sh") or "/bin/sh"
    args = (shell_path, "-c", command)

    started = time.monotonic()
    try:
        result = subprocess.run(  # noqa: S603 - user shell command execution is the feature.
            args,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )
        exit_code = result.returncode
        stdout = result.stdout
        stderr = result.stderr
    except FileNotFoundError as error:
        exit_code = 127
        stdout = ""
        stderr = str(error)

    duration_ms = int((time.monotonic() - started) * 1000)
    return CommandResult(
        command=command,
        args=args,
        cwd=str(cwd.resolve()),
        exit_code=exit_code,
        duration_ms=duration_ms,
        stdout=stdout,
        stderr=stderr,
    )


def run_harness_checks(checks: tuple[str, ...], cwd: Path) -> tuple[HarnessCheckResult, ...]:
    results: list[HarnessCheckResult] = []
    for index, check in enumerate(checks, start=1):
        command_result = run_command(check, cwd)
        results.append(
            HarnessCheckResult(
                name=f"check-{index}",
                command_result=command_result,
                status="pass" if command_result.exit_code == 0 else "fail",
            )
        )
    return tuple(results)


def capture_evidence(request: CaptureRequest) -> tuple[EvidenceRecord, Path]:
    ensure_store(request.store_dir)
    resolved_cwd = request.cwd.resolve()
    command_result = run_command(request.command, resolved_cwd)
    artifact_records = tuple(
        inspect_artifact(resolved_cwd, artifact) for artifact in request.artifacts
    )
    harness_results = run_harness_checks(request.checks, resolved_cwd)
    status = (
        "pass"
        if command_result.exit_code == 0
        and all(result.status == "pass" for result in harness_results)
        else "fail"
    )
    evidence = EvidenceRecord(
        run_id=new_id(request.run_id_prefix),
        goal=request.goal,
        status=status,
        created_at=now_iso(),
        runtime=runtime_info(),
        command_result=command_result,
        artifacts=artifact_records,
        harness_results=harness_results,
        git=collect_git_info(resolved_cwd),
    )
    output_path = request.store_dir / "evidence" / f"{evidence.run_id}.json"
    write_json(output_path, evidence.model_dump_json(indent=2))
    return evidence, output_path


def load_evidence(path: Path) -> EvidenceRecord:
    try:
        evidence = EvidenceRecord.model_validate(read_json(path))
    except ValidationError as error:
        raise OmfError.invalid_evidence(path, error) from error
    validate_evidence_record(evidence, path)
    return evidence


def validate_evidence_status(evidence: EvidenceRecord, path: Path) -> None:
    for harness_result in evidence.harness_results:
        expected_harness_status = (
            "pass" if harness_result.command_result.exit_code == 0 else "fail"
        )
        if harness_result.status != expected_harness_status:
            raise OmfError.evidence_record_mismatch(path)

    expected_status = (
        "pass"
        if evidence.command_result.exit_code == 0
        and all(result.status == "pass" for result in evidence.harness_results)
        else "fail"
    )
    if evidence.status != expected_status:
        raise OmfError.evidence_record_mismatch(path)


def validate_evidence_artifacts(evidence: EvidenceRecord, path: Path) -> None:
    cwd = Path(evidence.command_result.cwd)
    for artifact in evidence.artifacts:
        if not artifact.exists:
            if artifact.sha256 is not None or artifact.size_bytes is not None:
                raise OmfError.evidence_record_mismatch(path)
            continue

        if artifact.sha256 is None or artifact.size_bytes is None:
            raise OmfError.evidence_record_mismatch(path)

        artifact_path = resolve_artifact(cwd, artifact.path)
        if not artifact_path.is_file():
            raise OmfError.evidence_artifact_missing(artifact_path)
        if sha256_file(artifact_path) != artifact.sha256:
            raise OmfError.evidence_artifact_hash_mismatch(artifact_path)
        if artifact_path.stat().st_size != artifact.size_bytes:
            raise OmfError.evidence_record_mismatch(path)


def validate_evidence_record(evidence: EvidenceRecord, path: Path) -> None:
    validate_evidence_status(evidence, path)
    validate_evidence_artifacts(evidence, path)


def load_manifest(path: Path) -> CapabilityManifest:
    try:
        return CapabilityManifest.model_validate(read_json(path))
    except ValidationError as error:
        raise OmfError.invalid_manifest(path, error) from error


def load_replay(path: Path) -> ReplayResult:
    try:
        return ReplayResult.model_validate(read_json(path))
    except ValidationError as error:
        message = f"Invalid replay result: {path}: {error}"
        raise OmfError(message) from error


def load_eval(path: Path) -> EvalResult:
    try:
        return EvalResult.model_validate(read_json(path))
    except ValidationError as error:
        message = f"Invalid eval result: {path}: {error}"
        raise OmfError(message) from error


def load_review(path: Path) -> ReviewRecord:
    try:
        return ReviewRecord.model_validate(read_json(path))
    except ValidationError as error:
        message = f"Invalid review record: {path}: {error}"
        raise OmfError(message) from error


def load_regression_case(path: Path) -> RegressionCaseRecord:
    try:
        return RegressionCaseRecord.model_validate(read_json(path))
    except ValidationError as error:
        message = f"Invalid regression case record: {path}: {error}"
        raise OmfError(message) from error


def load_learning_export(path: Path) -> LearningExportManifest:
    try:
        return LearningExportManifest.model_validate(read_json(path))
    except ValidationError as error:
        message = f"Invalid learning export manifest: {path}: {error}"
        raise OmfError(message) from error


def read_learning_jsonl(path: Path) -> tuple[LearningExportItem, ...]:
    if not path.is_file():
        raise OmfError.missing_learning_jsonl(path)
    items: list[LearningExportItem] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            items.append(LearningExportItem.model_validate_json(line))
    except ValidationError as error:
        raise OmfError.invalid_learning_jsonl(path, error) from error
    return tuple(items)


def inspect_learning_export(path: Path, payload: dict[str, object]) -> InspectResult:
    learning_export = LearningExportManifest.model_validate(payload)
    jsonl_path = resolve_manifest_reference(path, learning_export.output_jsonl_path)
    if not jsonl_path.is_file():
        raise OmfError.missing_learning_jsonl(jsonl_path)
    if sha256_file(jsonl_path) != learning_export.output_jsonl_sha256:
        raise OmfError.learning_jsonl_hash_mismatch(jsonl_path)
    jsonl_items = read_learning_jsonl(jsonl_path)
    if len(jsonl_items) != learning_export.item_count:
        raise OmfError.learning_item_count_mismatch(jsonl_path)
    if jsonl_items != learning_export.items:
        raise OmfError.learning_jsonl_item_mismatch(jsonl_path)
    return InspectResult(
        path=str(path.resolve()),
        artifact_type="learning",
        status=learning_export.purpose,
        summary={
            "export_id": learning_export.export_id,
            "name": learning_export.name,
            "purpose": learning_export.purpose,
            "item_count": learning_export.item_count,
            "output_jsonl_path": str(jsonl_path.resolve()),
            "output_jsonl_sha256": learning_export.output_jsonl_sha256,
            "output_jsonl_verified": True,
        },
    )


def manifest_matches_source_evidence(
    manifest: CapabilityManifest,
    evidence: EvidenceRecord,
) -> bool:
    return (
        manifest.goal == evidence.goal
        and manifest.command == evidence.command_result.command
        and manifest.cwd == evidence.command_result.cwd
        and manifest.required_artifacts == evidence.artifacts
        and manifest.required_checks
        == tuple(result.command_result.command for result in evidence.harness_results)
    )


def inspect_capability_manifest(path: Path, payload: dict[str, object]) -> InspectResult:
    manifest = CapabilityManifest.model_validate(payload)
    evidence_path = resolve_manifest_reference(path, manifest.source_evidence_path)
    if not evidence_path.is_file():
        raise OmfError.missing_source_evidence(evidence_path)
    if sha256_file(evidence_path) != manifest.source_evidence_sha256:
        raise OmfError.source_evidence_hash_mismatch(evidence_path)
    evidence = load_evidence(evidence_path)
    if evidence.status != "pass":
        raise OmfError.source_evidence_not_passing(evidence_path)
    if not manifest_matches_source_evidence(manifest, evidence):
        raise OmfError.source_evidence_manifest_mismatch(evidence_path)
    return InspectResult(
        path=str(path.resolve()),
        artifact_type="capability",
        status="ready",
        summary={
            "name": manifest.name,
            "version": manifest.version,
            "source_evidence_sha256": manifest.source_evidence_sha256,
            "source_evidence_verified": True,
            "required_artifact_count": len(manifest.required_artifacts),
            "required_check_count": len(manifest.required_checks),
        },
    )


def load_verified_manifest(path: Path) -> CapabilityManifest:
    inspect_result = inspect_json_artifact(path)
    if inspect_result.artifact_type != "capability" or inspect_result.status != "ready":
        raise OmfError.expected_capability_manifest(path, inspect_result.artifact_type)
    return load_manifest(path)


def inspect_review_record(path: Path, payload: dict[str, object]) -> InspectResult:
    review = ReviewRecord.model_validate(payload)
    reviewed_path = resolve_manifest_reference(path, review.reviewed_artifact_path)
    if not reviewed_path.is_file():
        raise OmfError.missing_reviewed_artifact(reviewed_path)
    if reviewed_path.resolve() == path.resolve():
        raise OmfError.reviewed_artifact_record_mismatch(reviewed_path)
    if sha256_file(reviewed_path) != review.reviewed_artifact_sha256:
        raise OmfError.reviewed_artifact_hash_mismatch(reviewed_path)
    reviewed_artifact = inspect_json_artifact(reviewed_path)
    if (
        reviewed_artifact.artifact_type != review.reviewed_artifact_type
        or reviewed_artifact.status != review.reviewed_artifact_status
    ):
        raise OmfError.reviewed_artifact_record_mismatch(reviewed_path)
    return InspectResult(
        path=str(path.resolve()),
        artifact_type="review",
        status=review.decision,
        summary={
            "review_id": review.review_id,
            "reviewer": review.reviewer,
            "decision": review.decision,
            "reviewed_artifact_type": review.reviewed_artifact_type,
            "reviewed_artifact_status": review.reviewed_artifact_status,
            "reviewed_artifact_sha256": review.reviewed_artifact_sha256,
            "reviewed_artifact_verified": True,
        },
    )


def inspect_regression_case(path: Path, payload: dict[str, object]) -> InspectResult:
    regression = RegressionCaseRecord.model_validate(payload)
    source_artifact_path = resolve_manifest_reference(path, regression.source_artifact_path)
    manifest_path = resolve_manifest_reference(path, regression.manifest_path)
    if not source_artifact_path.is_file():
        raise OmfError.missing_regression_source_artifact(source_artifact_path)
    if sha256_file(source_artifact_path) != regression.source_artifact_sha256:
        raise OmfError.regression_source_artifact_hash_mismatch(source_artifact_path)
    if not manifest_path.is_file():
        raise OmfError.missing_regression_manifest(manifest_path)
    if sha256_file(manifest_path) != regression.manifest_sha256:
        raise OmfError.regression_manifest_hash_mismatch(manifest_path)

    source_artifact = inspect_json_artifact(source_artifact_path)
    manifest_result = inspect_json_artifact(manifest_path)
    if (
        source_artifact.artifact_type != regression.source_artifact_type
        or source_artifact.status != regression.source_artifact_status
        or manifest_result.artifact_type != "capability"
        or regression.replay_result.status != regression.status
    ):
        raise OmfError.regression_record_mismatch(path)
    manifest = load_manifest(manifest_path)
    if manifest.name != regression.capability_name:
        raise OmfError.regression_record_mismatch(path)
    validate_replay_result(regression.replay_result, path)

    return InspectResult(
        path=str(path.resolve()),
        artifact_type="regression",
        status=regression.status,
        summary={
            "case_id": regression.case_id,
            "name": regression.name,
            "capability_name": regression.capability_name,
            "source_artifact_type": regression.source_artifact_type,
            "source_artifact_status": regression.source_artifact_status,
            "source_artifact_sha256": regression.source_artifact_sha256,
            "source_artifact_verified": True,
            "manifest_sha256": regression.manifest_sha256,
            "manifest_verified": True,
            "replay_status": regression.replay_result.status,
        },
    )


def replay_exit_code_check(manifest: CapabilityManifest, evidence: EvidenceRecord) -> ReplayCheck:
    exit_code_status = (
        "pass" if evidence.command_result.exit_code == manifest.success_exit_code else "fail"
    )
    return ReplayCheck(
        name="exit-code",
        status=exit_code_status,
        detail=(
            f"expected {manifest.success_exit_code}, "
            f"got {evidence.command_result.exit_code}"
        ),
    )


def replay_checks_for_manifest_and_evidence(
    manifest: CapabilityManifest,
    evidence: EvidenceRecord,
) -> tuple[ReplayCheck, ...]:
    checks: list[ReplayCheck] = [replay_exit_code_check(manifest, evidence)]
    checks.extend(compare_replay_artifacts(manifest.required_artifacts, evidence.artifacts))
    checks.extend(replay_harness_checks(evidence.harness_results))
    return tuple(checks)


def replay_status_from_checks(checks: tuple[ReplayCheck, ...]) -> Literal["pass", "fail"]:
    return "pass" if all(check.status == "pass" for check in checks) else "fail"


def replay_evidence_matches_manifest(
    manifest: CapabilityManifest,
    evidence: EvidenceRecord,
) -> bool:
    return (
        evidence.command_result.command == manifest.command
        and evidence.command_result.cwd == manifest.cwd
        and tuple(artifact.path for artifact in evidence.artifacts)
        == tuple(artifact.path for artifact in manifest.required_artifacts)
        and tuple(result.command_result.command for result in evidence.harness_results)
        == manifest.required_checks
    )


def validate_replay_result(replay: ReplayResult, owner_path: Path) -> None:
    manifest_path = resolve_manifest_reference(owner_path, replay.manifest_path)
    evidence_path = resolve_manifest_reference(owner_path, replay.evidence_path)
    if not manifest_path.is_file():
        raise OmfError.missing_replay_manifest(manifest_path)
    if sha256_file(manifest_path) != replay.manifest_sha256:
        raise OmfError.replay_manifest_hash_mismatch(manifest_path)
    manifest_result = inspect_json_artifact(manifest_path)
    if manifest_result.artifact_type != "capability":
        raise OmfError.replay_record_mismatch(owner_path)
    manifest = load_manifest(manifest_path)
    if not evidence_path.is_file():
        raise OmfError.missing_replay_evidence(evidence_path)
    if sha256_file(evidence_path) != replay.evidence_sha256:
        raise OmfError.replay_evidence_hash_mismatch(evidence_path)
    evidence = load_evidence(evidence_path)
    expected_checks = replay_checks_for_manifest_and_evidence(manifest, evidence)
    expected_timing = replay_timing(evidence)
    expected_status = replay_status_from_checks(expected_checks)
    if (
        replay.capability_name != manifest.name
        or not replay_evidence_matches_manifest(manifest, evidence)
        or replay.checks != expected_checks
        or replay.timing != expected_timing
        or replay.status != expected_status
    ):
        raise OmfError.replay_record_mismatch(owner_path)


def inspect_replay_record(path: Path, payload: dict[str, object]) -> InspectResult:
    replay = ReplayResult.model_validate(payload)
    validate_replay_result(replay, path)
    return InspectResult(
        path=str(path.resolve()),
        artifact_type="replay",
        status=replay.status,
        summary={
            "replay_id": replay.replay_id,
            "capability_name": replay.capability_name,
            "manifest_sha256": replay.manifest_sha256,
            "manifest_verified": True,
            "evidence_sha256": replay.evidence_sha256,
            "evidence_verified": True,
            "check_count": len(replay.checks),
            "total_command_and_harness_duration_ms": (
                replay.timing.total_command_and_harness_duration_ms
            ),
        },
    )


def inspect_eval_record(path: Path, payload: dict[str, object]) -> InspectResult:
    eval_result = EvalResult.model_validate(payload)
    for replay in eval_result.replay_results:
        validate_replay_result(replay, path)
    pass_count = sum(1 for replay in eval_result.replay_results if replay.status == "pass")
    expected_status = "pass" if pass_count == eval_result.runs else "fail"
    expected_pass_rate = pass_count / eval_result.runs
    if (
        len(eval_result.replay_results) != eval_result.runs
        or eval_result.pass_count != pass_count
        or eval_result.pass_rate != expected_pass_rate
        or eval_result.status != expected_status
        or eval_result.timing != summarize_eval_timing(eval_result.replay_results)
    ):
        raise OmfError.eval_record_mismatch(path)
    return InspectResult(
        path=str(path.resolve()),
        artifact_type="eval",
        status=eval_result.status,
        summary={
            "eval_id": eval_result.eval_id,
            "capability_name": eval_result.capability_name,
            "runs": eval_result.runs,
            "pass_rate": eval_result.pass_rate,
            "replay_results_verified": True,
            "total_command_and_harness_duration_ms": (
                eval_result.timing.total_command_and_harness_duration_ms
            ),
        },
    )


def validated_store_entry(kind: ArtifactKind, path: Path, name: str) -> StoreIndexEntry:
    inspected_artifact = inspect_json_artifact(path)
    if inspected_artifact.artifact_type != kind:
        raise OmfError.list_artifact_kind_mismatch(
            expected=kind,
            actual=inspected_artifact.artifact_type,
            path=path,
        )
    return StoreIndexEntry(
        kind=kind,
        path=str(path.resolve()),
        name=name,
        status=inspected_artifact.status,
        validated=True,
    )


def list_store(store_dir: Path) -> StoreIndex:
    ensure_store(store_dir)
    entries = [
        validated_store_entry("evidence", evidence_path, evidence_path.stem)
        for evidence_path in sorted((store_dir / "evidence").glob("*.json"))
    ]
    entries.extend(
        validated_store_entry("capability", manifest_path, manifest_path.parent.name)
        for manifest_path in sorted((store_dir / "capabilities").glob("*/manifest.json"))
    )
    entries.extend(
        validated_store_entry("replay", replay_path, replay_path.stem)
        for replay_path in sorted((store_dir / "replays").glob("*.json"))
    )
    entries.extend(
        validated_store_entry("eval", eval_path, eval_path.stem)
        for eval_path in sorted((store_dir / "evals").glob("*.json"))
    )
    entries.extend(
        validated_store_entry("review", review_path, review_path.stem)
        for review_path in sorted((store_dir / "reviews").glob("*.json"))
    )
    entries.extend(
        validated_store_entry("regression", regression_path, regression_path.stem)
        for regression_path in sorted((store_dir / "regressions").glob("*.json"))
    )
    entries.extend(
        validated_store_entry("learning", learning_path, learning_path.parent.name)
        for learning_path in sorted((store_dir / "learning").glob("*/manifest.json"))
    )
    return StoreIndex(store_dir=str(store_dir.resolve()), entries=tuple(entries))


def search_snippets(text: str, query: str, limit: int) -> tuple[str, ...]:
    lowered_query = query.casefold()
    snippets: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if lowered_query in stripped.casefold():
            snippets.append(stripped[:240])
        if len(snippets) >= limit:
            break
    return tuple(snippets)


def search_store(
    store_dir: Path,
    query: str,
    *,
    kind: str | None = None,
    snippet_limit: int = 3,
) -> StoreSearchResult:
    normalized_query = query.strip()
    if not normalized_query:
        raise OmfError.empty_search_query()
    if kind is not None and kind not in ARTIFACT_KINDS:
        raise OmfError.unsupported_artifact_kind(kind)
    index = list_store(store_dir)
    matches: list[SearchMatch] = []
    for entry in index.entries:
        if kind is not None and entry.kind != kind:
            continue
        path = Path(entry.path)
        text = path.read_text(encoding="utf-8")
        score = text.casefold().count(normalized_query.casefold())
        if score == 0:
            continue
        inspected_artifact = inspect_json_artifact(path)
        if inspected_artifact.artifact_type != entry.kind:
            raise OmfError.search_artifact_kind_mismatch(
                expected=entry.kind,
                actual=inspected_artifact.artifact_type,
                path=path,
            )
        matches.append(
            SearchMatch(
                kind=entry.kind,
                path=entry.path,
                name=entry.name,
                status=inspected_artifact.status,
                validated=True,
                score=score,
                snippets=search_snippets(text, normalized_query, snippet_limit),
            )
        )
    matches.sort(key=lambda match: (-match.score, match.kind, match.name))
    return StoreSearchResult(
        store_dir=str(store_dir.resolve()),
        query=normalized_query,
        matches=tuple(matches),
    )


def inspect_json_artifact(path: Path) -> InspectResult:  # noqa: PLR0911
    payload = read_json(path)
    schema_version = payload.get("schema_version")
    resolved_path = str(path.resolve())
    if schema_version == "omf.evidence.v1":
        evidence = load_evidence(path)
        return InspectResult(
            path=resolved_path,
            artifact_type="evidence",
            status=evidence.status,
            summary={
                "run_id": evidence.run_id,
                "goal": evidence.goal,
                "exit_code": evidence.command_result.exit_code,
                "artifact_count": len(evidence.artifacts),
                "harness_count": len(evidence.harness_results),
                "git_dirty": evidence.git.dirty if evidence.git else False,
                "git_changed_file_count": (
                    len(evidence.git.changed_files) if evidence.git else 0
                ),
            },
        )
    if schema_version == "omf.capability.v1":
        return inspect_capability_manifest(path, payload)
    if schema_version == "omf.replay.v1":
        return inspect_replay_record(path, payload)
    if schema_version == "omf.eval.v1":
        return inspect_eval_record(path, payload)
    if schema_version == "omf.review.v1":
        return inspect_review_record(path, payload)
    if schema_version == "omf.regression_case.v1":
        return inspect_regression_case(path, payload)
    if schema_version == "omf.learning_export.v1":
        return inspect_learning_export(path, payload)
    message = f"Unsupported omf artifact schema: {schema_version!r}"
    raise OmfError(message)


def normalize_review_decision(decision: str) -> ReviewDecision:
    normalized = decision.strip().lower().replace("-", "_")
    if normalized not in REVIEW_DECISIONS:
        raise OmfError.unsupported_review_decision(decision)
    return normalized


def record_review(
    *,
    artifact_path: Path,
    reviewer: str,
    decision: str,
    note: str,
    store_dir: Path,
) -> tuple[ReviewRecord, Path]:
    ensure_store(store_dir)
    normalized_reviewer = reviewer.strip()
    normalized_note = note.strip()
    if not normalized_reviewer:
        raise OmfError.empty_reviewer()
    if not normalized_note:
        raise OmfError.empty_review_note()

    inspected_artifact = inspect_json_artifact(artifact_path)
    review = ReviewRecord(
        review_id=new_id("review"),
        created_at=now_iso(),
        reviewer=normalized_reviewer,
        decision=normalize_review_decision(decision),
        note=normalized_note,
        reviewed_artifact_path=str(artifact_path.resolve()),
        reviewed_artifact_sha256=sha256_file(artifact_path),
        reviewed_artifact_type=inspected_artifact.artifact_type,
        reviewed_artifact_status=inspected_artifact.status,
    )
    output_path = store_dir / "reviews" / f"{review.review_id}.json"
    write_json(output_path, review.model_dump_json(indent=2))
    return review, output_path


def record_regression_case(
    *,
    manifest_path: Path,
    source_artifact_path: Path,
    name: str,
    reason: str,
    store_dir: Path,
) -> tuple[RegressionCaseRecord, Path]:
    ensure_store(store_dir)
    slug = slugify(name)
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise OmfError.empty_regression_reason()

    source_artifact = inspect_json_artifact(source_artifact_path)
    manifest = load_verified_manifest(manifest_path)
    replay_result, _ = replay_capability(
        manifest_path=manifest_path,
        store_dir=store_dir,
    )
    case = RegressionCaseRecord(
        case_id=new_id("regression"),
        name=slug,
        reason=normalized_reason,
        created_at=now_iso(),
        source_artifact_path=str(source_artifact_path.resolve()),
        source_artifact_sha256=sha256_file(source_artifact_path),
        source_artifact_type=source_artifact.artifact_type,
        source_artifact_status=source_artifact.status,
        manifest_path=str(manifest_path.resolve()),
        manifest_sha256=sha256_file(manifest_path),
        capability_name=manifest.name,
        status=replay_result.status,
        replay_result=replay_result,
    )
    output_path = store_dir / "regressions" / f"{case.case_id}.json"
    write_json(output_path, case.model_dump_json(indent=2))
    return case, output_path


def normalize_learning_purpose(purpose: str) -> LearningPurpose:
    normalized = purpose.strip().lower().replace("-", "_")
    if normalized not in LEARNING_PURPOSES:
        raise OmfError.unsupported_learning_purpose(purpose)
    return normalized


def write_jsonl(path: Path, items: tuple[LearningExportItem, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = tuple(item.model_dump_json() for item in items)
    _ = path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def export_learning_items(
    *,
    source_artifact_paths: tuple[Path, ...],
    name: str,
    purpose: str,
    note: str,
    store_dir: Path,
) -> tuple[LearningExportManifest, Path]:
    ensure_store(store_dir)
    if not source_artifact_paths:
        raise OmfError.empty_learning_sources()
    slug = slugify(name)
    normalized_note = note.strip()
    if not normalized_note:
        raise OmfError.empty_learning_note()
    normalized_purpose = normalize_learning_purpose(purpose)

    items: list[LearningExportItem] = []
    for source_artifact_path in source_artifact_paths:
        inspected_artifact = inspect_json_artifact(source_artifact_path)
        items.append(
            LearningExportItem(
                source_artifact_path=str(source_artifact_path.resolve()),
                source_artifact_sha256=sha256_file(source_artifact_path),
                source_artifact_type=inspected_artifact.artifact_type,
                source_artifact_status=inspected_artifact.status,
                label=f"{inspected_artifact.artifact_type}:{inspected_artifact.status}",
                note=normalized_note,
            )
        )

    export_id = new_id("learning")
    output_dir = store_dir / "learning" / f"{slug}-{export_id}"
    jsonl_path = output_dir / "items.jsonl"
    export_items = tuple(items)
    write_jsonl(jsonl_path, export_items)
    manifest = LearningExportManifest(
        export_id=export_id,
        created_at=now_iso(),
        name=slug,
        purpose=normalized_purpose,
        output_jsonl_path=str(jsonl_path.resolve()),
        output_jsonl_sha256=sha256_file(jsonl_path),
        item_count=len(export_items),
        items=export_items,
    )
    manifest_path = output_dir / "manifest.json"
    write_json(manifest_path, manifest.model_dump_json(indent=2))
    return manifest, manifest_path


def promote_evidence(
    *,
    evidence_path: Path,
    name: str,
    store_dir: Path,
    version: str = "0.1.0",
) -> tuple[CapabilityManifest, Path]:
    ensure_store(store_dir)
    evidence = load_evidence(evidence_path)
    if evidence.status != "pass":
        raise OmfError.cannot_promote_failed_evidence()
    missing_artifacts = [artifact.path for artifact in evidence.artifacts if not artifact.exists]
    if missing_artifacts:
        raise OmfError.cannot_promote_missing_artifacts(missing_artifacts)

    slug = slugify(name)
    manifest = CapabilityManifest(
        name=slug,
        version=version,
        created_at=now_iso(),
        source_evidence_path=str(evidence_path.resolve()),
        source_evidence_sha256=sha256_file(evidence_path),
        goal=evidence.goal,
        command=evidence.command_result.command,
        cwd=evidence.command_result.cwd,
        success_exit_code=0,
        required_artifacts=evidence.artifacts,
        required_checks=tuple(result.command_result.command for result in evidence.harness_results),
    )
    output_path = store_dir / "capabilities" / slug / "manifest.json"
    write_json(output_path, manifest.model_dump_json(indent=2))
    return manifest, output_path


def compare_replay_artifacts(
    expected: tuple[ArtifactEvidence, ...], actual: tuple[ArtifactEvidence, ...]
) -> tuple[ReplayCheck, ...]:
    actual_by_path = {artifact.path: artifact for artifact in actual}
    checks: list[ReplayCheck] = []
    for expected_artifact in expected:
        actual_artifact = actual_by_path.get(expected_artifact.path)
        if actual_artifact is None or not actual_artifact.exists:
            checks.append(
                ReplayCheck(
                    name=f"artifact:{expected_artifact.path}",
                    status="fail",
                    detail="artifact missing after replay",
                )
            )
            continue
        if expected_artifact.sha256 != actual_artifact.sha256:
            checks.append(
                ReplayCheck(
                    name=f"artifact:{expected_artifact.path}",
                    status="fail",
                    detail="artifact hash changed after replay",
                )
            )
            continue
        checks.append(
            ReplayCheck(
                name=f"artifact:{expected_artifact.path}",
                status="pass",
                detail="artifact exists and hash matches promoted evidence",
            )
        )
    return tuple(checks)


def replay_harness_checks(
    harness_results: tuple[HarnessCheckResult, ...],
) -> tuple[ReplayCheck, ...]:
    return tuple(
        ReplayCheck(
            name=f"harness:{result.name}",
            status=result.status,
            detail=(
                f"{result.command_result.command!r} exited "
                f"{result.command_result.exit_code}"
            ),
        )
        for result in harness_results
    )


def replay_timing(evidence: EvidenceRecord) -> ReplayTiming:
    harness_duration_ms = sum(
        result.command_result.duration_ms for result in evidence.harness_results
    )
    return ReplayTiming(
        command_duration_ms=evidence.command_result.duration_ms,
        harness_duration_ms=harness_duration_ms,
        total_command_and_harness_duration_ms=(
            evidence.command_result.duration_ms + harness_duration_ms
        ),
    )


def replay_capability(
    *,
    manifest_path: Path,
    store_dir: Path,
) -> tuple[ReplayResult, Path]:
    ensure_store(store_dir)
    manifest = load_verified_manifest(manifest_path)
    artifact_paths = tuple(artifact.path for artifact in manifest.required_artifacts)
    evidence, evidence_path = capture_evidence(
        CaptureRequest(
            goal=f"Replay capability {manifest.name}",
            command=manifest.command,
            artifacts=artifact_paths,
            checks=manifest.required_checks,
            store_dir=store_dir,
            cwd=Path(manifest.cwd),
            run_id_prefix="replay-evidence",
        )
    )

    checks = replay_checks_for_manifest_and_evidence(manifest, evidence)
    status = replay_status_from_checks(checks)
    replay = ReplayResult(
        replay_id=new_id("replay"),
        capability_name=manifest.name,
        status=status,
        created_at=now_iso(),
        manifest_path=str(manifest_path.resolve()),
        manifest_sha256=sha256_file(manifest_path),
        evidence_path=str(evidence_path.resolve()),
        evidence_sha256=sha256_file(evidence_path),
        checks=checks,
        timing=replay_timing(evidence),
    )
    output_path = store_dir / "replays" / f"{replay.replay_id}.json"
    write_json(output_path, replay.model_dump_json(indent=2))
    return replay, output_path


def summarize_eval_timing(replay_results: tuple[ReplayResult, ...]) -> EvalTimingSummary:
    command_durations = tuple(
        replay.timing.command_duration_ms for replay in replay_results
    )
    harness_duration_total = sum(
        replay.timing.harness_duration_ms for replay in replay_results
    )
    total_measured_duration = sum(
        replay.timing.total_command_and_harness_duration_ms
        for replay in replay_results
    )
    return EvalTimingSummary(
        command_duration_ms_min=min(command_durations),
        command_duration_ms_max=max(command_durations),
        command_duration_ms_mean=sum(command_durations) / len(command_durations),
        harness_duration_ms_total=harness_duration_total,
        total_command_and_harness_duration_ms=total_measured_duration,
    )


def evaluate_capability(
    *,
    manifest_path: Path,
    store_dir: Path,
    runs: int,
) -> tuple[EvalResult, Path]:
    if runs <= 0:
        raise OmfError.invalid_eval_runs()
    ensure_store(store_dir)
    manifest = load_verified_manifest(manifest_path)
    replay_results: list[ReplayResult] = []
    for _ in range(runs):
        replay, _ = replay_capability(manifest_path=manifest_path, store_dir=store_dir)
        replay_results.append(replay)

    pass_count = sum(1 for replay in replay_results if replay.status == "pass")
    eval_result = EvalResult(
        eval_id=new_id("eval"),
        capability_name=manifest.name,
        status="pass" if pass_count == runs else "fail",
        created_at=now_iso(),
        runs=runs,
        pass_count=pass_count,
        pass_rate=pass_count / runs,
        timing=summarize_eval_timing(tuple(replay_results)),
        replay_results=tuple(replay_results),
    )
    output_path = store_dir / "evals" / f"{eval_result.eval_id}.json"
    write_json(output_path, eval_result.model_dump_json(indent=2))
    return eval_result, output_path
