from pathlib import Path
from typing import Literal

from pydantic import Field

from oh_my_field.models import StrictModel
from oh_my_field.storage import load_learning_patch_decision, load_manifest

type ExplainTargetType = Literal["capability", "harness", "learning-patch"]
type JsonValue = (
    str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
)


class ExplainError(Exception):
    pass


class ExplainRequest(StrictModel):
    target_type: ExplainTargetType
    target_id: str = Field(min_length=1)
    rule: str | None = None
    check: str | None = None
    capabilities_dir: Path = Path("capabilities")
    learning_patch_dir: Path = Path(".omf/learning_patches")


class ExplainSummary(StrictModel):
    target_type: ExplainTargetType
    target_id: str
    subject: str
    introduced_by: tuple[str, ...]
    evidence: tuple[str, ...]
    current_status: str
    payload: dict[str, JsonValue]


def explain_artifact(request: ExplainRequest) -> ExplainSummary:
    if request.target_type == "learning-patch":
        return _explain_learning_patch(request)
    if request.target_type == "harness":
        return _explain_harness(request)
    return _explain_capability(request)


def _explain_learning_patch(request: ExplainRequest) -> ExplainSummary:
    decision = load_learning_patch_decision(
        request.target_id,
        request.learning_patch_dir,
    )
    return ExplainSummary(
        target_type="learning-patch",
        target_id=decision.id,
        subject=decision.patch,
        introduced_by=(f"learning_patch_decision:{decision.id}",),
        evidence=(decision.learning_id,),
        current_status=decision.decision,
        payload={
            "patch_kind": decision.patch_kind,
            "reviewer": decision.reviewer,
            "notes": list(decision.notes),
            "manifest_path": decision.manifest_path,
            "before_eval_id": decision.before_eval_id,
            "after_eval_id": decision.after_eval_id,
            "pass_rate_delta": decision.pass_rate_delta,
        },
    )


def _explain_harness(request: ExplainRequest) -> ExplainSummary:
    manifest = load_manifest(request.target_id, request.capabilities_dir)
    check = request.check or request.rule or "harness"
    matching_patches = _matching_values(manifest.patches.harness, check)
    return ExplainSummary(
        target_type="harness",
        target_id=manifest.name,
        subject=check,
        introduced_by=(
            *(f"harness_patch:{patch}" for patch in matching_patches),
            f"capability:{manifest.name}",
        ),
        evidence=_evidence_ids(
            manifest.source_evidence_id,
            manifest.source_evidence_ids,
        ),
        current_status=manifest.harness.status,
        payload={
            "check_present": check in manifest.harness.checks,
            "required": check in manifest.harness.required_checks,
            "all_checks": list(manifest.harness.checks),
            "required_checks": list(manifest.harness.required_checks),
            "failures": list(manifest.harness.failures),
            "human_review_required": manifest.harness.human_review_required,
        },
    )


def _explain_capability(request: ExplainRequest) -> ExplainSummary:
    manifest = load_manifest(request.target_id, request.capabilities_dir)
    rule = request.rule or request.check or manifest.normalized_goal
    matches = {
        "workflow_nodes": _matching_values(manifest.workflow.nodes, rule),
        "harness_checks": _matching_values(manifest.harness.checks, rule),
        "required_checks": _matching_values(manifest.harness.required_checks, rule),
        "prompt_patches": _matching_values(manifest.patches.prompt, rule),
        "context_patches": _matching_values(manifest.patches.context, rule),
        "harness_patches": _matching_values(manifest.patches.harness, rule),
    }
    introduced_by = (
        *(f"prompt_patch:{patch}" for patch in matches["prompt_patches"]),
        *(f"context_patch:{patch}" for patch in matches["context_patches"]),
        *(f"harness_patch:{patch}" for patch in matches["harness_patches"]),
        f"capability:{manifest.name}",
    )
    return ExplainSummary(
        target_type="capability",
        target_id=manifest.name,
        subject=rule,
        introduced_by=introduced_by,
        evidence=_evidence_ids(
            manifest.source_evidence_id,
            manifest.source_evidence_ids,
        ),
        current_status=manifest.status,
        payload={
            "version": manifest.version,
            "runtime": manifest.runtime.name,
            "model": manifest.runtime.model,
            "matches": {key: list(value) for key, value in matches.items()},
            "promotion_harness_pass_rate": (
                manifest.promotion_metrics.harness_pass_rate
                if manifest.promotion_metrics is not None
                else None
            ),
        },
    )


def _matching_values(values: tuple[str, ...], needle: str) -> tuple[str, ...]:
    folded = needle.casefold()
    return tuple(value for value in values if folded in value.casefold())


def _evidence_ids(primary: str, values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys((primary, *values)))
