import json
from pathlib import Path
from typing import Literal

from pydantic import Field

from oh_my_field.domain.layout import (
    DEFAULT_DATASETS_DIR,
    DEFAULT_EVAL_DIR,
    DEFAULT_LEARNING_DIR,
    DEFAULT_LEARNING_PATCH_DIR,
)
from oh_my_field.models import (
    CAPABILITY_NAME_PATTERN,
    EvalResult,
    LearningExport,
    LearningPatchDecision,
    StrictModel,
)
from oh_my_field.storage import (
    list_eval_results,
    list_learning_exports,
    list_learning_patch_decisions,
)

type DatasetExportType = Literal["all", "fine-tuning", "preference", "eval"]
type DatasetRow = dict[str, object]

_DATASET_TYPES: tuple[DatasetExportType, ...] = (
    "fine-tuning",
    "preference",
    "eval",
)


class DatasetExportError(Exception):
    pass


class DatasetExportRequest(StrictModel):
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    dataset_type: DatasetExportType = "all"
    learning_dir: Path = DEFAULT_LEARNING_DIR
    learning_patch_dir: Path = DEFAULT_LEARNING_PATCH_DIR
    eval_dir: Path = DEFAULT_EVAL_DIR
    output_dir: Path = DEFAULT_DATASETS_DIR


class DatasetExportFile(StrictModel):
    dataset_type: str
    path: str
    row_count: int


class DatasetExportSummary(StrictModel):
    capability_name: str
    output_dir: str
    files: tuple[DatasetExportFile, ...]
    total_row_count: int


def run_dataset_export(request: DatasetExportRequest) -> DatasetExportSummary:
    learning_exports = _learning_exports(request)
    patch_decisions = _patch_decisions(request)
    eval_results = _eval_results(request)
    files = tuple(
        _write_dataset_file(request, dataset_type, rows)
        for dataset_type, rows in (
            (
                "fine-tuning",
                _fine_tuning_rows(learning_exports),
            ),
            (
                "preference",
                _preference_rows(patch_decisions),
            ),
            (
                "eval",
                _eval_rows(eval_results),
            ),
        )
        if dataset_type in _requested_types(request.dataset_type)
    )
    return DatasetExportSummary(
        capability_name=request.capability_name,
        output_dir=str(request.output_dir),
        files=files,
        total_row_count=sum(file.row_count for file in files),
    )


def _requested_types(dataset_type: DatasetExportType) -> tuple[DatasetExportType, ...]:
    if dataset_type == "all":
        return _DATASET_TYPES
    return (dataset_type,)


def _learning_exports(request: DatasetExportRequest) -> tuple[LearningExport, ...]:
    return tuple(
        export
        for export in list_learning_exports(request.learning_dir)
        if export.capability_name == request.capability_name
    )


def _patch_decisions(
    request: DatasetExportRequest,
) -> tuple[LearningPatchDecision, ...]:
    return tuple(
        decision
        for decision in list_learning_patch_decisions(request.learning_patch_dir)
        if decision.capability_name == request.capability_name
    )


def _eval_results(request: DatasetExportRequest) -> tuple[EvalResult, ...]:
    return tuple(
        result
        for result in list_eval_results(request.eval_dir)
        if result.capability_name == request.capability_name
    )


def _fine_tuning_rows(exports: tuple[LearningExport, ...]) -> tuple[DatasetRow, ...]:
    return tuple(
        _fine_tuning_row(export, candidate)
        for export in exports
        for candidate in export.fine_tuning_candidates
    )


def _fine_tuning_row(export: LearningExport, candidate: str) -> DatasetRow:
    prompt, completion = _split_few_shot_candidate(candidate)
    return {
        "capability_name": export.capability_name,
        "source_learning_id": export.id,
        "source_evidence_id": export.source_evidence_id,
        "prompt": prompt,
        "completion": completion,
    }


def _split_few_shot_candidate(candidate: str) -> tuple[str, str]:
    prefix = "input:\n"
    separator = "\n\noutput:\n"
    if candidate.startswith(prefix) and separator in candidate:
        prompt, completion = candidate.removeprefix(prefix).split(separator, 1)
        return prompt, completion
    return candidate, ""


def _preference_rows(
    decisions: tuple[LearningPatchDecision, ...],
) -> tuple[DatasetRow, ...]:
    return tuple(_preference_row(decision) for decision in decisions)


def _preference_row(decision: LearningPatchDecision) -> DatasetRow:
    return {
        "capability_name": decision.capability_name,
        "source_learning_id": decision.learning_id,
        "source_decision_id": decision.id,
        "patch_kind": decision.patch_kind,
        "prompt": f"{decision.capability_name}:{decision.patch_kind}",
        "accepted_output": decision.patch if decision.decision == "accepted" else "",
        "rejected_output": decision.patch if decision.decision == "rejected" else "",
        "decision": decision.decision,
        "reviewer": decision.reviewer,
        "notes": decision.notes,
        "before_eval_id": decision.before_eval_id,
        "after_eval_id": decision.after_eval_id,
        "pass_rate_delta": decision.pass_rate_delta,
    }


def _eval_rows(eval_results: tuple[EvalResult, ...]) -> tuple[DatasetRow, ...]:
    return tuple(_eval_row(result) for result in eval_results)


def _eval_row(result: EvalResult) -> DatasetRow:
    return {
        "capability_name": result.capability_name,
        "source_eval_id": result.id,
        "source_evidence_id": result.source_evidence_id,
        "replay_id": result.replay_id,
        "runtime_profile": result.runtime_profile,
        "eval_set_name": result.eval_set_name,
        "eval_case_ids": result.eval_case_ids,
        "status": result.status,
        "checks": tuple(check.model_dump(mode="json") for check in result.checks),
        "failures": result.failures,
        "checklist_items": tuple(
            item.model_dump(mode="json") for item in result.checklist_items
        ),
        "rubric_scores": tuple(
            score.model_dump(mode="json") for score in result.rubric_scores
        ),
    }


def _write_dataset_file(
    request: DatasetExportRequest,
    dataset_type: DatasetExportType,
    rows: tuple[DatasetRow, ...],
) -> DatasetExportFile:
    path = request.output_dir / request.capability_name / f"{dataset_type}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
    )
    path.write_text(payload, encoding="utf-8")
    return DatasetExportFile(
        dataset_type=dataset_type,
        path=str(path),
        row_count=len(rows),
    )
