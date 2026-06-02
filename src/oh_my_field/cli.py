from pathlib import Path
from typing import Annotated, Literal

import typer
from pydantic import ValidationError

from oh_my_field.capture import (
    CaptureError,
    CaptureFileInput,
    CaptureRequest,
    run_capture_workflow,
)
from oh_my_field.context import ContextError, ContextRequest, run_context_workflow
from oh_my_field.eval import EvalError, EvalRequest, run_eval_workflow
from oh_my_field.export import ExportError, ExportRequest, run_export_workflow
from oh_my_field.inspection import InspectRequest, inspect_artifact
from oh_my_field.learn import LearnError, LearnRequest, run_learn_workflow
from oh_my_field.models import (
    CapturedFileRole,
    EvalChecklistItem,
    EvalRubricScore,
    HumanReviewAction,
    ReviewTargetType,
)
from oh_my_field.orchestrate import (
    OrchestrateError,
    OrchestrateRequest,
    ResumeRequest,
    load_workflow_summary,
    run_orchestrate_workflow,
    run_resume_workflow,
)
from oh_my_field.promote import PromoteError, PromoteRequest, run_promote_workflow
from oh_my_field.reflect import ReflectError, ReflectRequest, run_reflect_workflow
from oh_my_field.registry import RegistryError, RegistryRequest, run_registry_workflow
from oh_my_field.replay import ReplayError, ReplayRequest, run_replay_workflow
from oh_my_field.review import ReviewError, ReviewRequest, run_review_workflow
from oh_my_field.rollback import RollbackError, RollbackRequest, rollback_workflow
from oh_my_field.storage import StorageError

app = typer.Typer(
    help="oh-my-field turns tacit know-how into reusable capabilities.",
    no_args_is_help=True,
)
RUBRIC_SCORE_REQUIRED_PARTS = 4
RUBRIC_SCORE_SPLIT_MAX = 4


class RubricScoreParseError(ValueError):
    def __str__(self) -> str:
        return "rubric score must use name:score:max_score:pass_threshold[:message]"


def _main() -> None:
    pass


app.callback()(_main)


