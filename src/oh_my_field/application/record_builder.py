import csv
import hashlib
import json
import mimetypes
import re
import zipfile
from pathlib import Path
from typing import Final

from oh_my_field.domain.evidence.redaction import redact_secrets
from oh_my_field.models import (
    ArtifactContract,
    ArtifactSnapshot,
    ArtifactSnapshotRole,
    EvidenceRecord,
    HarnessResult,
    RecordQuality,
    RunObservation,
    TaskContract,
    ValidationCheckResult,
)

TEXT_PREVIEW_BYTES: Final = 4096
DIRECTORY_ENTRY_LIMIT: Final = 200
PNG_MIN_HEADER_BYTES: Final = 24
KIND_BY_SUFFIX: Final = {
    ".csv": "csv",
    ".docx": "docx",
    ".htm": "html",
    ".html": "html",
    ".json": "json",
    ".pdf": "pdf",
    ".png": "png",
    ".py": "python",
    ".xlsx": "xlsx",
}
TEXT_EXTENSIONS: Final = {
    ".csv",
    ".html",
    ".json",
    ".log",
    ".md",
    ".py",
    ".txt",
    ".yaml",
    ".yml",
}


def harden_evidence_record(
    evidence: EvidenceRecord,
    *,
    project_root: Path | None = None,
    redact_previews: bool = True,
    redact_patterns: tuple[re.Pattern[str], ...] = (),
) -> EvidenceRecord:
    root = project_root or Path()
    artifact_paths = _artifact_paths(evidence)
    snapshots = tuple(
        _snapshot_artifact(
            path,
            root,
            redact_preview=redact_previews,
            redact_patterns=redact_patterns,
        )
        for path in artifact_paths
    )
    validation_results = _merge_validation_results(
        evidence.validation_results,
        tuple(
            result for snapshot in snapshots for result in _validate_snapshot(snapshot)
        ),
    )
    contracts = _artifact_contracts(snapshots)
    task_contract = TaskContract(
        goal=evidence.normalized_goal or evidence.goal,
        required_inputs=_required_inputs(evidence),
        expected_artifacts=tuple(contract.artifact_path for contract in contracts),
        validation_checks=tuple(result.name for result in validation_results),
    )
    observations = _merge_observations(
        evidence.run_observations,
        _observations_from_evidence(evidence),
    )
    quality = _record_quality(
        task_contract=task_contract,
        artifact_contracts=contracts,
        validation_results=validation_results,
    )
    harness = _harden_harness(evidence.harness, validation_results)
    return evidence.model_copy(
        update={
            "run_observations": observations,
            "artifact_snapshots": snapshots,
            "artifact_contracts": contracts,
            "validation_results": validation_results,
            "task_contract": task_contract,
            "record_quality": quality,
            "harness": harness,
        },
    )


def _artifact_paths(evidence: EvidenceRecord) -> tuple[str, ...]:
    values = [*evidence.final_artifacts]
    values.extend(file.path for file in evidence.files if file.role == "artifact")
    return tuple(dict.fromkeys(value for value in values if value))


def _required_inputs(evidence: EvidenceRecord) -> tuple[str, ...]:
    values = [*evidence.input_context]
    values.extend(
        file.path for file in evidence.files if file.role in ("prompt", "context")
    )
    return tuple(dict.fromkeys(value for value in values if value))


def _snapshot_artifact(
    path_value: str,
    root: Path,
    *,
    redact_preview: bool,
    redact_patterns: tuple[re.Pattern[str], ...] = (),
) -> ArtifactSnapshot:
    display_path = Path(path_value).as_posix()
    root_path = root.resolve(strict=False)
    absolute_path = _absolute_path(path_value, root_path)
    if absolute_path is None:
        return ArtifactSnapshot(
            path=display_path,
            role="final",
            kind=_kind_for_path(Path(path_value)),
            size_bytes=0,
            metadata={
                "exists": False,
                "path_within_project": False,
                "blocked_reason": "outside_project_root",
            },
        )
    if not absolute_path.exists():
        return ArtifactSnapshot(
            path=display_path,
            role="final",
            kind=_kind_for_path(absolute_path),
            size_bytes=0,
            metadata={"exists": False, "path_within_project": True},
        )
    if absolute_path.is_dir():
        return _snapshot_directory(display_path, absolute_path, root_path)
    return _snapshot_file(
        display_path,
        absolute_path,
        redact_preview=redact_preview,
        redact_patterns=redact_patterns,
    )


