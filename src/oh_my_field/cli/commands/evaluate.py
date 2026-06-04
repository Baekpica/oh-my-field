from pathlib import Path
from typing import Annotated

import typer

from oh_my_field.application.eval import EvalError, EvalRequest, run_eval_workflow
from oh_my_field.cli.errors import cli_errors
from oh_my_field.cli.options import (
    eval_checklist_items,
    eval_rubric_scores,
    matrix_profiles,
)
from oh_my_field.cli.output import emit_json
from oh_my_field.eval_set import (
    EvalSetError,
    RegressionCaseRequest,
    upsert_regression_case,
)
from oh_my_field.models import StrictModel


class EvalMatrixItem(StrictModel):
    runtime_profile: str
    eval_id: str
    eval_path: str
    status: str


class EvalMatrixSummary(StrictModel):
    capability_name: str
    results: tuple[EvalMatrixItem, ...]


def evaluate(
    capability_name: Annotated[str, typer.Argument()],
    replay_id: Annotated[str | None, typer.Option("--replay-id")] = None,
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
    evidence_dir: Annotated[Path, typer.Option("--evidence-dir")] = Path(
        ".omf/evidence",
    ),
    replay_dir: Annotated[Path, typer.Option("--replay-dir")] = Path(
        ".omf/replays",
    ),
    eval_dir: Annotated[Path, typer.Option("--eval-dir")] = Path(
        ".omf/evals",
    ),
    eval_set: Annotated[str | None, typer.Option("--eval-set")] = None,
    eval_set_dir: Annotated[Path, typer.Option("--eval-set-dir")] = Path(
        ".omf/eval_sets",
    ),
    matrix: Annotated[list[str] | None, typer.Option("--matrix")] = None,
    harness_command: Annotated[
        list[str] | None,
        typer.Option("--harness-command"),
    ] = None,
    checklist_pass: Annotated[
        list[str] | None,
        typer.Option("--checklist-pass"),
    ] = None,
    checklist_fail: Annotated[
        list[str] | None,
        typer.Option("--checklist-fail"),
    ] = None,
    rubric_score: Annotated[
        list[str] | None,
        typer.Option("--rubric-score"),
    ] = None,
    command_cwd: Annotated[Path, typer.Option("--command-cwd")] = Path(),
    command_timeout_seconds: Annotated[
        int,
        typer.Option("--command-timeout-seconds"),
    ] = 60,
    approve_command_risk: Annotated[
        bool,
        typer.Option("--approve-command-risk"),
    ] = False,
    allow_env: Annotated[list[str] | None, typer.Option("--allow-env")] = None,
) -> None:
    # Build the request inside the guard: rubric parsing raises ValueError on
    # malformed --rubric-score, which the eval command reports as exit code 1.
    with cli_errors(EvalError, ValueError):
        request = EvalRequest(
            capability_name=capability_name,
            replay_id=replay_id,
            capabilities_dir=capabilities_dir,
            evidence_dir=evidence_dir,
            replay_dir=replay_dir,
            eval_dir=eval_dir,
            eval_set_dir=eval_set_dir,
            eval_set_name=eval_set,
            harness_commands=tuple(harness_command or ()),
            checklist_items=eval_checklist_items(
                passes=checklist_pass,
                failures=checklist_fail,
            ),
            rubric_scores=eval_rubric_scores(rubric_score),
            command_cwd=command_cwd,
            command_timeout_seconds=command_timeout_seconds,
            approve_command_risk=approve_command_risk,
            allow_env=tuple(allow_env or ()),
        )
        profiles = matrix_profiles(matrix)
        if profiles:
            results = tuple(_eval_matrix_item(request, profile) for profile in profiles)
            emit_json(
                EvalMatrixSummary(capability_name=capability_name, results=results),
            )
            return
        summary = run_eval_workflow(request)
        emit_json(summary)


def _eval_matrix_item(request: EvalRequest, runtime_profile: str) -> EvalMatrixItem:
    summary = run_eval_workflow(
        request.model_copy(update={"runtime_profile": runtime_profile}),
    )
    return EvalMatrixItem(
        runtime_profile=runtime_profile,
        eval_id=summary.eval_id,
        eval_path=summary.eval_path,
        status=summary.status,
    )


def regression_case(
    capability_name: Annotated[str, typer.Argument()],
    case_id: Annotated[str, typer.Option("--case-id")],
    eval_set: Annotated[str | None, typer.Option("--eval-set")] = None,
    eval_set_version: Annotated[str, typer.Option("--eval-set-version")] = "0.1.0",
    input_value: Annotated[list[str] | None, typer.Option("--input")] = None,
    check: Annotated[list[str] | None, typer.Option("--check")] = None,
    flaky_check: Annotated[list[str] | None, typer.Option("--flaky-check")] = None,
    harness_command: Annotated[
        list[str] | None,
        typer.Option("--harness-command"),
    ] = None,
    eval_set_dir: Annotated[Path, typer.Option("--eval-set-dir")] = Path(
        ".omf/eval_sets",
    ),
) -> None:
    with cli_errors(EvalSetError):
        request = RegressionCaseRequest(
            capability_name=capability_name,
            eval_set_name=eval_set or f"{capability_name}_regression",
            eval_set_version=eval_set_version,
            case_id=case_id,
            inputs=tuple(input_value or ()),
            expected_checks=tuple(check or ()),
            flaky_checks=tuple(flaky_check or ()),
            harness_commands=tuple(harness_command or ()),
            eval_set_dir=eval_set_dir,
        )
        summary = upsert_regression_case(request)
        emit_json(summary)


def register(app: typer.Typer) -> None:
    app.command(
        "eval",
        help="Evaluate a capability with harness, rubric, or matrix runs.",
    )(evaluate)
    app.command(
        "regression-case",
        help="Create or update a regression eval case.",
    )(regression_case)
