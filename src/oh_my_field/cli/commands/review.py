from pathlib import Path
from typing import Annotated, Literal

import typer

from oh_my_field.cli.errors import cli_errors
from oh_my_field.cli.output import emit_json
from oh_my_field.models import HumanReviewAction, ReviewTargetType
from oh_my_field.review import ReviewError, ReviewRequest, run_review_workflow

TargetType = Literal["evidence", "capability", "replay", "eval"]


def _run_review_command(
    *,
    target_type: ReviewTargetType,
    target_id: str,
    action: HumanReviewAction,
    reviewer: str | None,
    notes: tuple[str, ...],
    revision_request: str | None,
    review_dir: Path,
    added_context: tuple[str, ...] = (),
    changed_goal: str | None = None,
    changed_constraint: str | None = None,
    regression_case: str | None = None,
) -> None:
    with cli_errors(ReviewError):
        request = ReviewRequest(
            target_type=target_type,
            target_id=target_id,
            action=action,
            reviewer=reviewer,
            notes=notes,
            revision_request=revision_request,
            added_context=added_context,
            changed_goal=changed_goal,
            changed_constraint=changed_constraint,
            regression_case=regression_case,
            review_dir=review_dir,
        )
        summary = run_review_workflow(request)
        emit_json(summary)


def approve(
    target_type: Annotated[TargetType, typer.Argument()],
    target_id: Annotated[str, typer.Argument()],
    reviewer: Annotated[str | None, typer.Option("--reviewer")] = None,
    note: Annotated[list[str] | None, typer.Option("--note")] = None,
    review_dir: Annotated[Path, typer.Option("--review-dir")] = Path(
        ".omf/reviews",
    ),
) -> None:
    _run_review_command(
        target_type=target_type,
        target_id=target_id,
        action="approve",
        reviewer=reviewer,
        notes=tuple(note or ()),
        revision_request=None,
        review_dir=review_dir,
    )


def reject(
    target_type: Annotated[TargetType, typer.Argument()],
    target_id: Annotated[str, typer.Argument()],
    reviewer: Annotated[str | None, typer.Option("--reviewer")] = None,
    note: Annotated[list[str] | None, typer.Option("--note")] = None,
    review_dir: Annotated[Path, typer.Option("--review-dir")] = Path(
        ".omf/reviews",
    ),
) -> None:
    _run_review_command(
        target_type=target_type,
        target_id=target_id,
        action="reject",
        reviewer=reviewer,
        notes=tuple(note or ()),
        revision_request=None,
        review_dir=review_dir,
    )


def revise(
    target_type: Annotated[TargetType, typer.Argument()],
    target_id: Annotated[str, typer.Argument()],
    revision: Annotated[str, typer.Option("--revision")],
    reviewer: Annotated[str | None, typer.Option("--reviewer")] = None,
    note: Annotated[list[str] | None, typer.Option("--note")] = None,
    review_dir: Annotated[Path, typer.Option("--review-dir")] = Path(
        ".omf/reviews",
    ),
) -> None:
    _run_review_command(
        target_type=target_type,
        target_id=target_id,
        action="revise",
        reviewer=reviewer,
        notes=tuple(note or ()),
        revision_request=revision,
        review_dir=review_dir,
    )


def review(
    target_type: Annotated[TargetType, typer.Argument()],
    target_id: Annotated[str, typer.Argument()],
    action: Annotated[
        Literal[
            "approve",
            "reject",
            "revise",
            "add_context",
            "change_goal",
            "change_constraint",
            "mark_reusable",
            "mark_unsafe",
            "create_regression_case",
        ],
        typer.Argument(),
    ],
    reviewer: Annotated[str | None, typer.Option("--reviewer")] = None,
    note: Annotated[list[str] | None, typer.Option("--note")] = None,
    revision: Annotated[str | None, typer.Option("--revision")] = None,
    added_context: Annotated[
        list[str] | None,
        typer.Option("--added-context"),
    ] = None,
    changed_goal: Annotated[str | None, typer.Option("--changed-goal")] = None,
    changed_constraint: Annotated[
        str | None,
        typer.Option("--changed-constraint"),
    ] = None,
    regression_case: Annotated[
        str | None,
        typer.Option("--regression-case"),
    ] = None,
    review_dir: Annotated[Path, typer.Option("--review-dir")] = Path(
        ".omf/reviews",
    ),
) -> None:
    _run_review_command(
        target_type=target_type,
        target_id=target_id,
        action=action,
        reviewer=reviewer,
        notes=tuple(note or ()),
        revision_request=revision,
        review_dir=review_dir,
        added_context=tuple(added_context or ()),
        changed_goal=changed_goal,
        changed_constraint=changed_constraint,
        regression_case=regression_case,
    )


def register(app: typer.Typer) -> None:
    app.command(
        "approve",
        help="Approve an evidence, capability, replay, or eval target.",
    )(approve)
    app.command(
        "reject",
        help="Reject an evidence, capability, replay, or eval target.",
    )(reject)
    app.command("revise", help="Request revision for a reviewed artifact.")(revise)
    app.command("review", help="Record a structured human review action.")(review)
