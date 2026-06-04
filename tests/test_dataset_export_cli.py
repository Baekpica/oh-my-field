import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict
from typer.testing import CliRunner

from oh_my_field.cli import app
from oh_my_field.models import (
    EvalCheck,
    EvalResult,
    LearningExport,
    LearningPatchDecision,
)
from oh_my_field.storage import (
    write_eval_result,
    write_learning_export,
    write_learning_patch_decision,
)


class DatasetExportFileOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_type: str
    path: str
    row_count: int


class DatasetExportOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_name: str
    output_dir: str
    files: tuple[DatasetExportFileOutput, ...]
    total_row_count: int


def test_dataset_export_writes_learning_patch_and_eval_jsonl(
    tmp_path: Path,
) -> None:
    learning_dir = tmp_path / "learning"
    learning_patch_dir = tmp_path / "learning_patches"
    eval_dir = tmp_path / "evals"
    output_dir = tmp_path / "datasets"
    learning = make_learning_export()
    accepted = make_patch_decision(
        "20260602T010204Z-cafebabe",
        "accepted",
        "Prefer parser-focused diffs.",
    )
    rejected = make_patch_decision(
        "20260602T010205Z-baddcafe",
        "rejected",
        "Rewrite the whole module.",
    )
    eval_result = make_eval_result()
    write_learning_export(learning, learning_dir)
    write_learning_patch_decision(accepted, learning_patch_dir)
    write_learning_patch_decision(rejected, learning_patch_dir)
    write_eval_result(eval_result, eval_dir)

    result = CliRunner().invoke(
        app,
        [
            "dataset-export",
            "repo_issue_triage",
            "--learning-dir",
            str(learning_dir),
            "--learning-patch-dir",
            str(learning_patch_dir),
            "--eval-dir",
            str(eval_dir),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0
    output = DatasetExportOutput.model_validate_json(result.stdout)
    assert output.capability_name == "repo_issue_triage"
    assert output.total_row_count == 4
    assert [(file.dataset_type, file.row_count) for file in output.files] == [
        ("fine-tuning", 1),
        ("preference", 2),
        ("eval", 1),
    ]

    fine_tuning_rows = _jsonl(output_dir / "repo_issue_triage" / "fine-tuning.jsonl")
    assert fine_tuning_rows == [
        {
            "capability_name": "repo_issue_triage",
            "completion": "Fixed parser branch.",
            "prompt": "Find the parser bug.",
            "source_evidence_id": "20260602T010203Z-deadbeef",
            "source_learning_id": learning.id,
        },
    ]

    preference_rows = _jsonl(output_dir / "repo_issue_triage" / "preference.jsonl")
    assert preference_rows[0]["accepted_output"] == "Prefer parser-focused diffs."
    assert preference_rows[0]["rejected_output"] == ""
    assert preference_rows[1]["accepted_output"] == ""
    assert preference_rows[1]["rejected_output"] == "Rewrite the whole module."
    assert preference_rows[1]["source_decision_id"] == rejected.id

    eval_rows = _jsonl(output_dir / "repo_issue_triage" / "eval.jsonl")
    assert eval_rows[0]["source_eval_id"] == eval_result.id
    assert eval_rows[0]["status"] == "fail"
    assert eval_rows[0]["failures"] == ["parser_regression"]
    assert eval_rows[0]["checks"][0]["name"] == "parser_regression"


def make_learning_export() -> LearningExport:
    return LearningExport(
        id="20260602T010203Z-feedface",
        created_at=datetime(2026, 6, 2, 1, 2, 3, tzinfo=UTC),
        capability_name="repo_issue_triage",
        source_evidence_id="20260602T010203Z-deadbeef",
        fine_tuning_candidates=(
            "input:\nFind the parser bug.\n\noutput:\nFixed parser branch.",
        ),
    )


def make_patch_decision(
    decision_id: str,
    decision: Literal["accepted", "rejected"],
    patch: str,
) -> LearningPatchDecision:
    return LearningPatchDecision(
        id=decision_id,
        created_at=datetime(2026, 6, 2, 1, 2, 4, tzinfo=UTC),
        capability_name="repo_issue_triage",
        learning_id="20260602T010203Z-feedface",
        patch_kind="prompt",
        patch=patch,
        decision=decision,
        reviewer="operator",
        before_eval_id="20260602T010206Z-aaaabbbb",
        after_eval_id="20260602T010207Z-ccccdddd",
        pass_rate_delta=0.25,
    )


def make_eval_result() -> EvalResult:
    return EvalResult(
        id="20260602T010208Z-facefeed",
        created_at=datetime(2026, 6, 2, 1, 2, 8, tzinfo=UTC),
        capability_name="repo_issue_triage",
        source_evidence_id="20260602T010203Z-deadbeef",
        replay_id="20260602T010209Z-1234abcd",
        status="fail",
        checks=(
            EvalCheck(
                name="parser_regression",
                status="fail",
                message="parser branch regressed",
            ),
        ),
        failures=("parser_regression",),
    )


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        cast("dict[str, Any]", json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
