import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import Field

from oh_my_field.models import (
    HumanReview,
    HumanReviewAction,
    HumanReviewRecord,
    HumanReviewStatus,
    ReviewTargetType,
    StrictModel,
)
from oh_my_field.storage import write_human_review

type Clock = Callable[[], datetime]
type TokenFactory = Callable[[], str]


class ReviewError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ReviewDependencies:
    clock: Clock
    token_factory: TokenFactory


class ReviewRequest(StrictModel):
    target_type: ReviewTargetType
    target_id: str = Field(min_length=1)
    action: HumanReviewAction
    reviewer: str | None = None
    notes: tuple[str, ...] = ()
    revision_request: str | None = None
    added_context: tuple[str, ...] = ()
    changed_goal: str | None = None
    changed_constraint: str | None = None
    regression_case: str | None = None
    review_dir: Path


class ReviewSummary(StrictModel):
    review_id: str
    review_path: str
    target_type: str
    target_id: str
    status: str


def run_review_workflow(
    request: ReviewRequest,
    dependencies: ReviewDependencies | None = None,
) -> ReviewSummary:
    dependencies = dependencies or _default_dependencies()
    created_at = dependencies.clock().astimezone(UTC)
    review = HumanReviewRecord(
        id=f"{created_at:%Y%m%dT%H%M%SZ}-{dependencies.token_factory()}",
        created_at=created_at,
        target_type=request.target_type,
        target_id=request.target_id,
        action=request.action,
        review=HumanReview(
            status=_status_for_action(request.action),
            reviewer=request.reviewer,
            notes=request.notes,
            revision_request=request.revision_request,
            added_context=request.added_context,
            changed_goal=request.changed_goal,
            changed_constraint=request.changed_constraint,
            reusable=True if request.action == "mark_reusable" else None,
            unsafe=True if request.action == "mark_unsafe" else None,
            regression_case=request.regression_case,
            reviewed_at=created_at,
        ),
    )
    review_path = write_human_review(review, request.review_dir)
    return ReviewSummary(
        review_id=review.id,
        review_path=str(review_path),
        target_type=review.target_type,
        target_id=review.target_id,
        status=review.review.status,
    )


def _default_dependencies() -> ReviewDependencies:
    return ReviewDependencies(clock=_now_utc, token_factory=_token_suffix)


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _token_suffix() -> str:
    return secrets.token_hex(4)


def _status_for_action(action: HumanReviewAction) -> HumanReviewStatus:
    status_by_action: dict[HumanReviewAction, HumanReviewStatus] = {
        "approve": "approved",
        "reject": "rejected",
        "revise": "revision_requested",
        "add_context": "context_added",
        "change_goal": "goal_changed",
        "change_constraint": "constraint_changed",
        "mark_reusable": "marked_reusable",
        "mark_unsafe": "marked_unsafe",
        "create_regression_case": "regression_case_created",
    }
    return status_by_action[action]