def _absolute_path(path_value: str, root: Path) -> Path | None:
    path = Path(path_value)
    root_path = root.resolve(strict=False)
    candidate = path if path.is_absolute() else root_path / path
    resolved = candidate.resolve(strict=False)
    if not _is_relative_to(resolved, root_path):
        return None
    return resolved


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _snapshot_directory(
    display_path: str,
    directory: Path,
    root: Path,
) -> ArtifactSnapshot:
    entries: list[str] = []
    total_size = 0
    skipped_outside_project = 0
    digest = hashlib.sha256()
    for child in sorted(item for item in directory.rglob("*") if item.is_file()):
        resolved_child = child.resolve(strict=False)
        if not _is_relative_to(resolved_child, root):
            skipped_outside_project += 1
            continue
        relative = child.relative_to(directory).as_posix()
        if len(entries) < DIRECTORY_ENTRY_LIMIT:
            entries.append(relative)
        try:
            raw = resolved_child.read_bytes()
        except OSError:
            raw = b""
        total_size += len(raw)
        digest.update(relative.encode("utf-8"))
        digest.update(hashlib.sha256(raw).hexdigest().encode("ascii"))
    return ArtifactSnapshot(
        path=display_path,
        role="final",
        kind="directory",
        sha256=digest.hexdigest(),
        size_bytes=total_size,
        directory_entries=tuple(entries),
        metadata={
            "exists": True,
            "path_within_project": True,
            "entry_count": len(entries),
            "skipped_outside_project_count": skipped_outside_project,
            "truncated": len(entries) >= DIRECTORY_ENTRY_LIMIT,
        },
    )


def _snapshot_file(
    display_path: str,
    path: Path,
    *,
    redact_preview: bool,
    redact_patterns: tuple[re.Pattern[str], ...] = (),
) -> ArtifactSnapshot:
    raw = path.read_bytes()
    kind = _kind_for_path(path)
    metadata = _metadata_for_file(path, raw, kind)
    text_preview = _text_preview(path, raw, kind)
    if text_preview is not None and redact_preview:
        text_preview, preview_redacted = redact_secrets(
            text_preview,
            extra_patterns=redact_patterns,
        )
        if preview_redacted:
            metadata["preview_redacted"] = True
    return ArtifactSnapshot(
        path=display_path,
        role="final",
        kind=kind,
        sha256=hashlib.sha256(raw).hexdigest(),
        size_bytes=len(raw),
        mime_type=mimetypes.guess_type(path.name)[0],
        text_preview=text_preview,
        metadata={"exists": True, "path_within_project": True, **metadata},
    )


def _kind_for_path(path: Path) -> str:
    if path.is_dir():
        return "directory"
    suffix = path.suffix.casefold()
    mapped = KIND_BY_SUFFIX.get(suffix)
    if mapped is not None:
        return mapped
    if suffix in TEXT_EXTENSIONS:
        return "text"
    return suffix.removeprefix(".") or "file"


def _metadata_for_file(
    path: Path,
    raw: bytes,
    kind: str,
) -> dict[str, str | int | float | bool | None]:
    metadata: dict[str, str | int | float | bool | None] = {}
    if kind == "json":
        metadata = _json_metadata(raw)
    elif kind == "csv":
        metadata = _csv_metadata(raw)
    elif kind == "png":
        metadata = _png_metadata(raw)
    elif kind in ("docx", "xlsx"):
        metadata = _zip_metadata(path)
    elif kind == "pdf":
        metadata = {"valid_pdf": raw.startswith(b"%PDF")}
    elif kind == "html":
        metadata = {"valid_html": b"<" in raw and b">" in raw}
    return metadata


