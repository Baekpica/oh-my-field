from pathlib import Path

from pydantic import BaseModel, ConfigDict
from typer.testing import CliRunner

from oh_my_field.cli import app
from oh_my_field.models import HumanReviewRecord


class ReviewOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    review_id: str
    review_path: str
    target_type: str
    target_id: str
    status: str


def test_approve_creates_human_review_record(tmp_path: Path) -> None:
    review_dir = tmp_path / "reviews"

    result = CliRunner().invoke(
        app,
        [
            "approve",
            "capability",
            "repo_issue_triage",
            "--reviewer",
            "operator",
            "--note",
            "meets field criteria",
            "--review-dir",
            str(review_dir),
        ],
    )

    assert result.exit_code == 0
    output = ReviewOutput.model_validate_json(result.stdout)
    record = HumanReviewRecord.model_validate_json(
        Path(output.review_path).read_text(encoding="utf-8"),
    )
    assert output.status == "approved"
    assert record.target_type == "capability"
    assert record.target_id == "repo_issue_triage"
    assert record.review.reviewer == "operator"
    assert record.review.notes == ("meets field criteria",)


def test_revise_requires_revision_and_records_requested_change(
    tmp_path: Path,
) -> None:
    review_dir = tmp_path / "reviews"

    result = CliRunner().invoke(
        app,
        [
            "revise",
            "evidence",
            "20260602T010203Z-deadbeef",
            "--revision",
            "add missing regression test",
            "--review-dir",
            str(review_dir),
        ],
    )

    assert result.exit_code == 0
    output = ReviewOutput.model_validate_json(result.stdout)
    record = HumanReviewRecord.model_validate_json(
        Path(output.review_path).read_text(encoding="utf-8"),
    )
    assert output.status == "revision_requested"
    assert record.action == "revise"
    assert record.review.revision_request == "add missing regression test"


def test_review_records_additional_human_actions(tmp_path: Path) -> None:
    review_dir = tmp_path / "reviews"

    result = CliRunner().invoke(
        app,
        [
            "review",
            "capability",
            "repo_issue_triage",
            "add_context",
            "--added-context",
            "prefer small diffs",
            "--review-dir",
            str(review_dir),
        ],
    )

    assert result.exit_code == 0
    output = ReviewOutput.model_validate_json(result.stdout)
    record = HumanReviewRecord.model_validate_json(
        Path(output.review_path).read_text(encoding="utf-8"),
    )
    assert output.status == "context_added"
    assert record.review.added_context == ("prefer small diffs",)


def test_review_records_safety_and_regression_signals(tmp_path: Path) -> None:
    review_dir = tmp_path / "reviews"

    unsafe_result = CliRunner().invoke(
        app,
        [
            "review",
            "replay",
            "20260602T010204Z-feedface",
            "mark_unsafe",
            "--note",
            "destructive command attempted",
            "--review-dir",
            str(review_dir),
        ],
    )
    regression_result = CliRunner().invoke(
        app,
        [
            "review",
            "evidence",
            "20260602T010203Z-deadbeef",
            "create_regression_case",
            "--regression-case",
            "parser should reject empty branch",
            "--review-dir",
            str(review_dir),
        ],
    )

    assert unsafe_result.exit_code == 0
    assert regression_result.exit_code == 0
    unsafe = HumanReviewRecord.model_validate_json(
        Path(ReviewOutput.model_validate_json(unsafe_result.stdout).review_path)
        .read_text(encoding="utf-8"),
    )
    regression = HumanReviewRecord.model_validate_json(
        Path(ReviewOutput.model_validate_json(regression_result.stdout).review_path)
        .read_text(encoding="utf-8"),
    )
    assert unsafe.review.unsafe is True
    assert regression.review.regression_case == "parser should reject empty branch"