def _capture(
    goal: Annotated[str, typer.Option("--goal")],
    prompt: Annotated[list[Path] | None, typer.Option("--prompt")] = None,
    context: Annotated[list[Path] | None, typer.Option("--context")] = None,
    tool_call: Annotated[list[Path] | None, typer.Option("--tool-call")] = None,
    command_output: Annotated[
        list[Path] | None,
        typer.Option("--command-output"),
    ] = None,
    diff: Annotated[list[Path] | None, typer.Option("--diff")] = None,
    test_result: Annotated[
        list[Path] | None,
        typer.Option("--test-result"),
    ] = None,
    artifact: Annotated[list[Path] | None, typer.Option("--artifact")] = None,
    command: Annotated[list[str] | None, typer.Option("--command")] = None,
    command_cwd: Annotated[Path, typer.Option("--command-cwd")] = Path(),
    command_timeout_seconds: Annotated[
        int,
        typer.Option("--command-timeout-seconds"),
    ] = 60,
    approve_command_risk: Annotated[
        bool,
        typer.Option("--approve-command-risk"),
    ] = False,
    feedback: Annotated[list[str] | None, typer.Option("--feedback")] = None,
    user_intervention: Annotated[
        list[str] | None,
        typer.Option("--user-intervention"),
    ] = None,
    final_artifact: Annotated[
        list[str] | None,
        typer.Option("--final-artifact"),
    ] = None,
    improvement_note: Annotated[
        list[str] | None,
        typer.Option("--improvement-note"),
    ] = None,
    outcome: Annotated[
        Literal["success", "failure", "unknown"],
        typer.Option("--outcome"),
    ] = "unknown",
    runtime_tool: Annotated[
        list[str] | None,
        typer.Option("--runtime-tool"),
    ] = None,
    retries: Annotated[int, typer.Option("--retries")] = 0,
    field: Annotated[str, typer.Option("--field")] = "local",
    runtime: Annotated[str, typer.Option("--runtime")] = "codex",
    model: Annotated[str | None, typer.Option("--model")] = None,
    evidence_dir: Annotated[Path, typer.Option("--evidence-dir")] = Path(
        ".omf/evidence",
    ),
) -> None:
    request = CaptureRequest(
        goal=goal,
        field=field,
        runtime=runtime,
        model=model,
        runtime_tools=tuple(runtime_tool or ()),
        evidence_dir=evidence_dir,
        files=(
            *_capture_file_inputs("prompt", prompt),
            *_capture_file_inputs("context", context),
            *_capture_file_inputs("tool_call", tool_call),
            *_capture_file_inputs("command_output", command_output),
            *_capture_file_inputs("diff", diff),
            *_capture_file_inputs("test_result", test_result),
            *_capture_file_inputs("artifact", artifact),
        ),
        commands=tuple(command or ()),
        command_cwd=command_cwd,
        command_timeout_seconds=command_timeout_seconds,
        approve_command_risk=approve_command_risk,
        retries=retries,
        feedback=tuple(feedback or ()),
        user_interventions=tuple(user_intervention or ()),
        final_artifacts=tuple(final_artifact or ()),
        improvement_notes=tuple(improvement_note or ()),
        success_or_failure_label=outcome,
    )
    try:
        summary = run_capture_workflow(request)
    except (CaptureError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


def _capture_file_inputs(
    role: CapturedFileRole,
    paths: list[Path] | None,
) -> tuple[CaptureFileInput, ...]:
    return tuple(CaptureFileInput(role=role, path=path) for path in paths or ())


app.command("capture")(_capture)


def _promote(
    evidence_id: Annotated[str, typer.Argument()],
    name: Annotated[str, typer.Option("--name")],
    description: Annotated[str, typer.Option("--description")],
    version: Annotated[str, typer.Option("--version")] = "0.1.0",
    evidence_dir: Annotated[Path, typer.Option("--evidence-dir")] = Path(
        ".omf/evidence",
    ),
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
) -> None:
    try:
        summary = run_promote_workflow(
            PromoteRequest(
                evidence_id=evidence_id,
                name=name,
                description=description,
                version=version,
                evidence_dir=evidence_dir,
                capabilities_dir=capabilities_dir,
            ),
        )
    except (PromoteError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


app.command("promote")(_promote)


def _replay(
    capability_name: Annotated[str, typer.Argument()],
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
    evidence_dir: Annotated[Path, typer.Option("--evidence-dir")] = Path(
        ".omf/evidence",
    ),
    replay_dir: Annotated[Path, typer.Option("--replay-dir")] = Path(
        ".omf/replays",
    ),
    execute: Annotated[bool, typer.Option("--execute")] = False,
    command_cwd: Annotated[Path, typer.Option("--command-cwd")] = Path(),
    command_timeout_seconds: Annotated[
        int,
        typer.Option("--command-timeout-seconds"),
    ] = 60,
    approve_command_risk: Annotated[
        bool,
        typer.Option("--approve-command-risk"),
    ] = False,
) -> None:
    try:
        summary = run_replay_workflow(
            ReplayRequest(
                capability_name=capability_name,
                capabilities_dir=capabilities_dir,
                evidence_dir=evidence_dir,
                replay_dir=replay_dir,
                execute_commands=execute,
                command_cwd=command_cwd,
                command_timeout_seconds=command_timeout_seconds,
                approve_command_risk=approve_command_risk,
            ),
        )
    except (ReplayError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


app.command("replay")(_replay)


def _eval(
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
) -> None:
    try:
        summary = run_eval_workflow(
            EvalRequest(
                capability_name=capability_name,
                replay_id=replay_id,
                capabilities_dir=capabilities_dir,
                evidence_dir=evidence_dir,
                replay_dir=replay_dir,
                eval_dir=eval_dir,
                harness_commands=tuple(harness_command or ()),
                checklist_items=_eval_checklist_items(
                    passes=checklist_pass,
                    failures=checklist_fail,
                ),
                rubric_scores=_eval_rubric_scores(rubric_score),
                command_cwd=command_cwd,
                command_timeout_seconds=command_timeout_seconds,
                approve_command_risk=approve_command_risk,
            ),
        )
    except (EvalError, StorageError, ValidationError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


app.command("eval")(_eval)


def _eval_checklist_items(
    *,
    passes: list[str] | None,
    failures: list[str] | None,
) -> tuple[EvalChecklistItem, ...]:
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


def _eval_rubric_scores(values: list[str] | None) -> tuple[EvalRubricScore, ...]:
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


def _approve(
    target_type: Annotated[
        Literal["evidence", "capability", "replay", "eval"],
        typer.Argument(),
    ],
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


app.command("approve")(_approve)


def _reject(
    target_type: Annotated[
        Literal["evidence", "capability", "replay", "eval"],
        typer.Argument(),
    ],
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


app.command("reject")(_reject)


def _revise(
    target_type: Annotated[
        Literal["evidence", "capability", "replay", "eval"],
        typer.Argument(),
    ],
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


app.command("revise")(_revise)


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
    try:
        summary = run_review_workflow(
            ReviewRequest(
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
            ),
        )
    except (ReviewError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


def _review(
    target_type: Annotated[
        Literal["evidence", "capability", "replay", "eval"],
        typer.Argument(),
    ],
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


app.command("review")(_review)


def _learn(
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
    try:
        summary = run_learn_workflow(
            LearnRequest(
                capability_name=capability_name,
                capabilities_dir=capabilities_dir,
                evidence_dir=evidence_dir,
                learning_dir=learning_dir,
            ),
        )
    except (LearnError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


app.command("learn")(_learn)


def _context(
    capability_name: Annotated[str, typer.Argument()],
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
    evidence_dir: Annotated[Path, typer.Option("--evidence-dir")] = Path(
        ".omf/evidence",
    ),
    context_dir: Annotated[Path, typer.Option("--context-dir")] = Path(
        ".omf/context",
    ),
    include_optional: Annotated[bool, typer.Option("--include-optional")] = False,
    query: Annotated[str | None, typer.Option("--query")] = None,
    max_chars: Annotated[int | None, typer.Option("--max-chars")] = None,
) -> None:
    try:
        summary = run_context_workflow(
            ContextRequest(
                capability_name=capability_name,
                capabilities_dir=capabilities_dir,
                evidence_dir=evidence_dir,
                context_dir=context_dir,
                include_optional=include_optional,
                query=query,
                max_chars=max_chars,
            ),
        )
    except (ContextError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


app.command("context")(_context)


def _run(
    goal: Annotated[str, typer.Option("--goal")],
    name: Annotated[str, typer.Option("--name")],
    description: Annotated[str, typer.Option("--description")],
    prompt: Annotated[list[Path] | None, typer.Option("--prompt")] = None,
    context: Annotated[list[Path] | None, typer.Option("--context")] = None,
    tool_call: Annotated[list[Path] | None, typer.Option("--tool-call")] = None,
    command_output: Annotated[
        list[Path] | None,
        typer.Option("--command-output"),
    ] = None,
    diff: Annotated[list[Path] | None, typer.Option("--diff")] = None,
    test_result: Annotated[
        list[Path] | None,
        typer.Option("--test-result"),
    ] = None,
    artifact: Annotated[list[Path] | None, typer.Option("--artifact")] = None,
    command: Annotated[list[str] | None, typer.Option("--command")] = None,
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
    runtime_tool: Annotated[
        list[str] | None,
        typer.Option("--runtime-tool"),
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
    field: Annotated[str, typer.Option("--field")] = "local",
    runtime: Annotated[str, typer.Option("--runtime")] = "codex",
    model: Annotated[str | None, typer.Option("--model")] = None,
    version: Annotated[str, typer.Option("--version")] = "0.1.0",
    allow_failed_capture: Annotated[
        bool,
        typer.Option("--allow-failed-capture"),
    ] = False,
    skip_replay_execute: Annotated[
        bool,
        typer.Option("--skip-replay-execute"),
    ] = False,
    skip_optional_context: Annotated[
        bool,
        typer.Option("--skip-optional-context"),
    ] = False,
    evidence_dir: Annotated[Path, typer.Option("--evidence-dir")] = Path(
        ".omf/evidence",
    ),
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
    replay_dir: Annotated[Path, typer.Option("--replay-dir")] = Path(
        ".omf/replays",
    ),
    eval_dir: Annotated[Path, typer.Option("--eval-dir")] = Path(
        ".omf/evals",
    ),
    context_dir: Annotated[Path, typer.Option("--context-dir")] = Path(
        ".omf/context",
    ),
    learning_dir: Annotated[Path, typer.Option("--learning-dir")] = Path(
        ".omf/learning",
    ),
    workflow_dir: Annotated[Path, typer.Option("--workflow-dir")] = Path(
        ".omf/workflows",
    ),
) -> None:
    request = OrchestrateRequest(
        goal=goal,
        capability_name=name,
        description=description,
        version=version,
        field=field,
        runtime=runtime,
        model=model,
        runtime_tools=tuple(runtime_tool or ()),
        files=(
            *_capture_file_inputs("prompt", prompt),
            *_capture_file_inputs("context", context),
            *_capture_file_inputs("tool_call", tool_call),
            *_capture_file_inputs("command_output", command_output),
            *_capture_file_inputs("diff", diff),
            *_capture_file_inputs("test_result", test_result),
            *_capture_file_inputs("artifact", artifact),
        ),
        commands=tuple(command or ()),
        command_cwd=command_cwd,
        command_timeout_seconds=command_timeout_seconds,
        approve_command_risk=approve_command_risk,
        harness_commands=tuple(harness_command or ()),
        checklist_items=_eval_checklist_items(
            passes=checklist_pass,
            failures=checklist_fail,
        ),
        rubric_scores=_eval_rubric_scores(rubric_score),
        execute_replay_commands=not skip_replay_execute,
        include_optional_context=not skip_optional_context,
        allow_failed_capture=allow_failed_capture,
        evidence_dir=evidence_dir,
        capabilities_dir=capabilities_dir,
        replay_dir=replay_dir,
        eval_dir=eval_dir,
        context_dir=context_dir,
        learning_dir=learning_dir,
        workflow_dir=workflow_dir,
    )
    try:
        summary = run_orchestrate_workflow(request)
    except (OrchestrateError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


app.command("run")(_run)


def _resume(
    run_id: Annotated[str, typer.Argument()],
    workflow_dir: Annotated[Path, typer.Option("--workflow-dir")] = Path(
        ".omf/workflows",
    ),
) -> None:
    try:
        summary = run_resume_workflow(
            ResumeRequest(run_id=run_id, workflow_dir=workflow_dir),
        )
    except (OrchestrateError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


app.command("resume")(_resume)


def _status(
    run_id: Annotated[str, typer.Argument()],
    workflow_dir: Annotated[Path, typer.Option("--workflow-dir")] = Path(
        ".omf/workflows",
    ),
) -> None:
    try:
        summary = load_workflow_summary(run_id, workflow_dir)
    except StorageError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


app.command("status")(_status)


def _registry(
    capability_name: Annotated[str | None, typer.Argument()] = None,
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
    eval_dir: Annotated[Path, typer.Option("--eval-dir")] = Path(".omf/evals"),
) -> None:
    try:
        summary = run_registry_workflow(
            RegistryRequest(
                capability_name=capability_name,
                capabilities_dir=capabilities_dir,
                eval_dir=eval_dir,
            ),
        )
    except (RegistryError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


app.command("registry")(_registry)


def _reflect(
    capability_name: Annotated[str, typer.Argument()],
    eval_id: Annotated[str | None, typer.Option("--eval-id")] = None,
    note: Annotated[list[str] | None, typer.Option("--note")] = None,
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
    evidence_dir: Annotated[Path, typer.Option("--evidence-dir")] = Path(
        ".omf/evidence",
    ),
    eval_dir: Annotated[Path, typer.Option("--eval-dir")] = Path(".omf/evals"),
    reflection_dir: Annotated[Path, typer.Option("--reflection-dir")] = Path(
        ".omf/reflections",
    ),
) -> None:
    try:
        summary = run_reflect_workflow(
            ReflectRequest(
                capability_name=capability_name,
                eval_id=eval_id,
                capabilities_dir=capabilities_dir,
                evidence_dir=evidence_dir,
                eval_dir=eval_dir,
                reflection_dir=reflection_dir,
                notes=tuple(note or ()),
            ),
        )
    except (ReflectError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


app.command("reflect")(_reflect)


def _inspect(
    target_type: Annotated[
        Literal[
            "evidence",
            "capability",
            "replay",
            "eval",
            "workflow",
            "context",
            "learning",
            "reflection",
        ],
        typer.Argument(),
    ],
    target_id: Annotated[str, typer.Argument()],
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
    evidence_dir: Annotated[Path, typer.Option("--evidence-dir")] = Path(
        ".omf/evidence",
    ),
    replay_dir: Annotated[Path, typer.Option("--replay-dir")] = Path(
        ".omf/replays",
    ),
    eval_dir: Annotated[Path, typer.Option("--eval-dir")] = Path(".omf/evals"),
    workflow_dir: Annotated[Path, typer.Option("--workflow-dir")] = Path(
        ".omf/workflows",
    ),
    context_dir: Annotated[Path, typer.Option("--context-dir")] = Path(
        ".omf/context",
    ),
    learning_dir: Annotated[Path, typer.Option("--learning-dir")] = Path(
        ".omf/learning",
    ),
    reflection_dir: Annotated[Path, typer.Option("--reflection-dir")] = Path(
        ".omf/reflections",
    ),
) -> None:
    try:
        summary = inspect_artifact(
            InspectRequest(
                target_type=target_type,
                target_id=target_id,
                capabilities_dir=capabilities_dir,
                evidence_dir=evidence_dir,
                replay_dir=replay_dir,
                eval_dir=eval_dir,
                workflow_dir=workflow_dir,
                context_dir=context_dir,
                learning_dir=learning_dir,
                reflection_dir=reflection_dir,
            ),
        )
    except (StorageError, ValidationError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


app.command("inspect")(_inspect)


def _export(
    capability_name: Annotated[str, typer.Argument()],
    approve_export: Annotated[
        bool,
        typer.Option("--approve-export"),
    ] = False,
    capabilities_dir: Annotated[Path, typer.Option("--capabilities-dir")] = Path(
        "capabilities",
    ),
    evidence_dir: Annotated[Path, typer.Option("--evidence-dir")] = Path(
        ".omf/evidence",
    ),
    eval_dir: Annotated[Path, typer.Option("--eval-dir")] = Path(".omf/evals"),
    context_dir: Annotated[Path, typer.Option("--context-dir")] = Path(
        ".omf/context",
    ),
    learning_dir: Annotated[Path, typer.Option("--learning-dir")] = Path(
        ".omf/learning",
    ),
    reflection_dir: Annotated[Path, typer.Option("--reflection-dir")] = Path(
        ".omf/reflections",
    ),
    export_dir: Annotated[Path, typer.Option("--export-dir")] = Path(
        ".omf/exports",
    ),
) -> None:
    try:
        summary = run_export_workflow(
            ExportRequest(
                capability_name=capability_name,
                approve_export=approve_export,
                capabilities_dir=capabilities_dir,
                evidence_dir=evidence_dir,
                eval_dir=eval_dir,
                context_dir=context_dir,
                learning_dir=learning_dir,
                reflection_dir=reflection_dir,
                export_dir=export_dir,
            ),
        )
    except (ExportError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


app.command("export")(_export)


def _rollback(
    run_id: Annotated[str, typer.Argument()],
    to_node: Annotated[
        Literal[
            "observe_capture",
            "structure_promote",
            "context_pack",
            "execute_replay",
            "evaluate_harness",
            "learn_export",
        ],
        typer.Option("--to-node"),
    ],
    reason: Annotated[str, typer.Option("--reason")] = "manual rollback",
    workflow_dir: Annotated[Path, typer.Option("--workflow-dir")] = Path(
        ".omf/workflows",
    ),
) -> None:
    try:
        summary = rollback_workflow(
            RollbackRequest(
                run_id=run_id,
                to_node=to_node,
                reason=reason,
                workflow_dir=workflow_dir,
            ),
        )
    except (RollbackError, StorageError, ValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(summary.model_dump_json())


app.command("rollback")(_rollback)