def _json_metadata(raw: bytes) -> dict[str, str | int | float | bool | None]:
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"valid_json": False, "parse_error": str(exc)}
    return {"valid_json": True, "top_level_type": type(parsed).__name__}


def _csv_metadata(raw: bytes) -> dict[str, str | int | float | bool | None]:
    try:
        rows = list(csv.reader(raw.decode("utf-8").splitlines()))
    except UnicodeDecodeError as exc:
        return {"valid_csv": False, "parse_error": str(exc)}
    column_count = len(rows[0]) if rows else 0
    return {
        "valid_csv": bool(rows),
        "row_count": len(rows),
        "column_count": column_count,
    }


def _png_metadata(raw: bytes) -> dict[str, str | int | float | bool | None]:
    if len(raw) < PNG_MIN_HEADER_BYTES or not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return {"valid_png": False}
    width = int.from_bytes(raw[16:20], "big")
    height = int.from_bytes(raw[20:24], "big")
    return {"valid_png": True, "width": width, "height": height}


def _zip_metadata(path: Path) -> dict[str, str | int | float | bool | None]:
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
    except zipfile.BadZipFile as exc:
        return {"valid_zip": False, "parse_error": str(exc)}
    return {"valid_zip": True, "zip_entry_count": len(names)}


def _text_preview(path: Path, raw: bytes, kind: str) -> str | None:
    if kind not in {"csv", "html", "json", "python", "text"}:
        return None
    if path.suffix.casefold() not in TEXT_EXTENSIONS and kind == "text":
        return None
    try:
        return raw[:TEXT_PREVIEW_BYTES].decode("utf-8", errors="replace")
    except UnicodeDecodeError:
        return None


def _validate_snapshot(
    snapshot: ArtifactSnapshot,
) -> tuple[ValidationCheckResult, ...]:
    if snapshot.metadata.get("path_within_project") is False:
        return (
            ValidationCheckResult(
                name=f"artifact_within_project:{snapshot.path}",
                status="fail",
                message="artifact path escapes project root",
                artifact_path=snapshot.path,
            ),
        )
    exists = bool(snapshot.metadata.get("exists"))
    results = [
        ValidationCheckResult(
            name=f"artifact_exists:{snapshot.path}",
            status="pass" if exists else "fail",
            message="artifact exists" if exists else "artifact is missing",
            artifact_path=snapshot.path,
        ),
    ]
    if not exists:
        return tuple(results)
    if snapshot.kind == "directory":
        has_entries = bool(snapshot.directory_entries)
        results.append(
            ValidationCheckResult(
                name=f"directory_has_entries:{snapshot.path}",
                status="pass" if has_entries else "fail",
                message="directory has files" if has_entries else "directory is empty",
                artifact_path=snapshot.path,
            ),
        )
    if snapshot.kind == "json":
        results.append(_metadata_check(snapshot, "valid_json", "json_parses"))
    if snapshot.kind == "csv":
        results.append(_metadata_check(snapshot, "valid_csv", "csv_parses"))
    if snapshot.kind == "png":
        results.append(_metadata_check(snapshot, "valid_png", "png_dimensions"))
    if snapshot.kind in ("docx", "xlsx"):
        results.append(_metadata_check(snapshot, "valid_zip", f"{snapshot.kind}_opens"))
    if snapshot.kind == "pdf":
        results.append(_metadata_check(snapshot, "valid_pdf", "pdf_header"))
    return tuple(results)


def _metadata_check(
    snapshot: ArtifactSnapshot,
    metadata_key: str,
    check_name: str,
) -> ValidationCheckResult:
    passed = bool(snapshot.metadata.get(metadata_key))
    return ValidationCheckResult(
        name=f"{check_name}:{snapshot.path}",
        status="pass" if passed else "fail",
        message=f"{check_name} passed" if passed else f"{check_name} failed",
        artifact_path=snapshot.path,
    )


