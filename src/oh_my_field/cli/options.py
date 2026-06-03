from pathlib import Path

from oh_my_field.capture import CaptureFileInput
from oh_my_field.models import CapturedFileRole, EvalChecklistItem, EvalRubricScore

RUBRIC_SCORE_REQUIRED_PARTS = 4
RUBRIC_SCORE_SPLIT_MAX = 4


class RubricScoreParseError(ValueError):
    def __str__(self) -> str:
        return "rubric score must use name:score:max_score:pass_threshold[:message]"


def capture_file_inputs(
    role: CapturedFileRole,
    paths: list[Path] | None,
) -> tuple[CaptureFileInput, ...]:
    """Build capture file inputs for a role from a list of CLI paths."""
    return tuple(CaptureFileInput(role=role, path=path) for path in paths or ())


def eval_checklist_items(
    *,
    passes: list[str] | None,
    failures: list[str] | None,
) -> tuple[EvalChecklistItem, ...]:
    """Build checklist items from --checklist-pass / --checklist-fail options."""
    return (
        *(
            EvalChecklistItem(
                name=item,
                status="pass",
                message=f"checklist item passed: {item}",
            )
            for item in passes or ()
        ),
        *(
            EvalChecklistItem(
                name=item,
                status="fail",
                message=f"checklist item failed: {item}",
            )
            for item in failures or ()
        ),
    )


def eval_rubric_scores(values: list[str] | None) -> tuple[EvalRubricScore, ...]:
    """Parse repeated --rubric-score options into rubric score models."""
    return tuple(_eval_rubric_score(value) for value in values or ())


def _eval_rubric_score(value: str) -> EvalRubricScore:
    parts = value.split(":", RUBRIC_SCORE_SPLIT_MAX)
    if len(parts) < RUBRIC_SCORE_REQUIRED_PARTS:
        raise RubricScoreParseError
    name, score_text, max_score_text, threshold_text, *message = parts
    score = float(score_text)
    max_score = float(max_score_text)
    pass_threshold = float(threshold_text)
    status = "pass" if score >= pass_threshold else "fail"
    default_message = f"rubric score {score:g}/{max_score:g}"
    return EvalRubricScore(
        name=name,
        score=score,
        max_score=max_score,
        pass_threshold=pass_threshold,
        status=status,
        message=message[0] if message else default_message,
    )


def matrix_profiles(values: list[str] | None) -> tuple[str, ...]:
    """Split comma/space separated --matrix options into unique profiles."""
    profiles = [
        profile.strip()
        for value in values or ()
        for profile in value.split(",")
        if profile.strip()
    ]
    return tuple(dict.fromkeys(profiles))
