from pathlib import Path
from typing import Annotated, Literal

import typer

from oh_my_field.cli.errors import cli_errors
from oh_my_field.cli.output import emit_json
from oh_my_field.learn import LearnError, LearnRequest, run_learn_workflow
from oh_my_field.learning_patch import (
    LearningPatchError,
    LearningPatchRequest,
    apply_learning_patch,
)
from oh_my_field.models import PatchDecisionStatus


def learn(
    capability_name: Annotated[str, typer.Argument()],
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
    evidence_dir: Annotated[Path, typer.Option("--evidence-dir")] = Path(
        ".omf/evidence",
    ),
    learning_dir: Annotated[Path, typer.Option("--learning-dir")] = Path(
        ".omf/learning",
    ),
) -> None:
    with cli_errors(LearnError):
        request = LearnRequest(
            capability_name=capability_name,
            capabilities_dir=capabilities_dir,
            evidence_dir=evidence_dir,
            learning_dir=learning_dir,
        )
        summary = run_learn_workflow(request)
        emit_json(summary)


def _patch_decision(
    decision: Literal["accept", "reject", "accepted", "rejected"],
) -> PatchDecisionStatus:
    if decision in {"accept", "accepted"}:
        return "accepted"
    return "rejected"


def learn_patch(
    capability_name: Annotated[str, typer.Argument()],
    learning_id: Annotated[str, typer.Option("--learning-id")],
    patch_index: Annotated[int, typer.Option("--patch-index")],
    decision: Annotated[
        Literal["accept", "reject", "accepted", "rejected"],
        typer.Option("--decision"),
    ],
    patch_kind: Annotated[
        Literal["prompt", "context", "harness"],
        typer.Option("--patch-kind"),
    ] = "prompt",
    reviewer: Annotated[str | None, typer.Option("--reviewer")] = None,
    note: Annotated[list[str] | None, typer.Option("--note")] = None,
    before_eval_id: Annotated[
        str | None,
        typer.Option("--before-eval-id"),
    ] = None,
    after_eval_id: Annotated[str | None, typer.Option("--after-eval-id")] = None,
    pass_rate_delta: Annotated[
        float | None,
        typer.Option("--pass-rate-delta"),
    ] = None,
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
    learning_dir: Annotated[Path, typer.Option("--learning-dir")] = Path(
        ".omf/learning",
    ),
    learning_patch_dir: Annotated[
        Path,
        typer.Option("--learning-patch-dir"),
    ] = Path(".omf/learning_patches"),
) -> None:
    with cli_errors(LearningPatchError):
        request = LearningPatchRequest(
            capability_name=capability_name,
            learning_id=learning_id,
            patch_kind=patch_kind,
            patch_index=patch_index,
            decision=_patch_decision(decision),
            reviewer=reviewer,
            notes=tuple(note or ()),
            before_eval_id=before_eval_id,
            after_eval_id=after_eval_id,
            pass_rate_delta=pass_rate_delta,
            capabilities_dir=capabilities_dir,
            learning_dir=learning_dir,
            learning_patch_dir=learning_patch_dir,
        )
        summary = apply_learning_patch(request)
        emit_json(summary)


def register(app: typer.Typer) -> None:
    app.command(
        "learn",
        help="Export learning assets from capability evidence.",
    )(learn)
    app.command(
        "learn-patch",
        help="Accept or reject a learning prompt patch.",
    )(learn_patch)