def _artifact_contracts(
    snapshots: tuple[ArtifactSnapshot, ...],
) -> tuple[ArtifactContract, ...]:
    return tuple(
        ArtifactContract(
            name=_contract_name(snapshot.path),
            artifact_path=snapshot.path,
            artifact_kind=snapshot.kind,
            role=_contract_role(snapshot),
            required=True,
            validation_checks=tuple(
                result.name for result in _validate_snapshot(snapshot)
            ),
        )
        for snapshot in snapshots
    )


def _contract_name(path: str) -> str:
    normalized = "".join(
        character if character.isalnum() else "_" for character in path.casefold()
    ).strip("_")
    return normalized or "artifact"


def _contract_role(snapshot: ArtifactSnapshot) -> ArtifactSnapshotRole:
    return snapshot.role


def _merge_validation_results(
    existing: tuple[ValidationCheckResult, ...],
    generated: tuple[ValidationCheckResult, ...],
) -> tuple[ValidationCheckResult, ...]:
    merged: dict[str, ValidationCheckResult] = {}
    for result in (*existing, *generated):
        merged[result.name] = result
    return tuple(merged.values())


def _observations_from_evidence(evidence: EvidenceRecord) -> tuple[RunObservation, ...]:
    observations: list[RunObservation] = [
        RunObservation(kind="goal", summary=evidence.goal),
    ]
    observations.extend(
        RunObservation(kind="input", summary=f"captured input {path}", path=path)
        for path in _required_inputs(evidence)
    )
    observations.extend(
        RunObservation(
            kind="command",
            summary=execution.command,
            command=execution.command,
            exit_code=execution.exit_code,
        )
        for execution in evidence.command_executions
    )
    observations.extend(
        RunObservation(kind="artifact", summary=f"captured artifact {path}", path=path)
        for path in _artifact_paths(evidence)
    )
    observations.extend(
        RunObservation(kind="validation", summary=check)
        for check in evidence.harness.checks
    )
    return tuple(observations)


def _merge_observations(
    existing: tuple[RunObservation, ...],
    generated: tuple[RunObservation, ...],
) -> tuple[RunObservation, ...]:
    seen: set[tuple[str, str, str | None, str | None]] = set()
    merged: list[RunObservation] = []
    for observation in (*existing, *generated):
        key = (
            observation.kind,
            observation.summary,
            observation.path,
            observation.command,
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(observation)
    return tuple(merged)


def _record_quality(
    *,
    task_contract: TaskContract,
    artifact_contracts: tuple[ArtifactContract, ...],
    validation_results: tuple[ValidationCheckResult, ...],
) -> RecordQuality:
    missing: list[str] = []
    warnings: list[str] = []
    if not task_contract.required_inputs:
        missing.append("required_inputs")
        warnings.append("No required input context was recorded.")
    if not artifact_contracts:
        missing.append("artifact_contracts")
        warnings.append("No artifact contract was inferred.")
    if not validation_results:
        missing.append("validation_results")
        warnings.append("No artifact validation was recorded.")
    if any(result.status == "fail" for result in validation_results):
        missing.append("passing_validation")
        warnings.append("One or more validation checks failed.")
    unique_missing = tuple(dict.fromkeys(missing))
    score = max(0.0, 1.0 - (len(unique_missing) / 4.0))
    return RecordQuality(
        score=score,
        warnings=tuple(warnings),
        missing_sections=unique_missing,
        strict_ready=not unique_missing,
    )


def _harden_harness(
    harness: HarnessResult,
    validation_results: tuple[ValidationCheckResult, ...],
) -> HarnessResult:
    checks = tuple(
        dict.fromkeys(
            (*harness.checks, *(result.name for result in validation_results)),
        ),
    )
    required_checks = tuple(
        dict.fromkeys(
            (*harness.required_checks, *(result.name for result in validation_results)),
        ),
    )
    failures = tuple(
        dict.fromkeys(
            (
                *harness.failures,
                *(
                    result.message
                    for result in validation_results
                    if result.status == "fail"
                ),
            ),
        ),
    )
    return HarnessResult(
        status="fail" if failures else harness.status,
        checks=checks,
        failures=failures,
        required_checks=required_checks,
        human_review_required=harness.human_review_required,
    )
